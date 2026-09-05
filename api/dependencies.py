import os
import tempfile
from pathlib import Path


try:
    from nostr_sdk_wrapper.agent import KuberboltAgent
except ImportError:
    from kuberbolt_nostr.agent import KuberboltAgent

# DEFAULT_RELAYS constant
env_relays = os.getenv("DEFAULT_RELAYS")
if env_relays:
    if env_relays.startswith("["):
        import json
        DEFAULT_RELAYS = json.loads(env_relays)
    else:
        DEFAULT_RELAYS = [r.strip() for r in env_relays.split(",") if r.strip()]
else:
    DEFAULT_RELAYS = ["wss://relay.damus.io", "wss://nos.lol"]

_discovery_agent: KuberboltAgent | None = None
_tmp_dir: tempfile.TemporaryDirectory | None = None


async def get_discovery_agent() -> KuberboltAgent:
    """Module-level singleton discovery agent, built once at app startup or on first call."""
    global _discovery_agent, _tmp_dir
    if _discovery_agent is None:
        _tmp_dir = tempfile.TemporaryDirectory()
        identity_path = os.path.join(_tmp_dir.name, "discovery_id.json")
        _discovery_agent = await KuberboltAgent.create(
            identity_path=identity_path,
            relay_urls=DEFAULT_RELAYS,
        )
    return _discovery_agent


async def cleanup_discovery_agent():
    """Clean up discovery agent singleton resources during app shutdown."""
    global _discovery_agent, _tmp_dir
    if _discovery_agent is not None:
        try:
            await _discovery_agent.disconnect()
        except Exception:
            pass
        _discovery_agent = None
    if _tmp_dir is not None:
        try:
            _tmp_dir.cleanup()
        except Exception:
            pass
        _tmp_dir = None
