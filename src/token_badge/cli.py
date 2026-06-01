from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from typing import Any

from token_badge.ccusage import CcusageError, collect_provider_usage
from token_badge.api import TokenBadgeAPI, run_http_server
from token_badge.dependencies import collect_dependency_checks, required_checks_pass
from token_badge.evidence import build_usage_evidence, evidence_summary
from token_badge.github_profile import (
    GitHubProfileClient,
    GitHubProfileError,
    ProfileVisibility,
    badge_base_url_from_env,
    profile_visibility_for_badge,
)
from token_badge.storage import StorageConfigurationError, StorageError, TiDBStorage
from token_badge.tiers import DEFAULT_TIERS, earned_tier, next_tier
from token_badge.upload import UploadError, fetch_ranking, request_challenge, upload_usage_snapshot


def _tier_payload(total_tokens: int) -> dict[str, Any]:
    earned = earned_tier(total_tokens)
    upcoming = next_tier(total_tokens)
    return {
        "earned": None
        if earned is None
        else {
            "name": earned.name,
            "threshold": earned.threshold,
            "description": earned.description,
        },
        "next": None
        if upcoming is None
        else {
            "name": upcoming.name,
            "threshold": upcoming.threshold,
            "tokens_remaining": upcoming.threshold - total_tokens,
        },
    }


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _profile_visibility_payload(visibility: ProfileVisibility) -> dict[str, Any]:
    return {
        "profile_url": visibility.profile_url,
        "share_url": visibility.share_url,
        "visible": visibility.visible,
        "detail": visibility.detail,
    }


def _print_profile_visibility(visibility: ProfileVisibility) -> None:
    if visibility.visible is True:
        print(f"Profile display: visible ({visibility.profile_url})")
    elif visibility.visible is False:
        print("Profile display: not visible yet")
        print(f"Manual step: open {visibility.share_url} and click \"Share to Profile\".")
    else:
        print(f"Profile display: not verified ({visibility.detail})")


