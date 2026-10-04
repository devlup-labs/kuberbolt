#!/usr/bin/env bash
# scripts/deploy-pod.sh — Deploy a new agent pod
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

usage() {
  cat <<EOF
Usage: $0 --name <agent-name> [--grpc-port <port>] [--lnd-port <port>]

Options:
  --name          Agent name (required)
  --grpc-port     Financial Pod gRPC port (default: 6001)
  --lnd-port      LND gRPC port (default: 10009)
  --detach        Run in background
EOF
  exit 1
}

AGENT_NAME="" GRPC_PORT=6001 LND_PORT=10009 DETACH=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --name)      AGENT_NAME="$2"; shift 2;;
    --grpc-port) GRPC_PORT="$2"; shift 2;;
    --lnd-port)  LND_PORT="$2"; shift 2;;
    --detach)    DETACH="-d"; shift;;
    *)           usage;;
  esac
done

[[ -z "$AGENT_NAME" ]] && usage

# Step 1: Initialize Financial Pod config if not exists
FP_BIN="${PROJECT_ROOT}/agent-pod/financial-pod/cmd/financialpod"
if [[ ! -d "${HOME}/.kuberbolt/${AGENT_NAME}" ]]; then
  echo ">>> Initializing agent config for '${AGENT_NAME}'..."
  go run "${FP_BIN}/main.go" --init --name "$AGENT_NAME"
fi

# Step 2: Validate LND credentials exist
CONFIG_DIR="${HOME}/.kuberbolt/${AGENT_NAME}"
if [[ ! -f "${CONFIG_DIR}/tls.cert" ]] || [[ ! -f "${CONFIG_DIR}/admin.macaroon" ]]; then
  echo "ERROR: Missing LND credentials in ${CONFIG_DIR}/"
  echo "  Required: tls.cert, admin.macaroon"
  exit 1
fi

# Step 3: Deploy pod
echo ">>> Deploying pod '${AGENT_NAME}' (gRPC=${GRPC_PORT}, LND=${LND_PORT})..."
export AGENT_NAME GRPC_PORT LND_GRPC_PORT="${LND_PORT}"

docker compose -f "${PROJECT_ROOT}/agent-pod/docker-compose.pod.yml" \
  --project-name "kuberbolt-${AGENT_NAME}" \
  up --build ${DETACH}

echo ">>> Pod '${AGENT_NAME}' deployed successfully."
