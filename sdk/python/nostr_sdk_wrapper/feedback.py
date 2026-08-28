"""Nostr feedback event publishing."""

from __future__ import annotations

import json

from nostr_sdk import Client, Event, EventBuilder, Keys, Kind, PublicKey, Tag


KIND_FEEDBACK = 7000


async def publish_feedback(
	client: Client,
	reviewer_keys: Keys,
	counterparty_pubkey: PublicKey,
	job_id: str,
	feedback_text: str,
	rating: int,
) -> Event:
	"""Publish feedback for a completed job as a kind:7000 event."""
	content = json.dumps(
		{
			"job_id": job_id,
			"feedback": feedback_text,
			"rating": rating,
		},
		separators=(",", ":"),
	)
	event = (
		EventBuilder(Kind(KIND_FEEDBACK), content)
		.tags([
			Tag.event(job_id),
			Tag.public_key(counterparty_pubkey),
		])
		.finalize(reviewer_keys)
	)
	await client.send_event(event)
	return event