def run_usage_provider(args: argparse.Namespace, provider: str) -> int:
    profile_client = None
    if args.profile_badge:
        if not args.upload_url:
            print("error: --profile-badge requires --upload-url so a backend grant can be accepted first")
            return 1
        profile_client = GitHubProfileClient()
        try:
            authenticated_login = profile_client.authenticated_login()
        except GitHubProfileError as exc:
            print(f"error: {exc}")
            return 1
        if not args.github:
            args.github = authenticated_login
        elif args.github.lower() != authenticated_login.lower():
            print(
                "error: --profile-badge can only update the authenticated GitHub profile "
                f"({authenticated_login})"
            )
            return 1

    collector_installation_id = args.collector_id or args.subject
    challenge_nonce = args.challenge
    if args.upload_url and not collector_installation_id:
        print("error: --collector-id is required when --upload-url is used")
        return 1

    if args.upload_url and not challenge_nonce:
        try:
            challenge = request_challenge(
                args.upload_url,
                collector_installation_id=collector_installation_id,
                github_login=args.github,
                github_node_id=args.github_node_id,
            )
        except UploadError as exc:
            print(f"error: {exc}")
            return 1
        challenge_nonce = challenge.get("challenge_nonce")
        if not isinstance(challenge_nonce, str) or not challenge_nonce:
            print("error: upload endpoint did not return a challenge_nonce")
            return 1

    try:
        snapshot = collect_provider_usage(
            provider,
            since=args.since,
            until=args.until,
            timezone=args.timezone,
            speed=getattr(args, "speed", None),
        )
    except CcusageError as exc:
        print(f"error: {exc}")
        return 1

    trust_level = "local-self-reported"
    evidence = None
    upload = None
    if challenge_nonce:
        evidence_payload = build_usage_evidence(
            provider=snapshot.provider,
            usage_kind=snapshot.usage_kind,
            source=snapshot.source,
            trust_level=trust_level,
            total_tokens=snapshot.total_tokens,
            challenge_nonce=challenge_nonce,
            collector_installation_id=collector_installation_id,
            github_login=args.github,
            raw_totals=snapshot.raw_totals,
        )
        evidence = evidence_summary(evidence_payload)

    if args.upload_url:
        if evidence is None:
            print("error: usage upload requires a challenge-bound evidence hash")
            return 1
        upload_payload = {
            "challenge_nonce": evidence["challenge_nonce"],
            "collector_installation_id": collector_installation_id,
            "github_login": args.github,
            "github_node_id": args.github_node_id,
            "provider": snapshot.provider,
            "raw_totals": snapshot.raw_totals,
            "report_hash": evidence["report_hash"],
            "source": snapshot.source,
            "total_tokens": snapshot.total_tokens,
            "trust_level": trust_level,
            "usage_kind": snapshot.usage_kind,
        }
        try:
            upload = upload_usage_snapshot(args.upload_url, upload_payload)
        except UploadError as exc:
            print(f"error: {exc}")
            return 1

    profile_badge = None
    if args.profile_badge:
        badge_base_url = args.badge_base_url or badge_base_url_from_env() or args.upload_url
        try:
            update = profile_client.install_badge(
                github_login=args.github,
                badge_base_url=badge_base_url,
                dry_run=False,
                message=args.profile_badge_message,
            )
        except GitHubProfileError as exc:
            print(f"error: {exc}")
            return 1
        profile_badge = {
            "github_login": update.github_login,
            "repository": update.repository,
            "changed": update.changed,
            "commit_sha": update.commit_sha,
            "visibility": _profile_visibility_payload(
                profile_visibility_for_badge(update.github_login, badge_base_url)
            ),
        }

    payload = {
        "as_of": datetime.now(UTC).isoformat(),
        "provider": snapshot.provider,
        "usage_kind": snapshot.usage_kind,
        "source": snapshot.source,
        "trust_level": trust_level,
        "github_login": args.github,
        "collector_subject_hint": args.subject,
        "collector_installation_id": collector_installation_id,
        "total_tokens": snapshot.total_tokens,
        "evidence": evidence,
        "upload": upload,
        "profile_badge": profile_badge,
        "tiers": _tier_payload(snapshot.total_tokens),
        "raw_totals": snapshot.raw_totals if args.include_raw_totals else None,
    }

    if args.json:
        _print_json(payload)
        return 0

    earned = payload["tiers"]["earned"]
    next_badge = payload["tiers"]["next"]
    print(f"Provider: {snapshot.provider}")
    print(f"Usage kind: {snapshot.usage_kind}")
    print(f"Total tokens: {snapshot.total_tokens:,}")
    print(f"Trust level: {payload['trust_level']}")
    if args.github:
        print(f"GitHub: {args.github}")
    if evidence:
        print(f"Challenge: {evidence['challenge_nonce']}")
        print(f"Report hash: {evidence['report_hash']}")
    if upload:
        print(f"Upload: {upload['status']} ({upload['snapshot_id']})")
    if profile_badge:
        action = "updated" if profile_badge["changed"] else "already up to date"
        print(f"Profile badge: {action} ({profile_badge['repository']})")
        _print_profile_visibility(ProfileVisibility(**profile_badge["visibility"]))
    print(f"Earned badge: {earned['name'] if earned else 'None yet'}")
    if next_badge:
        print(
            "Next badge: "
            f"{next_badge['name']} at {next_badge['threshold']:,} "
            f"({next_badge['tokens_remaining']:,} tokens remaining)"
        )
    return 0


def run_codex(args: argparse.Namespace) -> int:
    return run_usage_provider(args, "codex")


def run_claude(args: argparse.Namespace) -> int:
    return run_usage_provider(args, "claude")


def run_tiers(args: argparse.Namespace) -> int:
    rows = [
        {
            "threshold": tier.threshold,
            "name": tier.name,
            "description": tier.description,
        }
        for tier in DEFAULT_TIERS
    ]
    if args.json:
        _print_json({"tiers": rows})
        return 0

    for tier in DEFAULT_TIERS:
        print(f"{tier.threshold:>15,}  {tier.name}")
    return 0


