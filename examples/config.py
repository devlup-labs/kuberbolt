import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_RELAYS = ["wss://relay.damus.io", "wss://nos.lol"]


def load_env_file(path: Path = ENV_PATH) -> None:
    """Load simple KEY=VALUE pairs from .env without adding a dependency."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        os.environ.setdefault(key, value)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    raise RuntimeError(f"Missing required environment variable: {name}")


def get_relays() -> list[str]:
    raw_relays = os.getenv("KUBERBOLT_RELAYS") or os.getenv("DEFAULT_RELAYS")
    if not raw_relays:
        return DEFAULT_RELAYS
    return [relay.strip() for relay in raw_relays.split(",") if relay.strip()]


def get_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    return int(raw_value) if raw_value else default
