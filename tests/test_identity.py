import os
import tempfile
from pathlib import Path


from nostr_sdk import Metadata, MetadataRecord
from client.kuberbolt.discovery.nostr import generate_identity, get_or_create_identity


def test_generate_and_persist_identity():
    with tempfile.TemporaryDirectory() as tmpdir:
        identity_path = Path(tmpdir) / "test_identity.json"

        keys1 = get_or_create_identity(identity_path)
        keys2 = get_or_create_identity(identity_path)  # should load, not regenerate

        assert keys1.public_key().to_hex() == keys2.public_key().to_hex()

        mode = oct(os.stat(identity_path).st_mode)[-3:]
        assert mode == "600"


def test_profile_metadata_builds_cleanly():
    record = MetadataRecord(name="Test Agent", about="A test", picture=None)
    meta = Metadata.from_record(record)
    as_json = meta.as_json()

    assert "picture" not in as_json
    assert "Test Agent" in as_json


def test_profile_event_signs_and_verifies():
    keys = generate_identity()
    record = MetadataRecord(name="Test Agent")
    meta = Metadata.from_record(record)

    event = meta.into_event_builder().finalize(keys)

    assert event.verify()
    assert event.kind().as_u16() == 0
    assert event.author().to_hex() == keys.public_key().to_hex()