def run_doctor(args: argparse.Namespace) -> int:
    checks = collect_dependency_checks()
    payload = {
        "ok": required_checks_pass(checks),
        "checks": [check.to_dict() for check in checks],
    }
    if args.json:
        _print_json(payload)
        return 0 if payload["ok"] else 1

    print("Token Badge dependency check")
    for check in checks:
        marker = "ok" if check.ok else check.status
        requirement = "required" if check.required else "optional"
        print(f"- {check.name}: {marker} ({requirement})")
        print(f"  {check.detail}")
        if check.remediation:
            print(f"  fix: {check.remediation}")
    return 0 if payload["ok"] else 1


def run_init_db(args: argparse.Namespace) -> int:
    try:
        storage = TiDBStorage.from_env()
        storage.initialize_schema()
    except (StorageConfigurationError, StorageError) as exc:
        print(f"error: {exc}")
        return 1
    print("TiDB schema is ready")
    return 0


def run_serve(args: argparse.Namespace) -> int:
    try:
        storage = TiDBStorage.from_env()
    except StorageConfigurationError as exc:
        print(f"error: {exc}")
        return 1
    run_http_server(TokenBadgeAPI(storage), host=args.host, port=args.port)
    return 0


def run_profile_badge(args: argparse.Namespace) -> int:
    badge_base_url = args.badge_base_url or badge_base_url_from_env()
    if not badge_base_url:
        print("error: --badge-base-url or TOKEN_BADGE_PUBLIC_URL is required")
        return 1

    try:
        update = GitHubProfileClient().install_badge(
            github_login=args.github,
            badge_base_url=badge_base_url,
            dry_run=args.dry_run,
            message=args.message,
            branch=args.branch,
        )
    except GitHubProfileError as exc:
        print(f"error: {exc}")
        return 1

    payload = {
        "github_login": update.github_login,
        "repository": update.repository,
        "changed": update.changed,
        "dry_run": update.dry_run,
        "commit_sha": update.commit_sha,
    }
    visibility = None
    if not args.dry_run:
        visibility = profile_visibility_for_badge(update.github_login, badge_base_url)
        payload["visibility"] = _profile_visibility_payload(visibility)
    if args.dry_run:
        payload["readme"] = update.content

    if args.json:
        _print_json(payload)
        return 0

    action = "would update" if args.dry_run and update.changed else "updated"
    if not update.changed:
        action = "already up to date"
    print(f"GitHub: {update.github_login}")
    print(f"Repository: {update.repository}")
    print(f"Profile README: {action}")
    if update.commit_sha:
        print(f"Commit: {update.commit_sha}")
    if visibility:
        _print_profile_visibility(visibility)
    return 0


