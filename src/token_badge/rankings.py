from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


# While fewer than this many distinct profiles have uploaded usage, we celebrate
# early adopters instead of publishing a percentile that would swing wildly with
# every new upload.
FIRST_USERS_THRESHOLD = 100


@dataclass(frozen=True)
class ConsumptionRanking:
    total_tokens: int
    total_users: int
    users_beaten: int
    is_early_adopter: bool
    percentile: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_tokens": self.total_tokens,
            "total_users": self.total_users,
            "users_beaten": self.users_beaten,
            "is_early_adopter": self.is_early_adopter,
            "percentile": self.percentile,
        }


def compute_ranking(
    user_totals: Mapping[str, int],
    identity_key: str | None,
    *,
    threshold: int = FIRST_USERS_THRESHOLD,
) -> ConsumptionRanking:
    """Rank one profile's consumption against every other uploader.

    ``user_totals`` maps each profile's identity key to its highest accepted
    total. The percentile reports the share of *other* adopters this profile has
    out-consumed; it stays ``None`` until enough profiles have uploaded.
    """
    total_users = len(user_totals)
    user_total = user_totals.get(identity_key, 0) if identity_key is not None else 0
    others = [total for key, total in user_totals.items() if key != identity_key]
    users_beaten = sum(1 for total in others if total < user_total)

    is_early_adopter = total_users <= threshold
    if is_early_adopter or not others:
        percentile = None
    else:
        percentile = round(users_beaten / len(others) * 100, 1)

    return ConsumptionRanking(
        total_tokens=user_total,
        total_users=total_users,
        users_beaten=users_beaten,
        is_early_adopter=is_early_adopter,
        percentile=percentile,
    )


def ranking_message(ranking: ConsumptionRanking, *, threshold: int = FIRST_USERS_THRESHOLD) -> str:
    """Render the celebratory or percentile line shown to the user."""
    if ranking.is_early_adopter:
        return (
            f"You're one of the first {threshold} AI adopters to upload — yay! "
            "Check back later for your percentile."
        )
    if ranking.percentile is None:
        return "Not enough peers have uploaded yet to compute your percentile."
    return f"Your consumption has beat {ranking.percentile:g}% of other AI adopters."
