from __future__ import annotations

import unittest

from token_badge.tiers import earned_tier, next_tier


class BadgeTierTest(unittest.TestCase):
    def test_no_badge_below_first_threshold(self) -> None:
        self.assertIsNone(earned_tier(99_999_999))
        self.assertEqual(next_tier(99_999_999).name, "Wonder Kid")

    def test_awards_threshold_exactly(self) -> None:
        self.assertEqual(earned_tier(100_000_000).name, "Wonder Kid")

    def test_uses_highest_earned_tier(self) -> None:
        self.assertEqual(earned_tier(12_000_000_000).name, "AI Power User")
        self.assertEqual(next_tier(12_000_000_000).name, "Context Titan")

    def test_no_next_tier_after_top_badge(self) -> None:
        self.assertEqual(earned_tier(100_000_000_000).name, "Context Titan")
        self.assertIsNone(next_tier(100_000_000_000))


if __name__ == "__main__":
    unittest.main()

