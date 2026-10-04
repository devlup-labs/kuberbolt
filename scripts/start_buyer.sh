#!/usr/bin/env bash
# ==============================================================================
# Kuberbolt — Start Buyer Agent (Machine A)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=================================================================="
echo "🚀 Starting Kuberbolt Buyer Agent (Machine A)"
echo "=================================================================="

# Check Python environment
if [ -d "${REPO_ROOT}/.venv" ]; then
    source "${REPO_ROOT}/.venv/bin/activate"
elif [ -d "${REPO_ROOT}/venv" ]; then
    source "${REPO_ROOT}/venv/bin/activate"
fi

# Load .env file if it exists
if [ -f "${REPO_ROOT}/.env" ]; then
    echo "📂 Loading environment variables from .env"
    set -a
    source "${REPO_ROOT}/.env"
    set +a
fi

if [ -z "${SDK_SERVER_URL:-}" ]; then
    echo "Enter SDK Server URL (Machine C) [e.g. http://192.168.1.50:8000]: "
    read -rp "SDK_SERVER_URL: " USER_SDK_URL
    export SDK_SERVER_URL="${USER_SDK_URL}"
fi

if [ -z "${BUYER_NOSTR_PUBKEY:-}" ]; then
    read -rp "BUYER_NOSTR_PUBKEY: " BUYER_NOSTR_PUBKEY
    export BUYER_NOSTR_PUBKEY
fi

if [ -z "${BUYER_SESSION_TOKEN:-}" ]; then
    read -rsp "BUYER_SESSION_TOKEN: " BUYER_SESSION_TOKEN
    echo
    export BUYER_SESSION_TOKEN
fi

if [ -z "${BUYER_FP_ADDR:-}" ]; then
    read -rp "BUYER_FP_ADDR (host:port): " BUYER_FP_ADDR
    export BUYER_FP_ADDR
fi

export PYTHONPATH="${REPO_ROOT}/agent-pod/brain:${REPO_ROOT}:${PYTHONPATH:-}"

PROMPT="${1:-Find a text summarization provider on the Kuberbolt network and use it to summarize this text: 'The Lightning Network is a payment channel network built on top of Bitcoin that enables instant, high-volume micropayments with minimal fees.'}"

echo ""
echo "Running Buyer Agent with prompt: \"$PROMPT\""
exec python3 -m app.buyer_agent "$PROMPT"
