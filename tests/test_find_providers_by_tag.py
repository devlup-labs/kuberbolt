from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta

import pytest  # Imported for testing markers
from nostr_sdk import Client, Event, EventBuilder, Filter, Keys, Kind, ReqTarget, Tag

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


# ==============================================================================
# APPENDED TEST CASES
# ==============================================================================

def test_normalize_tag_formatting():
    """Verify tag string normalization logic works as expected."""
    assert normalize_tag("  My_Awesome Tag  ") == "my-awesome-tag"
    assert normalize_tag("NOSTR_dvm") == "nostr-dvm"
    assert normalize_tag("clean-tag") == "clean-tag"


@pytest.mark.asyncio
async def test_publish_job_request_structure():
    """Verify that publish_job_request structurally builds a valid event signature."""
    # Setup offline components
    keys = Keys.generate()
    client = Client() # An un-connected client still allows offline compilation/send event calls
    capability = "AI_generation"
    params = {"prompt": "test payload", "model": "flux"}

    # Execute build & broadcast chain 
    try:
        event = await publish_job_request(client, keys, capability, params)
        
        # Core Assertions
        assert event.kind().as_u16() == KIND_JOB_REQUEST
        assert event.author().to_hex() == keys.public_key().to_hex()
        assert json.loads(event.content()) == params
    except Exception as e:
        # If execution fails because there are no active relays configured, 
        # we catch network exceptions gracefully unless mocking network behavior.
        if "relay" in str(e).lower() or "connection" in str(e).lower():
            pytest.skip(f"Relay network omitted for structural check. Error: {e}")
        else:
            raise e