from __future__ import annotations

import hashlib
import json
from typing import Any


HASH_ALGORITHM = "sha256"


def canonical_json(payload: dict[str, Any]) -> str:
    """Return stable JSON for hashing evidence payloads."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def hash_payload(payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{HASH_ALGORITHM}:{digest}"


def build_usage_evidence(
    *,
    provider: str,
    usage_kind: str,
    source: str,
    trust_level: str,
    total_tokens: int,
    challenge_nonce: str,
    collector_installation_id: str | None,
    github_login: str | None,
    raw_totals: dict[str, Any],
) -> dict[str, Any]:
    """Build the challenge-bound evidence payload that gets hashed."""
    return {
        "challenge_nonce": challenge_nonce,
        "collector_installation_id": collector_installation_id,
        "github_login": github_login,
        "provider": provider,
        "raw_totals": raw_totals,
        "source": source,
        "total_tokens": total_tokens,
        "trust_level": trust_level,
        "usage_kind": usage_kind,
    }


def evidence_summary(evidence_payload: dict[str, Any]) -> dict[str, str | None]:
    return {
        "challenge_nonce": evidence_payload["challenge_nonce"],
        "collector_installation_id": evidence_payload["collector_installation_id"],
        "hash_algorithm": HASH_ALGORITHM,
        "report_hash": hash_payload(evidence_payload),
    }

