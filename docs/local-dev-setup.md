# Local Development Setup Guide

This guide provides step-by-step instructions for setting up the Kuberbolt development environment on your local machine.

## Prerequisites

Ensure you have the following installed on your system:
- **Python 3.12+**
- **Go 1.21+**
- **Docker & Docker Compose**
- **Git**

## 1. Clone the Repository

```bash
git clone https://github.com/your-org/kuberbolt.git
cd kuberbolt
```

## 2. Set up the Lightning Network Daemon (LND)

Kuberbolt requires a Lightning backend. You can use the provided Docker infrastructure for local testing.

```bash
cd lightning-infra
docker compose -f docker-compose.lnd.yml up -d
```
*Wait for the node to sync and initialize.*

## 3. Set up the Python Environment (SDK & API)

We recommend using a virtual environment for the Python components.

```bash
# Return to the root directory
cd ..

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate

# Install all project dependencies in editable mode
pip install -e .
```

## 4. Set up the Go Environment (Gateway)

The Gateway (Edge Gatekeeper) enforces L402 payments and is written in Go.

```bash
cd ../gateway
# Download dependencies and build the binary
go mod tidy
go build ./...
```

Alternatively, you can run the gateway via Docker:
```bash
docker compose -f docker-compose.gateway.yml up -d
```

## 5. Configure Environment Variables

Create a `.env` file in the root directory (you can use `.env.example` as a template). You will need to configure your Nostr private key and Lightning node credentials (macaroons/TLS certs) to run the full end-to-end flows securely on your local machine.

## 6. Verify Installation

You can run the examples to ensure everything is working correctly:

1. **Run the local AI provider proxy:**
   ```bash
   # From the root directory
   python examples/provider.py
   ```
2. **In a separate terminal, run the client agent:**
   ```bash
   # Make sure your virtual environment is activated
   python examples/client.py
   ```
