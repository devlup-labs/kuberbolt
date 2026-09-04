#!/bin/bash
cd "$(dirname "$0")/.."
INFRA_DIR=$(pwd)

echo "export ALICE_HOST=\"localhost\""
echo "export ALICE_GRPC_PORT=\"10001\""
echo "export ALICE_TLS_CERT=\"$INFRA_DIR/alice-data/tls.cert\""
echo "export ALICE_MACAROON=\"$INFRA_DIR/alice-data/data/chain/bitcoin/regtest/admin.macaroon\""

echo ""

echo "export BOB_HOST=\"localhost\""
echo "export BOB_GRPC_PORT=\"10002\""
echo "export BOB_TLS_CERT=\"$INFRA_DIR/bob-data/tls.cert\""
echo "export BOB_MACAROON=\"$INFRA_DIR/bob-data/data/chain/bitcoin/regtest/admin.macaroon\""
