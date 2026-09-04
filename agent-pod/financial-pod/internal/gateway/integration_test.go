package gateway_test

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"testing"
	"time"

	"github.com/kuberbolt/financial-pod/internal/ln"
	"go.uber.org/zap"
)

// TestL402Integration runs an end-to-end L402 + HODL invoice test against
// two real LND nodes running in Docker.
//
// Prerequisites (run from lightning-infra/ before this test):
//
//	docker compose -f docker-compose.lnd.yml up -d
//	# wait for nodes to sync and channel to open
//
// Required environment variables:
//
//	ALICE_HOST         e.g. "localhost"
//	ALICE_GRPC_PORT    e.g. "10001"
//	ALICE_TLS_CERT     path to alice/tls.cert
//	ALICE_MACAROON     path to alice/admin.macaroon
//	BOB_HOST           e.g. "localhost"
//	BOB_GRPC_PORT      e.g. "10002"
//	BOB_TLS_CERT       path to bob/tls.cert
//	BOB_MACAROON       path to bob/admin.macaroon
//
// If any env var is missing, the test is skipped automatically.
func TestL402Integration(t *testing.T) {
	aliceCfg, bobCfg, ok := loadTestConfig()
	if !ok {
		t.Skip("LND integration env vars not set — skipping. Set ALICE_HOST, ALICE_TLS_CERT, etc.")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()

	// Connect Alice (provider) and Bob (client).
	t.Log("connecting to Alice LND…")
	alice, err := ln.NewClient(ctx, aliceCfg, newTestLogger(t))
	if err != nil {
		t.Fatalf("connect alice: %v", err)
	}
	defer alice.Close()

	t.Log("connecting to Bob LND…")
	bob, err := ln.NewClient(ctx, bobCfg, newTestLogger(t))
	if err != nil {
		t.Fatalf("connect bob: %v", err)
	}
	defer bob.Close()

	// Verify both nodes are reachable.
	aliceInfo, err := alice.GetInfo(ctx)
	if err != nil {
		t.Fatalf("alice GetInfo: %v", err)
	}
	t.Logf("alice: alias=%s pubkey=%s…", aliceInfo.Alias, aliceInfo.IdentityPubkey[:12])

	bobInfo, err := bob.GetInfo(ctx)
	if err != nil {
		t.Fatalf("bob GetInfo: %v", err)
	}
	t.Logf("bob:   alias=%s pubkey=%s…", bobInfo.Alias, bobInfo.IdentityPubkey[:12])

	// Verify a channel exists (Bob must be funded and have a channel to Alice).
	channels, err := bob.ListChannels(ctx)
	if err != nil {
		t.Fatalf("bob ListChannels: %v", err)
	}
	if len(channels) == 0 {
		t.Fatal("no active channels found on Bob's node — open a channel first")
	}
	t.Logf("bob has %d active channel(s)", len(channels))

	// ── PHASE 1: Alice creates HODL invoice ──────────────────────────────
	t.Log("\n--- Phase 1: Alice creates HODL invoice ---")

	preimage := make([]byte, 32)
	// Use deterministic preimage for the test (easier to debug).
	copy(preimage, []byte(fmt.Sprintf("test-preimage-%d", time.Now().UnixNano())))
	rhash := sha256.Sum256(preimage)
	rhashBytes := rhash[:]
	t.Logf("preimage: %s…", hex.EncodeToString(preimage)[:16])
	t.Logf("rhash:    %s…", hex.EncodeToString(rhashBytes)[:16])

	payReq, err := alice.AddHoldInvoice(ctx, rhashBytes, 10_000, 300, "integration test")
	if err != nil {
		t.Fatalf("alice AddHoldInvoice: %v", err)
	}
	t.Logf("HODL invoice: %s…", payReq[:30])

	// ── PHASE 2: Alice subscribes to invoice state ───────────────────────
	t.Log("\n--- Phase 2: Alice watches invoice state ---")

	updates, err := alice.SubscribeSingleInvoice(ctx, rhashBytes)
	if err != nil {
		t.Fatalf("alice SubscribeSingleInvoice: %v", err)
	}

	// ── PHASE 3: Bob pays the HODL invoice ───────────────────────────────
	t.Log("\n--- Phase 3: Bob pays HODL invoice (HTLC lock) ---")

	payErrCh := make(chan error, 1)
	var receivedPreimage []byte
	go func() {
		// SendPayment blocks until Alice settles or cancels.
		pimg, err := bob.SendPayment(ctx, payReq, 120)
		receivedPreimage = pimg
		payErrCh <- err
	}()

	// ── PHASE 4: Wait for ACCEPTED on Alice's side ───────────────────────
	t.Log("\n--- Phase 4: Wait for HTLC ACCEPTED ---")

	htlcAccepted := false
	deadline := time.After(30 * time.Second)
	for !htlcAccepted {
		select {
		case <-deadline:
			t.Fatal("timed out waiting for HTLC ACCEPTED state")
		case update, ok := <-updates:
			if !ok {
				t.Fatal("invoice subscription channel closed unexpectedly")
			}
			if update.Err != nil {
				t.Fatalf("invoice subscription error: %v", update.Err)
			}
			t.Logf("invoice state: %d", update.State)
			if update.State == ln.InvoiceAccepted {
				htlcAccepted = true
				t.Logf("✓ HTLC ACCEPTED — funds locked: %d msat", update.AmtMSat)
			}
		}
	}

	// ── PHASE 5: Alice settles the HODL invoice ──────────────────────────
	t.Log("\n--- Phase 5: Alice settles HODL invoice ---")

	if err := alice.SettleInvoice(ctx, preimage); err != nil {
		t.Fatalf("alice SettleInvoice: %v", err)
	}
	t.Log("✓ SettleInvoice called — preimage revealed to network")

	// ── PHASE 6: Bob's SendPayment should complete ───────────────────────
	t.Log("\n--- Phase 6: Bob receives preimage from settled payment ---")

	select {
	case payErr := <-payErrCh:
		if payErr != nil {
			t.Fatalf("bob SendPayment error: %v", payErr)
		}
	case <-time.After(30 * time.Second):
		t.Fatal("timed out waiting for Bob's SendPayment to complete")
	}

	if len(receivedPreimage) == 0 {
		t.Fatal("bob received empty preimage")
	}

	// ── PHASE 7: Verify preimage matches ─────────────────────────────────
	t.Log("\n--- Phase 7: Verify preimage integrity ---")

	computedHash := sha256.Sum256(receivedPreimage)
	if hex.EncodeToString(computedHash[:]) != hex.EncodeToString(rhashBytes) {
		t.Fatalf("preimage mismatch: SHA256(%x…) = %x…, want %x…",
			receivedPreimage[:4], computedHash[:4], rhashBytes[:4])
	}

	t.Logf("✓ SHA256(preimage) == rhash — verification passed")
	t.Log("\n=== Integration test PASSED ===")
	t.Logf("    Alice received: 10,000 msat")
	t.Logf("    Bob confirmed:  preimage %s…", hex.EncodeToString(receivedPreimage)[:16])
}

// TestCancelHODL verifies that Alice can cancel an invoice before settlement,
// returning funds to Bob.
func TestCancelHODL(t *testing.T) {
	aliceCfg, bobCfg, ok := loadTestConfig()
	if !ok {
		t.Skip("LND integration env vars not set — skipping.")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	alice, err := ln.NewClient(ctx, aliceCfg, newTestLogger(t))
	if err != nil {
		t.Fatalf("connect alice: %v", err)
	}
	defer alice.Close()

	bob, err := ln.NewClient(ctx, bobCfg, newTestLogger(t))
	if err != nil {
		t.Fatalf("connect bob: %v", err)
	}
	defer bob.Close()

	preimage := make([]byte, 32)
	copy(preimage, []byte(fmt.Sprintf("cancel-test-preimage-%d", time.Now().UnixNano())))
	rhash := sha256.Sum256(preimage)
	rhashBytes := rhash[:]

	payReq, err := alice.AddHoldInvoice(ctx, rhashBytes, 5_000, 300, "cancel test")
	if err != nil {
		t.Fatalf("AddHoldInvoice: %v", err)
	}

	updates, _ := alice.SubscribeSingleInvoice(ctx, rhashBytes)

	payErrCh := make(chan error, 1)
	go func() {
		_, err := bob.SendPayment(ctx, payReq, 120)
		payErrCh <- err
	}()

	// Wait for ACCEPTED.
	deadline := time.After(30 * time.Second)
	for {
		select {
		case <-deadline:
			t.Fatal("timed out waiting for HTLC ACCEPTED")
		case update := <-updates:
			if update.State == ln.InvoiceAccepted {
				t.Log("HTLC ACCEPTED — now cancelling invoice")
				goto cancel
			}
		}
	}
cancel:
	if err := alice.CancelInvoice(ctx, rhashBytes); err != nil {
		t.Fatalf("CancelInvoice: %v", err)
	}
	t.Log("CancelInvoice called")

	// Bob's payment should fail with an error.
	select {
	case payErr := <-payErrCh:
		if payErr == nil {
			t.Fatal("expected Bob's payment to fail after cancel, but it succeeded")
		}
		t.Logf("✓ Bob's payment correctly failed: %v", payErr)
	case <-time.After(30 * time.Second):
		t.Fatal("timed out waiting for Bob's payment failure")
	}
}

// loadTestConfig reads LND connection config from environment variables.
// Returns false if any required variable is missing.
func loadTestConfig() (alice, bob *ln.Config, ok bool) {
	vars := []string{
		"ALICE_HOST", "ALICE_GRPC_PORT", "ALICE_TLS_CERT", "ALICE_MACAROON",
		"BOB_HOST", "BOB_GRPC_PORT", "BOB_TLS_CERT", "BOB_MACAROON",
	}
	for _, v := range vars {
		if os.Getenv(v) == "" {
			return nil, nil, false
		}
	}

	alicePort := 10001
	fmt.Sscanf(os.Getenv("ALICE_GRPC_PORT"), "%d", &alicePort)
	bobPort := 10002
	fmt.Sscanf(os.Getenv("BOB_GRPC_PORT"), "%d", &bobPort)

	return &ln.Config{
			Host:         os.Getenv("ALICE_HOST"),
			GRPCPort:     alicePort,
			TLSCertPath:  os.Getenv("ALICE_TLS_CERT"),
			MacaroonPath: os.Getenv("ALICE_MACAROON"),
		}, &ln.Config{
			Host:         os.Getenv("BOB_HOST"),
			GRPCPort:     bobPort,
			TLSCertPath:  os.Getenv("BOB_TLS_CERT"),
			MacaroonPath: os.Getenv("BOB_MACAROON"),
		}, true
}

// newTestLogger returns a zap logger that writes to t.Log.
func newTestLogger(t *testing.T) *zap.Logger {
	t.Helper()
	l, _ := zap.NewDevelopment()
	return l
}
