from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from token_badge.dependencies import CCUSAGE_INSTALL_GUIDANCE


class CcusageError(RuntimeError):
    """Raised when ccusage cannot produce a usable usage report."""


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    command_provider: str
    display_name: str
    supports_speed: bool = False


@dataclass(frozen=True)
class UsageSnapshot:
    provider: str
    usage_kind: str
    source: str
    total_tokens: int
    raw_totals: dict[str, Any]


PROVIDERS: dict[str, ProviderConfig] = {
    "codex": ProviderConfig(
        provider="codex",
        command_provider="codex",
        display_name="Codex",
        supports_speed=True,
    ),
    "claude": ProviderConfig(
        provider="claude",
        command_provider="claude",
        display_name="Claude Code",
    ),
}


def load_provider_monthly_report(
    provider: str,
    *,
    command_provider: str | None = None,
    since: str | None = None,
    until: str | None = None,
    timezone: str | None = None,
    speed: str | None = None,
    supports_speed: bool = False,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """Run ccusage's provider monthly report in JSON mode."""
    if not shutil.which("ccusage"):
        raise CcusageError(f"ccusage is not installed or is not on PATH. {CCUSAGE_INSTALL_GUIDANCE}")

    command_provider = command_provider or provider
    command = ["ccusage", command_provider, "monthly", "--json"]
    if since:
        command.extend(["--since", since])
    if until:
        command.extend(["--until", until])
    if timezone:
        command.extend(["--timezone", timezone])
    if speed and supports_speed:
        command.extend(["--speed", speed])
    elif speed:
        raise CcusageError(f"{provider} usage does not support --speed")

    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise CcusageError(f"ccusage failed: {detail}") from exc
    except subprocess.TimeoutExpired as exc:
        raise CcusageError(f"ccusage timed out while reading {provider} usage") from exc

    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise CcusageError("ccusage returned non-JSON output") from exc

    if not isinstance(report, dict):
        raise CcusageError("ccusage returned an unexpected JSON shape")
    return report


def total_tokens_from_report(report: dict[str, Any]) -> int:
    """Extract a total token count from a ccusage monthly JSON report."""
    totals = report.get("totals")
    if isinstance(totals, dict) and isinstance(totals.get("totalTokens"), int):
        return totals["totalTokens"]

    monthly = report.get("monthly")
    if isinstance(monthly, list):
        total = 0
        for row in monthly:
            if not isinstance(row, dict) or not isinstance(row.get("totalTokens"), int):
                raise CcusageError("monthly report rows are missing integer totalTokens")
            total += row["totalTokens"]
        return total

    raise CcusageError("report is missing totals.totalTokens")


def collect_provider_usage(provider: str, **kwargs: Any) -> UsageSnapshot:
    config = PROVIDERS[provider]
    report = load_provider_monthly_report(
        config.provider,
        command_provider=config.command_provider,
        supports_speed=config.supports_speed,
        **kwargs,
    )
    totals = report.get("totals") if isinstance(report.get("totals"), dict) else {}
    return UsageSnapshot(
        provider=config.provider,
        usage_kind="subscription",
        source=f"ccusage {config.command_provider} monthly --json",
        total_tokens=total_tokens_from_report(report),
        raw_totals=totals,
    )


def collect_codex_usage(**kwargs: Any) -> UsageSnapshot:
    return collect_provider_usage("codex", **kwargs)


def collect_claude_usage(**kwargs: Any) -> UsageSnapshot:
    return collect_provider_usage("claude", **kwargs)
