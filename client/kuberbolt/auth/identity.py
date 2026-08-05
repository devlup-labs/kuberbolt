from pathlib import Path
from coincurve import PrivateKey


def save_key(private_key_hex: str, path: str):
    """Write a private key (as hex text) to disk, creating folders if needed."""
    file_path = Path(path).expanduser()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(private_key_hex)


def load_or_create_key(path: str) -> str:
    """Load an existing private key from disk, or generate and save a new one."""
    file_path = Path(path).expanduser()

    if file_path.exists():
        return file_path.read_text().strip()

    new_key = PrivateKey().to_hex()
    save_key(new_key, path)
    return new_key