from __future__ import annotations

import unittest

from token_badge.badges import (
    badge_grant_from_snapshot,
    github_identity_key,
    render_badge_svg,
    should_replace_badge_grant,
)


def snapshot(total_tokens: int, provider: str = "codex") -> dict[str, object]:
    return {
        "github_login": "OctoCat",
        "github_node_id": "U_123",
        "provider": provider,
        "total_tokens": total_tokens,
        "trust_level": "local-self-reported",
    }


class BadgeGrantTest(unittest.TestCase):
    def test_github_login_is_profile_identity_key(self) -> None:
        self.assertEqual(github_identity_key("OctoCat", "U_123"), "github_login:octocat")

    def test_snapshot_below_first_tier_does_not_create_grant(self) -> None:
        self.assertIsNone(badge_grant_from_snapshot(snapshot(99_999_999), "snapshot-1"))

    def test_snapshot_at_tier_creates_grant(self) -> None:
        grant = badge_grant_from_snapshot(snapshot(500_000_000, "claude"), "snapshot-1")

        self.assertEqual(grant.tier.name, "Wonder AI Kid")
        self.assertEqual(grant.winning_provider, "claude")

    def test_highest_provider_total_wins(self) -> None:
        self.assertTrue(should_replace_badge_grant(164_000_000, 1_200_000_000))
        self.assertFalse(should_replace_badge_grant(1_200_000_000, 164_000_000))

    def test_svg_renders_current_tier(self) -> None:
        svg = render_badge_svg(
            {
                "earned": True,
                "tier": {"name": "Key AI Player", "threshold": 1_000_000_000},
            }
        )

        self.assertIn("<svg", svg)
        self.assertIn("Key AI Player", svg)


if __name__ == "__main__":
    unittest.main()
