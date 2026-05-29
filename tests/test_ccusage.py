from __future__ import annotations

import unittest

from token_badge.ccusage import CcusageError, total_tokens_from_report


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


if __name__ == "__main__":
    unittest.main()

