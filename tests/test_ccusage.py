from __future__ import annotations

import unittest
from subprocess import CompletedProcess
from unittest.mock import patch

from token_badge.ccusage import CcusageError, collect_provider_usage, load_provider_monthly_report, total_tokens_from_report


class CcusageParsingTest(unittest.TestCase):
    def test_prefers_report_totals(self) -> None:
        report = {
            "monthly": [{"totalTokens": 1}],
            "totals": {"totalTokens": 123},
        }

        self.assertEqual(total_tokens_from_report(report), 123)

    def test_falls_back_to_monthly_sum(self) -> None:
        report = {
            "monthly": [
                {"totalTokens": 100},
                {"totalTokens": 250},
            ]
        }

        self.assertEqual(total_tokens_from_report(report), 350)

    def test_rejects_missing_total(self) -> None:
        with self.assertRaises(CcusageError):
            total_tokens_from_report({"monthly": [{"inputTokens": 100}]})

    def test_collects_claude_totals_from_ccusage_shape(self) -> None:
        report = {
            "monthly": [{"totalTokens": 1}],
            "totals": {
                "cacheCreationTokens": 10,
                "cacheReadTokens": 20,
                "inputTokens": 30,
                "outputTokens": 40,
                "totalCost": 1.23,
                "totalTokens": 100,
            },
        }
        completed = CompletedProcess(
            args=["ccusage", "claude", "monthly", "--json"],
            returncode=0,
            stdout='{"monthly":[{"totalTokens":1}],"totals":{"cacheCreationTokens":10,"cacheReadTokens":20,"inputTokens":30,"outputTokens":40,"totalCost":1.23,"totalTokens":100}}',
        )

        with patch("token_badge.ccusage.shutil.which", return_value="/usr/local/bin/ccusage"):
            with patch("token_badge.ccusage.subprocess.run", return_value=completed) as run:
                snapshot = collect_provider_usage("claude")

        self.assertEqual(snapshot.provider, "claude")
        self.assertEqual(snapshot.source, "ccusage claude monthly --json")
        self.assertEqual(snapshot.total_tokens, 100)
        self.assertEqual(snapshot.raw_totals, report["totals"])
        self.assertEqual(run.call_args.args[0], ["ccusage", "claude", "monthly", "--json"])

    def test_rejects_speed_for_claude_usage(self) -> None:
        with patch("token_badge.ccusage.shutil.which", return_value="/usr/local/bin/ccusage"):
            with self.assertRaisesRegex(CcusageError, "does not support --speed"):
                load_provider_monthly_report("claude", speed="fast")


if __name__ == "__main__":
    unittest.main()
