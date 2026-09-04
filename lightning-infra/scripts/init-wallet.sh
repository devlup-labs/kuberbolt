#!/bin/bash
set -e

# Change directory to the infrastructure root
cd "$(dirname "$0")/.."

echo "Waiting for Alice and Bob LND nodes to be ready..."
sleep 5

echo "Creating wallet for Alice..."
docker compose -f docker-compose.lnd.yml exec -T alice bash -c 'echo -e "password\npassword\n" | lncli --network regtest create' || echo "Alice wallet may already exist."

echo "Creating wallet for Bob..."
docker compose -f docker-compose.lnd.yml exec -T bob bash -c 'echo -e "password\npassword\n" | lncli --network regtest create' || echo "Bob wallet may already exist."

echo "Waiting for wallets to initialize..."
sleep 5

echo "Generating a new regtest address for Bob..."
BOB_ADDRESS=$(docker compose -f docker-compose.lnd.yml exec -T bob lncli --network regtest newaddress p2wkh | jq -r '.address')
echo "Bob address: $BOB_ADDRESS"

echo "Mining 101 blocks to fund Bob's wallet..."
docker compose -f docker-compose.lnd.yml exec -T bitcoind bitcoin-cli -regtest -rpcuser=devuser -rpcpassword=devpass generatetoaddress 101 "$BOB_ADDRESS"

echo "Waiting for LND to sync the new blocks..."
sleep 10

echo "Checking Bob's balance..."
docker compose -f docker-compose.lnd.yml exec -T bob lncli --network regtest walletbalance

echo "Wallets initialized and funded!"
