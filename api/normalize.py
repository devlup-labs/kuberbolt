"""
Shared text-normalisation helpers for the Kuberbolt API.
"""

from __future__ import annotations


def normalize_tag(tag: str) -> str:
    """Normalise a capability / hashtag string for relay queries.

    Mirrors the convention used across the codebase:
    strip whitespace, lower-case, replace underscores and spaces with hyphens.
    """
    return tag.strip().lower().replace("_", "-").replace(" ", "-")
