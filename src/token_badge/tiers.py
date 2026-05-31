from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class BadgeTier:
    threshold: int
    name: str
    description: str


DEFAULT_TIERS: tuple[BadgeTier, ...] = (
    BadgeTier(
        threshold=100_000_000,
        name="Hot AI Prospect",
        description="Crossed the first 100 million subscription-agent tokens.",
    ),
    BadgeTier(
        threshold=500_000_000,
        name="Wonder AI Kid",
        description="Reached half a billion subscription-agent tokens.",
    ),
    BadgeTier(
        threshold=1_000_000_000,
        name="Key AI Player",
        description="Reached one billion subscription-agent tokens.",
    ),
    BadgeTier(
        threshold=10_000_000_000,
        name="World-Class AI Player",
        description="Reached ten billion subscription-agent tokens.",
    ),
)


def earned_tier(total_tokens: int, tiers: tuple[BadgeTier, ...] = DEFAULT_TIERS) -> BadgeTier | None:
    """Return the highest tier earned by a total token count."""
    earned = [tier for tier in tiers if total_tokens >= tier.threshold]
    return earned[-1] if earned else None


def next_tier(total_tokens: int, tiers: tuple[BadgeTier, ...] = DEFAULT_TIERS) -> BadgeTier | None:
    """Return the next tier not yet reached."""
    for tier in tiers:
        if total_tokens < tier.threshold:
            return tier
    return None
