from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any

from token_badge.tiers import BadgeTier, earned_tier, next_tier


TIER_COLORS = {
    "Hot AI Prospect": "#2da44e",
    "Wonder AI Kid": "#0969da",
    "Key AI Player": "#8250df",
    "World-Class AI Player": "#bf8700",
}


@dataclass(frozen=True)
class BadgeGrant:
    identity_key: str
    github_login: str | None
    github_node_id: str | None
    tier: BadgeTier
    winning_provider: str
    winning_snapshot_id: str
    winning_total_tokens: int
    trust_level: str

    def to_record(self) -> dict[str, Any]:
        return {
            "identity_key": self.identity_key,
            "github_login": self.github_login,
            "github_node_id": self.github_node_id,
            "tier_name": self.tier.name,
            "tier_threshold": self.tier.threshold,
            "winning_provider": self.winning_provider,
            "winning_snapshot_id": self.winning_snapshot_id,
            "winning_total_tokens": self.winning_total_tokens,
            "trust_level": self.trust_level,
        }


def github_identity_key(github_login: str | None, github_node_id: str | None = None) -> str | None:
    if github_login:
        return f"github_login:{github_login.lower()}"
    if github_node_id:
        return f"github_node_id:{github_node_id}"
    return None


def badge_grant_from_snapshot(snapshot: dict[str, Any], snapshot_id: str) -> BadgeGrant | None:
    total_tokens = snapshot["total_tokens"]
    tier = earned_tier(total_tokens)
    identity_key = github_identity_key(snapshot.get("github_login"), snapshot.get("github_node_id"))
    if tier is None or identity_key is None:
        return None

    return BadgeGrant(
        identity_key=identity_key,
        github_login=snapshot.get("github_login"),
        github_node_id=snapshot.get("github_node_id"),
        tier=tier,
        winning_provider=snapshot["provider"],
        winning_snapshot_id=snapshot_id,
        winning_total_tokens=total_tokens,
        trust_level=snapshot["trust_level"],
    )


def should_replace_badge_grant(existing_total_tokens: int | None, candidate_total_tokens: int) -> bool:
    return existing_total_tokens is None or candidate_total_tokens > existing_total_tokens


def badge_summary_from_record(record: dict[str, Any] | None) -> dict[str, Any]:
    if record is None:
        return {
            "earned": False,
            "tier": None,
            "winning_provider": None,
            "winning_total_tokens": 0,
            "next": {
                "name": next_tier(0).name,
                "threshold": next_tier(0).threshold,
                "tokens_remaining": next_tier(0).threshold,
            },
        }

    total_tokens = int(record["winning_total_tokens"])
    upcoming = next_tier(total_tokens)
    return {
        "earned": True,
        "github_login": record.get("github_login"),
        "github_node_id": record.get("github_node_id"),
        "tier": {
            "name": record["tier_name"],
            "threshold": int(record["tier_threshold"]),
        },
        "winning_provider": record["winning_provider"],
        "winning_snapshot_id": record["winning_snapshot_id"],
        "winning_total_tokens": total_tokens,
        "trust_level": record["trust_level"],
        "next": None
        if upcoming is None
        else {
            "name": upcoming.name,
            "threshold": upcoming.threshold,
            "tokens_remaining": upcoming.threshold - total_tokens,
        },
    }


def render_badge_svg(summary: dict[str, Any]) -> str:
    label = "Token Badge"
    if summary.get("earned"):
        message = summary["tier"]["name"]
        color = TIER_COLORS.get(message, "#0969da")
    else:
        message = "No Badge Yet"
        color = "#6e7781"

    label_width = max(84, len(label) * 7 + 14)
    message_width = max(96, len(message) * 7 + 18)
    width = label_width + message_width
    label_text_x = label_width / 2
    message_text_x = label_width + message_width / 2
    escaped_label = html.escape(label)
    escaped_message = html.escape(message)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="28" role="img" aria-label="{escaped_label}: {escaped_message}">
  <title>{escaped_label}: {escaped_message}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#fff" stop-opacity=".18"/>
    <stop offset="1" stop-color="#000" stop-opacity=".08"/>
  </linearGradient>
  <clipPath id="r"><rect width="{width}" height="28" rx="6"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="28" fill="#24292f"/>
    <rect x="{label_width}" width="{message_width}" height="28" fill="{color}"/>
    <rect width="{width}" height="28" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" font-size="12" font-weight="600">
    <text x="{label_text_x}" y="18">{escaped_label}</text>
    <text x="{message_text_x}" y="18">{escaped_message}</text>
  </g>
</svg>
"""
