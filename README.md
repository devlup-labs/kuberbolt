# Kuberbolt

Kuberbolt is an autonomous, decentralized financial and semantic routing layer for AI agents. It enables machines to discover each other via **Nostr**, negotiate terms securely, and pay for compute in sub-cent micro-transactions via the **Lightning Network** (using L402) over high-speed **gRPC**.

## Repository Structure

This repository is a monorepo containing the following components:

*   **`/client`**: The Python SDK (Brain). Provides LangChain tools for Nostr discovery and middleware for L402 gRPC execution.
*   **`/gatekeeper`**: The Go daemons. Contains the CFO Daemon (local LDK node manager) and the Edge Gatekeeper (reverse proxy that enforces L402 payments).
*   **`/proto`**: Shared Protocol Buffer definitions for the gRPC execution rail.
*   **`/examples`**: Boilerplate templates for deploying both Client Agents and Merchant Agents.

## Architecture & Documentation

For a comprehensive overview of the architecture, workflow, and design decisions (including the dual-rail system, Hold Invoices, and NAT Traversal), please read the **[Software Requirements Specification (SRS)](SRS.md)**.

## Getting Started

Because Kuberbolt utilizes a dual-pod architecture, setup depends on whether you are running a Client Agent (Buyer) or a Merchant Agent (Seller).

### For Client Agents (Python)
Client Agents use the Python SDK to discover merchants via Nostr and pay for compute.
1. Navigate to the client directory: `cd client`
2. Install the SDK: `pip install -e .`
3. Provide your Nostr private key and connect your funding source (e.g., Alby wallet or local LDK node).
4. Use the LangChain middleware to wrap your tool calls. (See `examples/client_agent_example/main.py`).

### For Merchant Agents (Go)
Merchant Agents run the Go Gatekeeper to enforce L402 payments before allowing access to local AI compute.
1. Navigate to the gatekeeper directory: `cd gatekeeper`
2. Build the binaries: `go build ./...`
3. Run your AI model locally (e.g., YOLOv9 on port `8080`).
4. Run the Gatekeeper proxy to expose your model to the Kuberbolt network. (See `examples/merchant_gpu_example/docker-compose.yml`).

## Contributing

We welcome contributions to Kuberbolt! Please review our [Contributing Guidelines](CONTRIBUTING.md) to understand our development workflow, how to run tests, and how to format pull requests. Be sure to also read our [Code of Conduct](CODE_OF_CONDUCT.md) before participating.

## License
MIT License.
