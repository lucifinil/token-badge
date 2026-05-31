from __future__ import annotations

import unittest
from typing import Any

from token_badge.api import TokenBadgeAPI, validate_usage_snapshot
from token_badge.badges import badge_grant_from_snapshot, should_replace_badge_grant


class FakeStorage:
    def __init__(self) -> None:
        self.challenges: list[tuple[str, dict[str, str | None]]] = []
        self.snapshots: list[dict[str, Any]] = []
        self.grants: dict[str, dict[str, Any]] = {}

    def create_challenge(self, challenge_nonce: str, request: dict[str, str | None]) -> None:
        self.challenges.append((challenge_nonce, request))

    def store_usage_snapshot(self, snapshot: dict[str, Any]) -> str:
        snapshot_id = f"snapshot-{len(self.snapshots) + 1}"
        self.snapshots.append(snapshot)
        grant = badge_grant_from_snapshot(snapshot, snapshot_id)
        if grant is not None:
            current = self.grants.get(grant.identity_key)
            current_total = None if current is None else current["winning_total_tokens"]
            if should_replace_badge_grant(current_total, grant.winning_total_tokens):
                self.grants[grant.identity_key] = grant.to_record()
        return snapshot_id

    def get_badge_grant(self, github_login: str) -> dict[str, Any] | None:
        return self.grants.get(f"github_login:{github_login.lower()}")


class FailingStorage(FakeStorage):
    def store_usage_snapshot(self, snapshot: dict[str, Any]) -> str:
        raise RuntimeError("database unavailable")


def valid_snapshot() -> dict[str, Any]:
    return {
        "challenge_nonce": "nonce-1",
        "collector_installation_id": "collector-1",
        "github_login": "octocat",
        "github_node_id": "U_123",
        "provider": "codex",
        "raw_totals": {
            "cachedInputTokens": 10,
            "inputTokens": 20,
            "outputTokens": 30,
            "reasoningOutputTokens": 40,
            "totalTokens": 100,
        },
        "report_hash": "sha256:" + "a" * 64,
        "source": "ccusage codex monthly --json",
        "total_tokens": 100,
        "trust_level": "local-self-reported",
        "usage_kind": "subscription",
    }


class APITest(unittest.TestCase):
    def test_challenge_endpoint_stores_clean_identifier_metadata(self) -> None:
        storage = FakeStorage()
        api = TokenBadgeAPI(storage)

        response = api.handle(
            "POST",
            "/v1/challenges",
            {
                "collector_installation_id": "collector-1",
                "github_login": "octocat",
                "github_node_id": "U_123",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(storage.challenges[0][1]["collector_installation_id"], "collector-1")
        self.assertIn("challenge_nonce", response.body)

    def test_snapshot_endpoint_rejects_full_report_fields(self) -> None:
        payload = valid_snapshot()
        payload["monthly"] = [{"totalTokens": 100}]

        response = TokenBadgeAPI(FakeStorage()).handle("POST", "/v1/usage-snapshots", payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("unknown fields", response.body["error"])

    def test_snapshot_endpoint_stores_minimal_metadata_only(self) -> None:
        storage = FakeStorage()
        response = TokenBadgeAPI(storage).handle("POST", "/v1/usage-snapshots", valid_snapshot())

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.body["snapshot_id"], "snapshot-1")
        self.assertEqual(storage.snapshots[0]["raw_totals"]["totalTokens"], 100)
        self.assertNotIn("monthly", storage.snapshots[0])

    def test_snapshot_endpoint_returns_json_when_storage_fails(self) -> None:
        response = TokenBadgeAPI(FailingStorage()).handle("POST", "/v1/usage-snapshots", valid_snapshot())

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.body["error"], "storage_unavailable")

    def test_snapshot_validation_rejects_future_provider_until_adapter_exists(self) -> None:
        payload = valid_snapshot()
        payload["provider"] = "gemini"

        response = TokenBadgeAPI(FakeStorage()).handle("POST", "/v1/usage-snapshots", payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("unsupported provider", response.body["error"])

    def test_snapshot_endpoint_accepts_claude_minimal_totals(self) -> None:
        payload = valid_snapshot()
        payload["provider"] = "claude"
        payload["source"] = "ccusage claude monthly --json"
        payload["raw_totals"] = {
            "cacheCreationTokens": 10,
            "cacheReadTokens": 20,
            "inputTokens": 30,
            "outputTokens": 40,
            "totalCost": 1.23,
            "totalTokens": 100,
        }

        response = TokenBadgeAPI(FakeStorage()).handle("POST", "/v1/usage-snapshots", payload)

        self.assertEqual(response.status_code, 201)

    def test_badge_endpoint_uses_highest_provider_for_same_github_user(self) -> None:
        storage = FakeStorage()
        api = TokenBadgeAPI(storage)
        codex = valid_snapshot()
        codex["total_tokens"] = 1_200_000_000
        codex["raw_totals"]["totalTokens"] = 1_200_000_000
        claude = valid_snapshot()
        claude["provider"] = "claude"
        claude["source"] = "ccusage claude monthly --json"
        claude["total_tokens"] = 164_000_000
        claude["raw_totals"] = {
            "cacheCreationTokens": 1,
            "cacheReadTokens": 2,
            "inputTokens": 3,
            "outputTokens": 4,
            "totalCost": 5.0,
            "totalTokens": 164_000_000,
        }

        self.assertEqual(api.handle("POST", "/v1/usage-snapshots", codex).status_code, 201)
        self.assertEqual(api.handle("POST", "/v1/usage-snapshots", claude).status_code, 201)
        response = api.handle("GET", "/v1/badges/octocat")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body["tier"]["name"], "Wonder AI Kid")
        self.assertEqual(response.body["winning_provider"], "codex")
        self.assertEqual(response.body["winning_total_tokens"], 1_200_000_000)

    def test_badge_endpoint_returns_svg(self) -> None:
        storage = FakeStorage()
        api = TokenBadgeAPI(storage)
        snapshot = valid_snapshot()
        snapshot["total_tokens"] = 1_200_000_000
        snapshot["raw_totals"]["totalTokens"] = 1_200_000_000

        api.handle("POST", "/v1/usage-snapshots", snapshot)
        response = api.handle("GET", "/v1/badges/octocat.svg")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "image/svg+xml")
        self.assertIn("Wonder AI Kid", response.body)

    def test_validate_snapshot_rejects_nested_raw_totals(self) -> None:
        payload = valid_snapshot()
        payload["raw_totals"]["models"] = {"gpt": {"totalTokens": 100}}

        with self.assertRaisesRegex(Exception, "unknown fields"):
            validate_usage_snapshot(payload)


if __name__ == "__main__":
    unittest.main()
