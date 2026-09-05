# Kuberbolt Financial Pod — Developer Makefile

PROTO_DIR := ../proto
PB_OUT    := internal/pb

.PHONY: proto build test lint help

## proto: Regenerate Go code from .proto definitions (requires buf in PATH)
proto:
	cd $(PROTO_DIR) && buf generate

## build: Compile the financial-pod binary
build:
	go build ./...

## test: Run unit tests (mock tests only; integration tests require live LND)
test:
	go test ./... -short

## test-integration: Run all tests including live LND integration tests
## Requires: ALICE_HOST, ALICE_TLS_CERT, ALICE_MACAROON, BOB_HOST, etc.
test-integration:
	go test ./internal/gateway/... -v -run TestL402Integration -count=1

## lint: Run go vet and staticcheck
lint:
	go vet ./...

help:
	@grep -E '^##' $(MAKEFILE_LIST) | sed 's/## //'
