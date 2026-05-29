from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from typing import Any

from token_badge.ccusage import CcusageError, collect_codex_usage
from token_badge.tiers import DEFAULT_TIERS, earned_tier, next_tier


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


def run_codex(args: argparse.Namespace) -> int:
    try:
        snapshot = collect_codex_usage(
            since=args.since,
            until=args.until,
            timezone=args.timezone,
            speed=args.speed,
        )
    except CcusageError as exc:
        print(f"error: {exc}")
        return 1

    payload = {
        "as_of": datetime.now(UTC).isoformat(),
        "provider": snapshot.provider,
        "usage_kind": snapshot.usage_kind,
        "source": snapshot.source,
        "trust_level": "local-self-reported",
        "github_login": args.github,
        "collector_subject_hint": args.subject,
        "total_tokens": snapshot.total_tokens,
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
    print(f"Earned badge: {earned['name'] if earned else 'None yet'}")
    if next_badge:
        print(
            "Next badge: "
            f"{next_badge['name']} at {next_badge['threshold']:,} "
            f"({next_badge['tokens_remaining']:,} tokens remaining)"
        )
    return 0


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="token-badge",
        description="Collect subscription-agent token totals and map them to badge tiers.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    codex = subcommands.add_parser("codex", help="Collect Codex subscription usage via ccusage")
    codex.add_argument("--github", help="GitHub login to include in the local report")
    codex.add_argument(
        "--subject",
        help="Optional local collector subject hint; server enrollment should create the real ID",
    )
    codex.add_argument("--since", help="Start date passed to ccusage, YYYY-MM-DD or YYYYMMDD")
    codex.add_argument("--until", help="End date passed to ccusage, inclusive")
    codex.add_argument("--timezone", help="IANA timezone passed to ccusage")
    codex.add_argument(
        "--speed",
        choices=("auto", "standard", "fast"),
        help="Codex cost speed tier passed to ccusage",
    )
    codex.add_argument("--include-raw-totals", action="store_true")
    codex.add_argument("--json", action="store_true", help="Emit JSON")
    codex.set_defaults(func=run_codex)

    tiers = subcommands.add_parser("tiers", help="Show badge tiers")
    tiers.add_argument("--json", action="store_true", help="Emit JSON")
    tiers.set_defaults(func=run_tiers)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

