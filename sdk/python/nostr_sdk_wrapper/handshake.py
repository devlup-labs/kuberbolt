"""
Discovery + encrypted handshake, on nostr-sdk (rust-nostr), NIP-44 only --
no NIP-59 gift wrap.

API COMPATIBILITY NOTE: targets nostr-sdk 0.45.0. See discovery.py's
module docstring for the specific API changes from earlier versions
(`.sign_with_keys()` -> `.finalize()`, `fetch_events` signature/return type).

Difference from gift-wrapped DMs (NIP-17-style): the event's `pubkey` field
is the real sender's key, signed directly with their real private key. Only
`.content` is encrypted (via NIP-44 v2). This means:

  - Relays and observers CAN see who is talking to whom (sender pubkey is
    the event's real author; recipient is visible via the 'p' tag).
  - They CANNOT see what was said -- NIP-44 encrypts the content.
  - Simpler than gift wrap: one signed event per message, not three
    (rumor + seal + wrap).

This trades away gift wrap's sender/recipient metadata privacy for
simplicity. If you later need to also hide *who* is talking to whom,
NIP-59 gift wrap is what provides that -- it can be layered back on top of
this later without changing the NIP-44 payload format.
"""

from __future__ import annotations

import json
from datetime import timedelta

from nostr_sdk import (
    Client,
    Event,
    EventBuilder,
    Filter,
    Keys,
    Kind,
    Nip44Version,
    PublicKey,
    ReqTarget,
    Tag,
    nip44_decrypt,
    nip44_encrypt,
)

# App-specific kind for handshake request/response messages. Pick a value
# that doesn't collide with your other custom kinds / reserved NIP ranges.
KIND_HANDSHAKE = 21000


def build_encrypted_event(sender_keys: Keys, recipient_pubkey: PublicKey, payload: dict) -> Event:
    """Build and sign a NIP-44-encrypted handshake event. Does not send it --
    see `send_encrypted_request` for that."""
    plaintext = json.dumps(payload, separators=(",", ":"))
    ciphertext = nip44_encrypt(sender_keys.secret_key(), recipient_pubkey, plaintext, Nip44Version.V2)
    return (
        EventBuilder(Kind(KIND_HANDSHAKE), ciphertext)
        .tags([Tag.public_key(recipient_pubkey)])
        .finalize(sender_keys)
    )


async def send_encrypted_request(client: Client, sender_keys: Keys,
                                  recipient_pubkey: PublicKey, payload: dict) -> Event:
    """Build, sign, and publish a NIP-44-encrypted event to `recipient_pubkey`."""
    event = build_encrypted_event(sender_keys, recipient_pubkey, payload)
    await client.send_event(event)
    return event


def decrypt_event(recipient_keys: Keys, event: Event) -> dict:
    """Decrypt a received handshake event's content back into the original
    payload dict. Verifies the event's signature first -- an unverified
    event's claimed author can't be trusted."""
    if not event.verify():
        raise ValueError("event signature invalid")
    plaintext = nip44_decrypt(recipient_keys.secret_key(), event.author(), event.content())
    return json.loads(plaintext)


async def fetch_handshake_events(client: Client, recipient_pubkey: PublicKey,
                                  timeout_secs: int = 10) -> list[Event]:
    """Fetch events addressed to `recipient_pubkey` (via a 'p' tag) of our
    handshake kind. Call `decrypt_event(my_keys, ev)` on each result."""
    f = Filter().kind(Kind(KIND_HANDSHAKE)).pubkey(recipient_pubkey)
    events = await client.fetch_events(ReqTarget.auto([f]), timedelta(seconds=timeout_secs))
    return list(events)
