"""
Unit tests for KuberboltAgent.serve_endpoint_requests daemon loop.
"""

import asyncio
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from sdk.python.nostr_sdk_wrapper.agent import KuberboltAgent


class MockEvent:
    def __init__(self, event_id: str, author_pubkey: str):
        self._event_id = event_id
        self._author_pubkey = author_pubkey

    def id(self):
        m = MagicMock()
        m.to_hex.return_value = self._event_id
        return m

    def author(self):
        m = MagicMock()
        m.to_hex.return_value = self._author_pubkey
        return m


@pytest.fixture
def mock_agent():
    keys = MagicMock()
    pubkey_mock = MagicMock()
    pubkey_mock.to_hex.return_value = "0000000000000000000000000000000000000000000000000000000000000001"
    keys.public_key.return_value = pubkey_mock

    client = MagicMock()
    agent = KuberboltAgent(keys, client)
    agent.send_handshake = AsyncMock()
    return agent


@pytest.mark.anyio
async def test_serve_endpoint_requests_success(mock_agent):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_ledger.db")
        mock_ev = MockEvent("event_001", "sender_pubkey_123")
        stop_event = asyncio.Event()

        async def mock_fetch(*args, **kwargs):
            if stop_event.is_set():
                return []
            stop_event.set()
            return [mock_ev]

        payload = {"action": "resolve_endpoint", "job_id": "job_abc_123"}

        with patch("sdk.python.nostr_sdk_wrapper.handshake.fetch_handshake_events", side_effect=mock_fetch), \
             patch("sdk.python.nostr_sdk_wrapper.handshake.decrypt_event", return_value=payload):

            await mock_agent.serve_endpoint_requests(
                host="192.168.1.50",
                port=50051,
                poll_interval=1,
                db_path=db_path,
                stop_event=stop_event,
            )

        # Assert reply sent
        mock_agent.send_handshake.assert_called_once_with(
            "sender_pubkey_123",
            {"job_id": "job_abc_123", "host": "192.168.1.50", "port": 50051},
        )

        # Assert SQLite state persistence
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT event_id, sender_pubkey, job_id FROM seen_requests")
        row = cursor.fetchone()
        conn.close()

        assert row == ("event_001", "sender_pubkey_123", "job_abc_123")


@pytest.mark.anyio
async def test_serve_endpoint_requests_deduplication(mock_agent):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_ledger.db")
        mock_ev = MockEvent("event_dup", "sender_pubkey_123")
        stop_event = asyncio.Event()

        fetch_count = 0

        async def mock_fetch(*args, **kwargs):
            nonlocal fetch_count
            fetch_count += 1
            if fetch_count > 2:
                stop_event.set()
                return []
            return [mock_ev]

        payload = {"action": "resolve_endpoint", "job_id": "job_dup_1"}

        with patch("sdk.python.nostr_sdk_wrapper.handshake.fetch_handshake_events", side_effect=mock_fetch), \
             patch("sdk.python.nostr_sdk_wrapper.handshake.decrypt_event", return_value=payload):

            await mock_agent.serve_endpoint_requests(
                host="127.0.0.1",
                port=8080,
                poll_interval=1,
                db_path=db_path,
                stop_event=stop_event,
            )

        # Send handshake should only be called ONCE despite 2 loop iterations returning the same event
        assert mock_agent.send_handshake.call_count == 1


@pytest.mark.anyio
async def test_serve_endpoint_requests_missing_job_id(mock_agent):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_ledger.db")
        mock_ev = MockEvent("event_no_job", "sender_pubkey_123")
        stop_event = asyncio.Event()

        async def mock_fetch(*args, **kwargs):
            stop_event.set()
            return [mock_ev]

        payload = {"action": "resolve_endpoint"}  # missing job_id

        with patch("sdk.python.nostr_sdk_wrapper.handshake.fetch_handshake_events", side_effect=mock_fetch), \
             patch("sdk.python.nostr_sdk_wrapper.handshake.decrypt_event", return_value=payload):

            await mock_agent.serve_endpoint_requests(
                host="127.0.0.1",
                port=8080,
                poll_interval=1,
                db_path=db_path,
                stop_event=stop_event,
            )

        mock_agent.send_handshake.assert_not_called()


@pytest.mark.anyio
async def test_serve_endpoint_requests_authorization(mock_agent):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_ledger.db")
        mock_ev = MockEvent("event_auth", "unauthorized_pubkey")
        stop_event = asyncio.Event()

        async def mock_fetch(*args, **kwargs):
            stop_event.set()
            return [mock_ev]

        payload = {"action": "resolve_endpoint", "job_id": "job_auth_1"}

        with patch("sdk.python.nostr_sdk_wrapper.handshake.fetch_handshake_events", side_effect=mock_fetch), \
             patch("sdk.python.nostr_sdk_wrapper.handshake.decrypt_event", return_value=payload):

            await mock_agent.serve_endpoint_requests(
                host="127.0.0.1",
                port=8080,
                poll_interval=1,
                db_path=db_path,
                allowed_pubkeys=["allowed_pubkey_only"],
                stop_event=stop_event,
            )

        mock_agent.send_handshake.assert_not_called()


@pytest.mark.anyio
async def test_serve_endpoint_requests_decrypt_error(mock_agent):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_ledger.db")
        mock_ev = MockEvent("event_corrupt", "sender_pubkey_123")
        stop_event = asyncio.Event()

        async def mock_fetch(*args, **kwargs):
            stop_event.set()
            return [mock_ev]

        with patch("sdk.python.nostr_sdk_wrapper.handshake.fetch_handshake_events", side_effect=mock_fetch), \
             patch("sdk.python.nostr_sdk_wrapper.handshake.decrypt_event", side_effect=ValueError("bad signature")):

            await mock_agent.serve_endpoint_requests(
                host="127.0.0.1",
                port=8080,
                poll_interval=1,
                db_path=db_path,
                stop_event=stop_event,
            )

        mock_agent.send_handshake.assert_not_called()
