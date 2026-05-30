from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from token_badge.dependencies import CCUSAGE_INSTALL_GUIDANCE


class CcusageError(RuntimeError):
    """Raised when ccusage cannot produce a usable Codex usage report."""


@dataclass(frozen=True)
class CodexUsageSnapshot:
    provider: str
    usage_kind: str
    source: str
    total_tokens: int
    raw_totals: dict[str, Any]


def load_codex_monthly_report(
    *,
    since: str | None = None,
    until: str | None = None,
    timezone: str | None = None,
    speed: str | None = None,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """Run ccusage's Codex monthly report in JSON mode."""
    if not shutil.which("ccusage"):
        raise CcusageError(f"ccusage is not installed or is not on PATH. {CCUSAGE_INSTALL_GUIDANCE}")

    command = ["ccusage", "codex", "monthly", "--json"]
    if since:
        command.extend(["--since", since])
    if until:
        command.extend(["--until", until])
    if timezone:
        command.extend(["--timezone", timezone])
    if speed:
        command.extend(["--speed", speed])

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
        raise CcusageError("ccusage timed out while reading Codex usage") from exc

    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise CcusageError("ccusage returned non-JSON output") from exc

    if not isinstance(report, dict):
        raise CcusageError("ccusage returned an unexpected JSON shape")
    return report


def total_tokens_from_report(report: dict[str, Any]) -> int:
    """Extract a total token count from a ccusage Codex monthly JSON report."""
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


def collect_codex_usage(**kwargs: Any) -> CodexUsageSnapshot:
    report = load_codex_monthly_report(**kwargs)
    totals = report.get("totals") if isinstance(report.get("totals"), dict) else {}
    return CodexUsageSnapshot(
        provider="codex",
        usage_kind="subscription",
        source="ccusage codex monthly --json",
        total_tokens=total_tokens_from_report(report),
        raw_totals=totals,
    )