def _prompt_yes_no(question: str) -> bool:
    try:
        answer = input(f"{question} [y/N]: ").strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def run_start(args: argparse.Namespace, confirm=_prompt_yes_no) -> int:
    """One-shot quickstart: upload usage, report the badge and percentile, then
    offer to install the GitHub profile badge."""
    if not args.upload_url:
        print("error: start requires --upload-url so usage can be ranked against other adopters")
        return 1

    profile_client = GitHubProfileClient()
    github_login = args.github
    if not github_login:
        try:
            github_login = profile_client.authenticated_login()
        except GitHubProfileError as exc:
            print(f"error: {exc}")
            return 1

    collector_installation_id = args.collector_id or args.subject
    if not collector_installation_id:
        print("error: start requires --collector-id (falls back to --subject for the prototype)")
        return 1

    try:
        challenge = request_challenge(
            args.upload_url,
            collector_installation_id=collector_installation_id,
            github_login=github_login,
            github_node_id=args.github_node_id,
        )
    except UploadError as exc:
        print(f"error: {exc}")
        return 1
    challenge_nonce = challenge.get("challenge_nonce")
    if not isinstance(challenge_nonce, str) or not challenge_nonce:
        print("error: upload endpoint did not return a challenge_nonce")
        return 1

    try:
        snapshot = collect_provider_usage(
            args.provider,
            since=args.since,
            until=args.until,
            timezone=args.timezone,
            speed=getattr(args, "speed", None),
        )
    except CcusageError as exc:
        print(f"error: {exc}")
        return 1

    trust_level = "local-self-reported"
    evidence = evidence_summary(
        build_usage_evidence(
            provider=snapshot.provider,
            usage_kind=snapshot.usage_kind,
            source=snapshot.source,
            trust_level=trust_level,
            total_tokens=snapshot.total_tokens,
            challenge_nonce=challenge_nonce,
            collector_installation_id=collector_installation_id,
            github_login=github_login,
            raw_totals=snapshot.raw_totals,
        )
    )

    try:
        upload_usage_snapshot(
            args.upload_url,
            {
                "challenge_nonce": evidence["challenge_nonce"],
                "collector_installation_id": collector_installation_id,
                "github_login": github_login,
                "github_node_id": args.github_node_id,
                "provider": snapshot.provider,
                "raw_totals": snapshot.raw_totals,
                "report_hash": evidence["report_hash"],
                "source": snapshot.source,
                "total_tokens": snapshot.total_tokens,
                "trust_level": trust_level,
                "usage_kind": snapshot.usage_kind,
            },
        )
        ranking = fetch_ranking(args.upload_url, github_login)
    except UploadError as exc:
        print(f"error: {exc}")
        return 1

    earned = earned_tier(snapshot.total_tokens)
    summary = {
        "github_login": github_login,
        "provider": snapshot.provider,
        "total_tokens": snapshot.total_tokens,
        "earned_badge": None if earned is None else earned.name,
        "ranking": ranking,
    }

    if args.json:
        _print_json(summary)
    else:
        print(f"Total consumption: {snapshot.total_tokens:,} tokens ({snapshot.provider})")
        print(f"Badge tier: {earned.name if earned else 'None yet'}")
        print(ranking.get("message", ""))

    # --install-badge installs without prompting (for agents driving the flow);
    # --json without it is report-only; otherwise ask the human.
    if args.install_badge:
        pass
    elif args.json:
        return 0
    elif not confirm("Create your GitHub profile repo and show the badge?"):
        print("No problem — skipping profile badge. Your usage is still recorded.")
        return 0

    badge_base_url = args.badge_base_url or badge_base_url_from_env() or args.upload_url
    try:
        update = profile_client.install_badge(
            github_login=github_login,
            badge_base_url=badge_base_url,
            dry_run=False,
            message=args.profile_badge_message,
            create_repo=True,
        )
    except GitHubProfileError as exc:
        print(f"error: {exc}")
        return 1

    if update.repo_created:
        print(f"Profile repository: created ({update.repository})")
    action = "updated" if update.changed else "already up to date"
    print(f"Profile badge: {action} ({update.repository})")
    _print_profile_visibility(profile_visibility_for_badge(update.github_login, badge_base_url))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="token-badge",
        description="Collect subscription-agent token totals and map them to badge tiers.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    def add_usage_provider_arguments(command: argparse.ArgumentParser) -> None:
        command.add_argument("--github", help="GitHub login to include in the local report")
        command.add_argument("--github-node-id", help="Stable GitHub node_id from backend enrollment")
        command.add_argument(
            "--subject",
            help="Optional local collector subject hint; server enrollment should create the real ID",
        )
        command.add_argument(
            "--collector-id",
            help="Collector installation ID issued during enrollment; falls back to --subject for the prototype",
        )
        command.add_argument(
            "--challenge",
            help="Server-issued challenge nonce to bind the local usage report to a collection attempt",
        )
        command.add_argument(
            "--upload-url",
            help="Backend base URL; when set, request a challenge if needed and upload minimal usage metadata",
        )
        command.add_argument("--since", help="Start date passed to ccusage, YYYY-MM-DD or YYYYMMDD")
        command.add_argument("--until", help="End date passed to ccusage, inclusive")
        command.add_argument("--timezone", help="IANA timezone passed to ccusage")
        command.add_argument(
            "--profile-badge",
            action="store_true",
            help="After a successful upload, install or refresh the badge in the authenticated GitHub profile README",
        )
        command.add_argument(
            "--profile-badge-message",
            default="Add Token Badge profile badge",
            help="Commit message for --profile-badge",
        )
        command.add_argument(
            "--badge-base-url",
            help="Public badge URL for --profile-badge; defaults to TOKEN_BADGE_PUBLIC_URL or --upload-url",
        )
        command.add_argument("--include-raw-totals", action="store_true")
        command.add_argument("--json", action="store_true", help="Emit JSON")

    codex = subcommands.add_parser("codex", help="Collect Codex subscription usage via ccusage")
    add_usage_provider_arguments(codex)
    codex.add_argument(
        "--speed",
        choices=("auto", "standard", "fast"),
        help="Codex cost speed tier passed to ccusage",
    )
    codex.set_defaults(func=run_codex)

    claude = subcommands.add_parser("claude", help="Collect Claude Code subscription usage via ccusage")
    add_usage_provider_arguments(claude)
    claude.set_defaults(func=run_claude)

    start = subcommands.add_parser(
        "start",
        help="Quickstart: upload usage, show the badge tier and percentile, then offer the profile badge",
    )
    start.add_argument(
        "--provider",
        choices=("codex", "claude"),
        default="claude",
        help="Subscription agent to collect usage from (default: claude)",
    )
    start.add_argument("--github", help="GitHub login; defaults to the authenticated local GitHub user")
    start.add_argument("--github-node-id", help="Stable GitHub node_id from backend enrollment")
    start.add_argument("--subject", help="Optional local collector subject hint; falls back to --collector-id")
    start.add_argument("--collector-id", help="Collector installation ID issued during enrollment")
    start.add_argument(
        "--upload-url",
        required=True,
        help="Backend base URL used to upload usage and rank it against other adopters",
    )
    start.add_argument("--since", help="Start date passed to ccusage, YYYY-MM-DD or YYYYMMDD")
    start.add_argument("--until", help="End date passed to ccusage, inclusive")
    start.add_argument("--timezone", help="IANA timezone passed to ccusage")
    start.add_argument(
        "--speed",
        choices=("auto", "standard", "fast"),
        help="Codex cost speed tier passed to ccusage (codex provider only)",
    )
    start.add_argument(
        "--badge-base-url",
        help="Public badge URL for the profile badge; defaults to TOKEN_BADGE_PUBLIC_URL or --upload-url",
    )
    start.add_argument(
        "--profile-badge-message",
        default="Add Token Badge profile badge",
        help="Commit message used when installing the profile badge",
    )
    start.add_argument(
        "--install-badge",
        action="store_true",
        help="Create the profile repo (if needed) and install the badge without prompting; for agent-driven runs",
    )
    start.add_argument(
        "--json",
        action="store_true",
        help="Emit the usage, tier, and percentile summary as JSON; report-only unless --install-badge is also set",
    )
    start.set_defaults(func=run_start)

    tiers = subcommands.add_parser("tiers", help="Show badge tiers")
    tiers.add_argument("--json", action="store_true", help="Emit JSON")
    tiers.set_defaults(func=run_tiers)

    doctor = subcommands.add_parser("doctor", help="Check local collector dependencies")
    doctor.add_argument("--json", action="store_true", help="Emit JSON")
    doctor.set_defaults(func=run_doctor)

    init_db = subcommands.add_parser("init-db", help="Create or update the TiDB schema")
    init_db.set_defaults(func=run_init_db)

    serve = subcommands.add_parser("serve", help="Run the Token Badge upload API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=run_serve)

    profile_badge = subcommands.add_parser("profile-badge", help="Install the badge link in a GitHub profile README")
    profile_badge.add_argument("--github", help="GitHub login; defaults to the authenticated local GitHub user")
    profile_badge.add_argument(
        "--badge-base-url",
        help="Public Token Badge service URL; defaults to TOKEN_BADGE_PUBLIC_URL",
    )
    profile_badge.add_argument(
        "--message",
        default="Add Token Badge profile badge",
        help="Commit message for the profile README update",
    )
    profile_badge.add_argument("--branch", help="Optional target branch; defaults to the profile repository default")
    profile_badge.add_argument("--dry-run", action="store_true", help="Show the planned README content without committing")
    profile_badge.add_argument("--json", action="store_true", help="Emit JSON")
    profile_badge.set_defaults(func=run_profile_badge)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
