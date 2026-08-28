from contextlib import asynccontextmanager
import json
import logging
import os
import re
import sys
from pathlib import Path

# Ensure project root is in sys.path so 'api' package can be resolved when running directly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from api.dependencies import cleanup_discovery_agent, get_discovery_agent
from api.errors import register_exception_handlers
from api.routers import agents, feedback, providers, requests, search

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kuberbolt.api")


SENSITIVE_KEY_MARKERS = (
    "privkey",
    "secret",
    "private_key",
    "api_key",
    "token",
    "password",
)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in SENSITIVE_KEY_MARKERS)


def redact_sensitive_data(data):
    """Recursively redact sensitive key fields such as nostr_privkey."""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if _is_sensitive_key(key):
                result[key] = "[REDACTED]"
            else:
                result[key] = redact_sensitive_data(value)
        return result
    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    return data


class SensitiveDataRedactionLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        body_bytes = await request.body()
        body_consumed = False

        # Re-assign request._receive so downstream endpoint handlers can still read body
        async def receive():
            nonlocal body_consumed
            if body_consumed:
                return {"type": "http.request", "body": b"", "more_body": False}
            body_consumed = True
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        request._receive = receive

        logged_body = ""
        if body_bytes:
            try:
                body_json = json.loads(body_bytes)
                redacted_json = redact_sensitive_data(body_json)
                logged_body = json.dumps(redacted_json)
            except Exception:
                raw_str = body_bytes.decode("utf-8", errors="ignore")
                for field_name in (
                    "nostr_privkey",
                    "agent_privkey",
                    "secret_key",
                    "secret_key_hex",
                    "secret_key_bech32",
                    "private_key",
                    "api_key",
                    "token",
                    "password",
                ):
                    raw_str = re.sub(
                        rf'("{field_name}"\s*:\s*")[^"]+(")',
                        r'\1[REDACTED]\2',
                        raw_str,
                    )
                logged_body = raw_str

        logger.info(f"Incoming Request: {request.method} {request.url.path} Body: {logged_body}")

        response = await call_next(request)
        logger.info(f"Response: {response.status_code} {request.method} {request.url.path}")
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup event: warm up get_discovery_agent()
    logger.info("Warming up discovery agent...")
    try:
        await get_discovery_agent()
    except Exception as e:
        logger.error(f"Failed to warm up discovery agent on startup: {e}")
    yield
    # Cleanup on shutdown
    logger.info("Cleaning up discovery agent...")
    await cleanup_discovery_agent()


app = FastAPI(title="Kuberbolt REST API", lifespan=lifespan)

# Register global exception handlers
register_exception_handlers(app)

# CORS middleware (allow frontend origin from env var)
frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
origins = [o.strip() for o in frontend_origin.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware with redaction
app.add_middleware(SensitiveDataRedactionLoggingMiddleware)

# Include routers
app.include_router(agents.router)
app.include_router(providers.router)
app.include_router(requests.router)
app.include_router(search.router)
app.include_router(feedback.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
