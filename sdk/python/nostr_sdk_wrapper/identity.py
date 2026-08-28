"""
Agent identity: keypair generation, persistence to disk, and kind:0 profile
publishing.

Tested against nostr-sdk 0.45.0 -- see the module-level note in
discovery.py/handshake.py about API changes from earlier versions used in
this project. In this version:
  - There's no `NostrSigner.keys(keys)` wrapper anymore -- `Keys` objects
    are accepted directly anywhere a signer is expected.
  - `EventBuilder.sign_with_keys(keys)` is gone -- use `.finalize(keys)`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from nostr_sdk import Client, Event, Keys, Metadata, MetadataRecord, SecretKey


def generate_identity() -> Keys:
    """Generate a brand-new secp256k1 keypair for an agent."""
    return Keys.generate()


def save_identity(keys: Keys, path: str | Path) -> None:
    """Persist an identity to disk as JSON. Stores the secret key in both
    hex and bech32 (nsec) form for convenience, plus the public key (hex
    and npub) so the file is human-inspectable without needing to re-derive
    anything.

    SECURITY NOTE: this file contains a real secret key in plaintext. Keep
    it out of version control (add it to .gitignore) and restrict its file
    permissions -- this function sets it to 0600 (owner read/write only)
    right after writing.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "secret_key_hex": keys.secret_key().to_hex(),
        "secret_key_bech32": keys.secret_key().to_bech32(),
        "public_key_hex": keys.public_key().to_hex(),
        "public_key_bech32": keys.public_key().to_bech32(),
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    os.chmod(path, 0o600)


def load_identity(path: str | Path) -> Keys:
    """Load a previously saved identity from disk."""
    path = Path(path)
    with open(path) as f:
        data = json.load(f)
    secret_key = SecretKey.parse(data["secret_key_hex"])
    return Keys(secret_key)


def get_or_create_identity(path: str | Path) -> Keys:
    """Load the identity at `path` if it exists, otherwise generate a new
    one and save it there. This is the function most agents actually want
    to call -- it makes identity persistent across runs without the caller
    having to think about the load/generate branching themselves."""
    path = Path(path)
    if path.exists():
        return load_identity(path)
    keys = generate_identity()
    save_identity(keys, path)
    return keys


async def publish_profile(client: Client, keys: Keys, name: str | None = None,
                           about: str | None = None, picture: str | None = None,
                           **extra_fields) -> Event:
    """Publish a kind:0 profile (NIP-01 metadata) for this agent. `client`
    must already be connected to at least one relay. `**extra_fields` maps
    to any other MetadataRecord field (website, nip05, lud16, etc.)."""
    record = MetadataRecord(name=name, about=about, picture=picture, **extra_fields)
    metadata = Metadata.from_record(record)
    event = metadata.into_event_builder().finalize(keys)
    await client.send_event(event)
    return event
