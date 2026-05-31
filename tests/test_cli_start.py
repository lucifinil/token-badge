from __future__ import annotations

import argparse
import contextlib
import unittest
from unittest import mock

from token_badge import cli
from token_badge.ccusage import UsageSnapshot


def start_args(**overrides: object) -> argparse.Namespace:
    base = {
        "provider": "claude",
        "github": "octocat",
        "github_node_id": None,
        "subject": None,
        "collector_id": "collector-1",
        "upload_url": "https://token-badge.example.com",
        "since": None,
        "until": None,
        "timezone": None,
        "speed": None,
        "badge_base_url": None,
        "profile_badge_message": "Add Token Badge profile badge",
        "json": False,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


class FakeProfileClient:
    instances: list["FakeProfileClient"] = []

    def __init__(self) -> None:
        self.installed = False
        FakeProfileClient.instances.append(self)

    def install_badge(self, **kwargs: object):
        self.installed = True
        return mock.Mock(changed=True, repository="octocat/octocat", repo_created=False)


class StartFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeProfileClient.instances = []
        self.snapshot = UsageSnapshot(
            provider="claude",
            usage_kind="subscription",
            source="ccusage claude monthly --json",
            total_tokens=150_000_000,
            raw_totals={"totalTokens": 150_000_000},
        )
        self.ranking = {
            "total_tokens": 150_000_000,
            "total_users": 250,
            "users_beaten": 200,
            "is_early_adopter": False,
            "percentile": 80.0,
            "message": "Your consumption has beat 80% of other AI adopters.",
            "github_login": "octocat",
        }

    @contextlib.contextmanager
    def _patched_collaborators(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(cli, "GitHubProfileClient", FakeProfileClient))
            stack.enter_context(mock.patch.object(cli, "request_challenge", return_value={"challenge_nonce": "nonce-1"}))
            stack.enter_context(mock.patch.object(cli, "collect_provider_usage", return_value=self.snapshot))
            stack.enter_context(
                mock.patch.object(cli, "upload_usage_snapshot", return_value={"snapshot_id": "s1", "status": "accepted"})
            )
            stack.enter_context(mock.patch.object(cli, "fetch_ranking", return_value=self.ranking))
            yield

    def test_start_installs_badge_when_user_confirms(self) -> None:
        with self._patched_collaborators():
            code = cli.run_start(start_args(), confirm=lambda _question: True)

        self.assertEqual(code, 0)
        self.assertTrue(FakeProfileClient.instances[0].installed)

    def test_start_skips_badge_when_user_declines(self) -> None:
        with self._patched_collaborators():
            code = cli.run_start(start_args(), confirm=lambda _question: False)

        self.assertEqual(code, 0)
        self.assertFalse(FakeProfileClient.instances[0].installed)


if __name__ == "__main__":
    unittest.main()
