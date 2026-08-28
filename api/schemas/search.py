"""Pydantic models for the agent search-by-tag endpoint."""

from __future__ import annotations

from pydantic import BaseModel


class SearchProviderItem(BaseModel):
    """A single provider/event returned by a hashtag search."""
    author_pubkey: str
    kind: int
    tags: list[list[str]]
    content: str
    event_id: str
    created_at: int


class SearchProvidersResponse(BaseModel):
    """Wrapper returned by GET /api/agents/search."""
    tag: str
    count: int
    items: list[SearchProviderItem]
