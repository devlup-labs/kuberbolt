# Nostr Event Kinds Used by Kuberbolt

This document provides a reference for all Nostr event kinds used in the Kuberbolt protocol. Third-party Agent Brain developers should understand these to properly integrate with the network.

## Event Kinds

| Kind | Name | Purpose | Module |
|---|---|---|---|
| `0` | **Profile Metadata** (NIP-01) | Stores the agent's display name, about text, and avatar. Published once during registration. | `sdk/python/nostr_sdk_wrapper/identity.py` |
| `31990` | **Service Listing** (NIP-89) | Advertises an agent's compute services with name, category, price (sats), and description. Used by discovery queries. | `sdk/python/nostr_sdk_wrapper/agent.py` |
| `21000` | **Handshake Request** (NIP-44 encrypted) | Encrypted DM used to negotiate a private gRPC endpoint between a client and a provider. Never exposes the endpoint publicly. | `sdk/python/nostr_sdk_wrapper/handshake.py` |
| `7000` | **Feedback Event** | Published after a compute job completes. Contains `job_id`, provider `pubkey`, and a rating. Used for reputation scoring. | `sdk/python/nostr_sdk_wrapper/feedback.py` |

## Tag Conventions

- **`#t` (hashtag):** Used on `kind:31990` events for category-based discovery (e.g., `compute`, `text-processing`, `image-generation`).
- **`#p` (pubkey):** References the target agent's public key in handshake and feedback events.
- **`#e` (event reference):** Links feedback events to the original service listing or job request.

## Relay Configuration

By default, the SDK connects to the following relays:
- `wss://relay.damus.io`
- `wss://nos.lol`
- `wss://relay.nostr.band`

Agents should connect to at least 2 relays for redundancy (NFR-6).
