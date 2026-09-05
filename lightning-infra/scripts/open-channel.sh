#!/bin/bash
set -e

cd "$(dirname "$0")/.."

echo "Fetching Alice's pubkey..."
ALICE_PUBKEY=$(docker compose -f docker-compose.lnd.yml exec -T alice lncli --network regtest getinfo | jq -r '.identity_pubkey')
echo "Alice pubkey: $ALICE_PUBKEY"

echo "Connecting Bob to Alice..."
docker compose -f docker-compose.lnd.yml exec -T bob lncli --network regtest connect "${ALICE_PUBKEY}@alice" || echo "Maybe already connected"

echo "Opening a channel from Bob to Alice (capacity: 10,000,000 sats)..."
docker compose -f docker-compose.lnd.yml exec -T bob lncli --network regtest openchannel --node_key "$ALICE_PUBKEY" --local_amt 10000000 || echo "Channel may already be open"

echo "Mining 6 blocks to confirm the channel..."
# We generate 6 blocks to a new address to confirm the channel
NEW_ADDRESS=$(docker compose -f docker-compose.lnd.yml exec -T bob lncli --network regtest newaddress p2wkh | jq -r '.address')
docker compose -f docker-compose.lnd.yml exec -T bitcoind bitcoin-cli -regtest -rpcuser=devuser -rpcpassword=devpass generatetoaddress 6 "$NEW_ADDRESS" || true

echo "Waiting for LND to sync and channel to become active..."
sleep 10

echo "Bob's channels:"
docker compose -f docker-compose.lnd.yml exec -T bob lncli --network regtest listchannels

echo "Channel is open and ready!"
