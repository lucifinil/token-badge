from __future__ import annotations

import unittest

from token_badge.api import TokenBadgeAPI
from token_badge.profile_page import render_profile_html

from tests.test_api import FakeStorage, valid_snapshot


class ProfilePageRenderTest(unittest.TestCase):
    def test_earned_page_shows_tier_total_and_message(self) -> None:
        summary = {
            "earned": True,
            "tier": {"name": "Key AI Player", "threshold": 10_000_000_000},
            "winning_provider": "codex",
            "winning_total_tokens": 1_168_789_399,
            "trust_level": "local-self-reported",
            "next": {"name": "World-Class AI Player", "threshold": 100_000_000_000, "tokens_remaining": 98_831_210_601},
        }
        ranking = {"total_tokens": 1_168_789_399, "message": "You're one of the first 100 AI adopters to upload — yay!"}

        page = render_profile_html("lucifinil", summary, ranking)

        self.assertIn("Key AI Player", page)
        self.assertIn("1,168,789,399", page)
        self.assertIn("/v1/badges/lucifinil.svg", page)
        self.assertIn("one of the first 100", page)
        self.assertIn("World-Class AI Player", page)

    def test_no_badge_page_renders_gracefully(self) -> None:
        summary = {
            "earned": False,
            "tier": None,
            "winning_total_tokens": 0,
            "next": {"name": "Hot AI Prospect", "threshold": 100_000_000, "tokens_remaining": 100_000_000},
        }
        ranking = {"total_tokens": 0, "message": "Not enough peers yet."}

        page = render_profile_html("newcomer", summary, ranking)

        self.assertIn("No badge yet", page)
        self.assertIn("Hot AI Prospect", page)

    def test_login_is_html_escaped(self) -> None:
        page = render_profile_html("a<script>", {"earned": False, "next": None}, {"total_tokens": 0, "message": ""})

        self.assertNotIn("@a<script>", page)
        self.assertIn("a&lt;script&gt;", page)


class ProfilePageEndpointTest(unittest.TestCase):
    def test_profile_endpoint_serves_html(self) -> None:
        storage = FakeStorage()
        api = TokenBadgeAPI(storage)
        snapshot = valid_snapshot()
        snapshot["total_tokens"] = 1_200_000_000
        snapshot["raw_totals"]["totalTokens"] = 1_200_000_000
        api.handle("POST", "/v1/usage-snapshots", snapshot)

        response = api.handle("GET", "/u/octocat")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content_type.startswith("text/html"))
        self.assertIn("Wonder AI Kid", response.body)
        self.assertIn("/v1/badges/octocat.svg", response.body)


if __name__ == "__main__":
    unittest.main()
