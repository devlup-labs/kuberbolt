import asyncio
import json
from datetime import timedelta
from pathlib import Path

from nostr_sdk import Client, Keys, NostrSigner, RelayUrl, Filter, Kind

# ==========================================
# 1. Generate Agent Keys
# ==========================================
def generate_agent_keys() -> Keys:
    """
    Generates a new sec and public key for the agent.
    Returns a nostr_sdk.Keys object.
    """
    return generate_identity()


def generate_identity() -> Keys:
    """Create a fresh Nostr identity keypair."""
    return Keys.generate()


def get_or_create_identity(path: str | Path) -> Keys:
    """Load an existing identity from disk or create and persist a new one."""
    identity_path = Path(path)
    if identity_path.exists():
        try:
            with identity_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            secret_key = payload.get("secret_key")
            if secret_key:
                return Keys.parse(secret_key)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

    keys = generate_identity()
    identity_path.parent.mkdir(parents=True, exist_ok=True)
    with identity_path.open("w", encoding="utf-8") as handle:
        json.dump({"secret_key": keys.secret_key().to_bech32()}, handle)
    identity_path.chmod(0o600)
    return keys


__all__ = ["generate_agent_keys", "generate_identity", "get_or_create_identity"]
