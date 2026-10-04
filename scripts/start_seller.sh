#!/usr/bin/env bash
# ==============================================================================
# Kuberbolt — Start Seller Stack (Machine B)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=================================================================="
echo "🚀 Starting Kuberbolt Seller Agent (Machine B)"
echo "=================================================================="

# Check Python environment
if [ -d "${REPO_ROOT}/.venv" ]; then
    source "${REPO_ROOT}/.venv/bin/activate"
elif [ -d "${REPO_ROOT}/venv" ]; then
    source "${REPO_ROOT}/venv/bin/activate"
else
    echo "⚠️  No virtualenv found at .venv or venv. Using system python3."
fi

# Load .env file if it exists
if [ -f "${REPO_ROOT}/.env" ]; then
    echo "📂 Loading environment variables from .env"
    set -a
    source "${REPO_ROOT}/.env"
    set +a
fi

# Detect Local LAN IP
LOCAL_IP=$(python3 -c "
import sys; sys.path.insert(0, '${REPO_ROOT}/agent-pod/brain');
from app.utils.network import get_local_ip;
print(get_local_ip())
" 2>/dev/null || ipconfig getifaddr en0 2>/dev/null || echo "127.0.0.1")

echo "📍 Detected LAN IP: ${LOCAL_IP}"
echo "📡 Financial Pod gRPC Port: ${FP_GRPC_PORT:-6001}"
echo "🧠 Brain Compute Port: ${BRAIN_PORT:-8001}"

if [ -z "${SELLER_NOSTR_PRIVKEY:-}" ]; then
    echo ""
    echo "⚠️  SELLER_NOSTR_PRIVKEY is not set in environment."
    echo "   Please register your seller agent on the SDK server (Machine C) first:"
    echo "   curl -X POST http://<MACHINE_C_IP>:8000/api/agents/register -H 'Content-Type: application/json' -d '{\"role\":\"merchant\",\"display_name\":\"Kuberbolt Summarizer\",\"lightning\":{\"node_pubkey\":\"...\",\"lightning_address\":\"seller@testnet\"},\"service\":{\"service_name\":\"Text Summarization\",\"category\":\"text-summarization\",\"price_sats\":100,\"price_unit\":\"per_request\"}}'"
    echo ""
    read -rp "Enter your SELLER_NOSTR_PRIVKEY (hex) or press Enter to run compute-only: " USER_KEY
    if [ -n "${USER_KEY}" ]; then
        export SELLER_NOSTR_PRIVKEY="${USER_KEY}"
    fi
fi

if [ -z "${GOOGLE_API_KEY:-}" ]; then
    echo "⚠️  GOOGLE_API_KEY is not set. Brain will run in offline fallback mode."
fi

export PYTHONPATH="${REPO_ROOT}/agent-pod/brain:${REPO_ROOT}:${PYTHONPATH:-}"
export BRAIN_HOST="0.0.0.0"
export BRAIN_PORT="${BRAIN_PORT:-8001}"
export FP_GRPC_PORT="${FP_GRPC_PORT:-6001}"

echo ""
echo "Starting Seller Brain (FastAPI Compute Server + Nostr Endpoint Resolver)..."
exec python3 -m app.seller_agent
