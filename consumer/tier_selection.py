"""Tier-picking helpers used by the consumer graph's pick_tier_node.

These are pure functions so they can be unit-tested without an LLM.
"""
from __future__ import annotations

import re

_TIER_WORD_TO_RANK = {
    "small": 0, "cheapest": 0, "basic": 0, "minimum": 0,
    "medium": 1, "standard": 1, "mid": 1,
    "large": 2, "fast": 2, "biggest": 2, "premium": 2,
}


def rank_catalog(catalog: list[dict]) -> list[dict]:
    """Return the catalog sorted by mbps ascending (smallest tier first)."""
    return sorted(catalog, key=lambda p: p["mbps"])


def deterministic_tier_pick(user_message: str, catalog: list[dict]) -> dict:
    """Rule-based fallback when the LLM output is not a recognizable tier word.

    1. "X Mbps" → smallest tier with mbps ≥ X (else largest).
    2. tier word match.
    3. middle tier.
    """
    ranked = rank_catalog(catalog)
    msg = user_message.lower()

    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:mbps|mbit|m)\b", msg)
    if m:
        want = float(m.group(1))
        candidates = [p for p in ranked if p["mbps"] >= want]
        return candidates[0] if candidates else ranked[-1]

    for word, rank in _TIER_WORD_TO_RANK.items():
        if word in msg:
            return ranked[min(rank, len(ranked) - 1)]

    return ranked[len(ranked) // 2]
