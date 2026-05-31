from __future__ import annotations

import unittest

from token_badge.rankings import compute_ranking, ranking_message


class RankingTest(unittest.TestCase):
    def test_early_adopter_phase_hides_percentile(self) -> None:
        totals = {f"github_login:user{i}": i * 1_000 for i in range(1, 6)}

        ranking = compute_ranking(totals, "github_login:user5", threshold=100)

        self.assertTrue(ranking.is_early_adopter)
        self.assertIsNone(ranking.percentile)
        self.assertEqual(ranking.total_users, 5)
        self.assertIn("one of the first 100", ranking_message(ranking, threshold=100))

    def test_percentile_counts_only_other_adopters(self) -> None:
        # 11 users so the early-adopter gate (threshold 10) is cleared.
        totals = {f"github_login:user{i}": i * 1_000 for i in range(1, 12)}

        # user11 has the highest total and beats the other 10 adopters.
        ranking = compute_ranking(totals, "github_login:user11", threshold=10)

        self.assertFalse(ranking.is_early_adopter)
        self.assertEqual(ranking.users_beaten, 10)
        self.assertEqual(ranking.percentile, 100.0)
        self.assertIn("beat 100% of other AI adopters", ranking_message(ranking))

    def test_percentile_for_mid_pack_user(self) -> None:
        totals = {f"github_login:user{i}": i * 1_000 for i in range(1, 12)}

        # user6 beats users 1-5 (5 of the other 10) -> 50%.
        ranking = compute_ranking(totals, "github_login:user6", threshold=10)

        self.assertEqual(ranking.users_beaten, 5)
        self.assertEqual(ranking.percentile, 50.0)

    def test_unknown_identity_has_zero_total(self) -> None:
        totals = {f"github_login:user{i}": i for i in range(1, 12)}

        ranking = compute_ranking(totals, "github_login:newcomer", threshold=10)

        self.assertEqual(ranking.total_tokens, 0)
        self.assertEqual(ranking.users_beaten, 0)
        self.assertEqual(ranking.percentile, 0.0)


if __name__ == "__main__":
    unittest.main()
