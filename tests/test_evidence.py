from __future__ import annotations

import unittest

from token_badge.evidence import (
    build_usage_evidence,
    canonical_json,
    evidence_summary,
    hash_payload,
)


class EvidenceTest(unittest.TestCase):
    def test_canonical_json_is_stable_and_compact(self) -> None:
        payload = {"z": 1, "a": {"b": 2}}

        self.assertEqual(canonical_json(payload), '{"a":{"b":2},"z":1}')

    def test_hash_is_stable_for_equivalent_payloads(self) -> None:
        left = {"provider": "codex", "raw_totals": {"totalTokens": 100}, "challenge_nonce": "abc"}
        right = {"challenge_nonce": "abc", "raw_totals": {"totalTokens": 100}, "provider": "codex"}

        self.assertEqual(hash_payload(left), hash_payload(right))

    def test_hash_changes_when_challenge_changes(self) -> None:
        base = build_usage_evidence(
            provider="codex",
            usage_kind="subscription",
            source="ccusage codex monthly --json",
            trust_level="local-self-reported",
            total_tokens=100,
            challenge_nonce="challenge-a",
            collector_installation_id="collector-1",
            github_login="octocat",
            raw_totals={"totalTokens": 100},
        )
        changed = dict(base)
        changed["challenge_nonce"] = "challenge-b"

        self.assertNotEqual(hash_payload(base), hash_payload(changed))

    def test_evidence_summary_exposes_hash_metadata(self) -> None:
        payload = build_usage_evidence(
            provider="codex",
            usage_kind="subscription",
            source="ccusage codex monthly --json",
            trust_level="local-self-reported",
            total_tokens=100,
            challenge_nonce="challenge-a",
            collector_installation_id="collector-1",
            github_login="octocat",
            raw_totals={"totalTokens": 100},
        )

        summary = evidence_summary(payload)

        self.assertEqual(summary["challenge_nonce"], "challenge-a")
        self.assertEqual(summary["collector_installation_id"], "collector-1")
        self.assertEqual(summary["hash_algorithm"], "sha256")
        self.assertTrue(summary["report_hash"].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()

