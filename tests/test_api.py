from __future__ import annotations

import unittest
from typing import Any

from token_badge.api import TokenBadgeAPI, validate_usage_snapshot


class FakeStorage:
    def __init__(self) -> None:
        self.challenges: list[tuple[str, dict[str, str | None]]] = []
        self.snapshots: list[dict[str, Any]] = []

    def create_challenge(self, challenge_nonce: str, request: dict[str, str | None]) -> None:
        self.challenges.append((challenge_nonce, request))

    def store_usage_snapshot(self, snapshot: dict[str, Any]) -> str:
        self.snapshots.append(snapshot)
        return "snapshot-1"


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
        self.assertIn("only codex", response.body["error"])

    def test_validate_snapshot_rejects_nested_raw_totals(self) -> None:
        payload = valid_snapshot()
        payload["raw_totals"]["models"] = {"gpt": {"totalTokens": 100}}

        with self.assertRaisesRegex(Exception, "unknown fields"):
            validate_usage_snapshot(payload)


if __name__ == "__main__":
    unittest.main()
