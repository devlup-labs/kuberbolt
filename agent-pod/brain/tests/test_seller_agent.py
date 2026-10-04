import base64
import json
import pytest
from fastapi.testclient import TestClient

from app.seller_agent import app, summarize_text
from app.utils.network import get_local_ip


def test_get_local_ip():
    ip = get_local_ip()
    assert isinstance(ip, str)
    assert len(ip.split(".")) == 4


def test_health_endpoint():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["role"] == "seller_brain"
    assert "local_ip" in data


@pytest.mark.asyncio
async def test_summarize_text_offline_fallback():
    sample_text = "The Lightning Network is a layer 2 payment protocol built on top of Bitcoin. It enables fast, low-cost microtransactions across a network of bidirectional payment channels."
    summary = await summarize_text(sample_text)
    assert isinstance(summary, str)
    assert len(summary) > 0


def test_compute_endpoint_json_payload():
    client = TestClient(app)
    
    payload = {"text": "Bitcoin is a decentralized digital currency designed to enable peer-to-peer money transfers over the internet."}
    payload_bytes = json.dumps(payload).encode("utf-8")
    payload_b64 = base64.b64encode(payload_bytes).decode("utf-8")
    
    resp = client.post(
        "/compute",
        json={
            "service_kind": "text-summarization",
            "job_spec_base64": payload_b64,
        },
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["error"] == ""
    assert data["output_data_base64"] != ""
    
    output_bytes = base64.b64decode(data["output_data_base64"])
    output_json = json.loads(output_bytes.decode("utf-8"))
    assert output_json["status"] == "completed"
    assert output_json["service_kind"] == "text-summarization"
    assert "summary" in output_json
