"""
Discovery layer for the Client Pod's Brain (FR2, Section 9 steps 1-2),
built on nostr-sdk.

API COMPATIBILITY NOTE: this file targets nostr-sdk 0.45.0. Earlier work in
this project was written against an older version with a different API --
if you're comparing against old code/docs, three things changed:
  1. `client.fetch_events(filter, timeout)` -> now takes a `ReqTarget`, not
     a raw `Filter`: `client.fetch_events(ReqTarget.auto([filter]), timeout)`
  2. `fetch_events(...)` now returns a plain Python `list[Event]` directly
     -- no more `.to_vec()` needed.
  3. `EventBuilder.sign_with_keys(keys)` is gone -- use `.finalize(keys)`
     instead (works the same way, `Keys` is accepted directly as a signer).
`requirements.txt` pins the exact version this was tested against so this
doesn't silently break again on a future `pip install`.

IMPORTANT UPDATE (unrelated to the above): NIP-90 (Data Vending Machines --
the job-request/job-feedback kinds below) is now marked "unrecommended" in
the official NIP index: "this got totally out of control, prefer
use-case-specific microstandards." In practice there is very little live
DVM traffic on public relays -- don't expect `publish_job_request`/
`listen_for_job_responses` below to find real service providers. They're
left in for reference/local testing, but `find_by_hashtag` is the function
actually worth using against real relays: hashtag search (NIP-12's #t
filter) is basic, widely implemented, and has real live traffic, unlike
NIP-90 job kinds.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta

from nostr_sdk import Client, Event, EventBuilder, Filter, Keys, Kind, PublicKey, ReqTarget, Tag

KIND_SERVICE_LISTING = 31990   # NIP-89 handler recommendation / parameterized replaceable
KIND_JOB_REQUEST = 5202        # NIP-90 (unrecommended) DVM-style job request
KIND_JOB_FEEDBACK = 7000       # NIP-90 (unrecommended) job feedback / status


@dataclass
class TaggedEvent:
    author_pubkey: str
    kind: int
    tags: list[str]
    content: str
    event_id: str
    created_at: int


def normalize_tag(tag: str) -> str:
    return tag.strip().lower().replace("_", "-").replace(" ", "-")


async def find_by_hashtag(client: Client, tag: str, kinds: list[int] | None = None,
                           limit: int = 50, timeout_secs: int = 8) -> list[TaggedEvent]:
    """Find events tagged with a given hashtag (NIP-12 '#t' filter) -- the
    realistic way to discover 'service providers' or anyone self-tagging
    with a capability/topic on real public relays. If `kinds` is omitted,
    searches across all kinds (useful for a first exploratory query)."""
    tag = normalize_tag(tag)
    f = Filter().hashtag(tag).limit(limit)
    if kinds:
        f = f.kinds([Kind(k) for k in kinds])

    events = await client.fetch_events(ReqTarget.auto([f]), timedelta(seconds=timeout_secs))

    results = []
    for ev in events:
        all_tags = [t.to_vec() for t in ev.tags()]
        results.append(TaggedEvent(
            author_pubkey=ev.author().to_hex(),
            kind=ev.kind().as_u16(),
            tags=all_tags,
            content=ev.content(),
            event_id=ev.id().to_hex(),
            created_at=ev.created_at().as_secs(),
        ))
    return results


async def query_service_listings(client: Client, capability_tag: str,
                                  limit: int = 50, timeout_secs: int = 8) -> list[Event]:
    """PULL discovery via NIP-89 handler listings (kind 31990). Left for
    reference -- expect very few/no real results, see module docstring.
    Also note: real kind:31990 events are filtered by a 'k' tag (the event
    kind they handle), not a 't' hashtag like this -- see the kind:31990
    discussion elsewhere in the project docs for the correct filter."""
    f = Filter().kind(Kind(KIND_SERVICE_LISTING)).hashtag(capability_tag).limit(limit)
    events = await client.fetch_events(ReqTarget.auto([f]), timedelta(seconds=timeout_secs))
    return list(events)


async def publish_job_request(client: Client, requester_keys: Keys,
                               capability_tag: str, params: dict) -> Event:
    """PUSH discovery: broadcast a job request (kind 5202) and let interested
    merchants respond."""
    content = json.dumps(params, separators=(",", ":"))
    event = (
        EventBuilder(Kind(KIND_JOB_REQUEST), content)
        .tags([Tag.hashtag(capability_tag)])
        .finalize(requester_keys)
    )
    await client.send_event(event)
    return event


async def listen_for_job_responses(client: Client, job_event_id, timeout_secs: int = 10) -> list[Event]:
    """Fetch kind:7000 feedback events that reference our job request via an
    'e' tag."""
    f = Filter().kind(Kind(KIND_JOB_FEEDBACK)).event(job_event_id).limit(50)
    events = await client.fetch_events(ReqTarget.auto([f]), timedelta(seconds=timeout_secs))
    return list(events)


async def fetch_profile(client: Client, pubkey: PublicKey, timeout_secs: int = 5) -> dict | None:
    """Fetch kind:0 profile metadata for a given author public key."""
    try:
        f = Filter().kind(Kind(0)).author(pubkey).limit(1)
        events = await client.fetch_events(ReqTarget.auto([f]), timedelta(seconds=timeout_secs))
        if not events:
            return None
        data = json.loads(events[0].content())
        return data if isinstance(data, dict) else None
    except Exception:
        return None


async def fetch_existing_profile(client: Client, pubkey_hex: str, timeout_secs: int = 5) -> Event | None:
    """Fetch the latest kind:0 profile for an agent."""
    events = await client.fetch_events(
        ReqTarget.auto([Filter().kind(Kind(0)).author(PublicKey.parse(pubkey_hex)).limit(1)]),
        timedelta(seconds=timeout_secs),
    )
    return events[0] if events else None


async def fetch_existing_listing(client: Client, pubkey_hex: str, timeout_secs: int = 5) -> Event | None:
    """Fetch the latest service listing published by an agent."""
    events = await client.fetch_events(
        ReqTarget.auto([
            Filter().kind(Kind(KIND_SERVICE_LISTING)).author(PublicKey.parse(pubkey_hex)).limit(1)
        ]),
        timedelta(seconds=timeout_secs),
    )
    return events[0] if events else None

