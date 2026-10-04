"""Small compute boundary for the Brain Pod.

Provider-specific LangChain tools can replace ``run_job`` without changing the
Financial Pod contract. The default implementation preserves the submitted JSON
as a deterministic local development response.
"""

from __future__ import annotations

import json
from typing import Any


async def run_job(service_kind: str, job_spec: bytes) -> bytes:
    """Run a job without exposing payment or Lightning credentials to the Brain."""
    try:
        payload: Any = json.loads(job_spec) if job_spec else {}
    except json.JSONDecodeError:
        payload = {"raw_job_spec": job_spec.decode("utf-8", errors="replace")}

    return json.dumps(
        {"status": "completed", "service_kind": service_kind, "result": payload},
        separators=(",", ":"),
    ).encode()
