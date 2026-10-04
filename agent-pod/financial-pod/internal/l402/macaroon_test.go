package l402

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"strings"
	"testing"
	"time"
)

func TestCreateAndVerifyMacaroon(t *testing.T) {
	rootKey := []byte("12345678901234567890123456789012") // 32 bytes
	mgr := NewManager(rootKey)

	preimage := make([]byte, 32)
	rand.Read(preimage)
	paymentHash := sha256.Sum256(preimage)

	macBytes, err := mgr.CreateMacaroon(paymentHash[:], 5*time.Minute)
	if err != nil {
		t.Fatalf("CreateMacaroon failed: %v", err)
	}

	// 1. Verify without preimage (HMAC + expiry only)
	if err := mgr.Verify(macBytes); err != nil {
		t.Fatalf("Verify failed: %v", err)
	}

	// 2. Verify with valid preimage
	if err := mgr.VerifyWithPreimage(macBytes, preimage); err != nil {
		t.Fatalf("VerifyWithPreimage failed: %v", err)
	}
}

func TestVerifyWithPreimage_Mismatch(t *testing.T) {
	rootKey := []byte("12345678901234567890123456789012")
	mgr := NewManager(rootKey)

	preimage := make([]byte, 32)
	rand.Read(preimage)
	paymentHash := sha256.Sum256(preimage)

	macBytes, err := mgr.CreateMacaroon(paymentHash[:], 5*time.Minute)
	if err != nil {
		t.Fatalf("CreateMacaroon failed: %v", err)
	}

	// Wrong preimage of correct length (32 bytes)
	wrongPreimage := make([]byte, 32)
	rand.Read(wrongPreimage)

	err = mgr.VerifyWithPreimage(macBytes, wrongPreimage)
	if err == nil {
		t.Fatal("expected error on mismatched preimage, got nil")
	}
	if !strings.Contains(err.Error(), "preimage does not match payment hash") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestVerifyWithPreimage_SlicePanicGuards(t *testing.T) {
	rootKey := []byte("12345678901234567890123456789012")
	mgr := NewManager(rootKey)

	preimage := make([]byte, 32)
	rand.Read(preimage)
	paymentHash := sha256.Sum256(preimage)

	macBytes, err := mgr.CreateMacaroon(paymentHash[:], 5*time.Minute)
	if err != nil {
		t.Fatalf("CreateMacaroon failed: %v", err)
	}

	// Test attacker-controlled preimages of invalid lengths: 0, 1, 4, 16, 31, 33, 64 bytes
	testLengths := []int{0, 1, 2, 4, 16, 31, 33, 64}
	for _, l := range testLengths {
		attackerPreimage := make([]byte, l)
		err := mgr.VerifyWithPreimage(macBytes, attackerPreimage)
		if err == nil {
			t.Errorf("expected error for preimage of length %d, got nil", l)
		}
		if !strings.Contains(err.Error(), "invalid preimage: expected 32 bytes") {
			t.Errorf("for length %d, unexpected error: %v", l, err)
		}
	}
}

func TestExpiredMacaroon(t *testing.T) {
	rootKey := []byte("12345678901234567890123456789012")
	mgr := NewManager(rootKey)

	preimage := make([]byte, 32)
	rand.Read(preimage)
	paymentHash := sha256.Sum256(preimage)

	// Negative TTL -> immediately expired
	macBytes, err := mgr.CreateMacaroon(paymentHash[:], -1*time.Second)
	if err != nil {
		t.Fatalf("CreateMacaroon failed: %v", err)
	}

	err = mgr.Verify(macBytes)
	if err == nil {
		t.Fatal("expected error for expired macaroon, got nil")
	}
	if !strings.Contains(err.Error(), "macaroon expired") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestExtractPaymentHash(t *testing.T) {
	rootKey := []byte("12345678901234567890123456789012")
	mgr := NewManager(rootKey)

	preimage := make([]byte, 32)
	rand.Read(preimage)
	paymentHash := sha256.Sum256(preimage)

	macBytes, err := mgr.CreateMacaroon(paymentHash[:], 5*time.Minute)
	if err != nil {
		t.Fatalf("CreateMacaroon failed: %v", err)
	}

	extracted, err := mgr.ExtractPaymentHash(macBytes)
	if err != nil {
		t.Fatalf("ExtractPaymentHash failed: %v", err)
	}

	if hex.EncodeToString(extracted) != hex.EncodeToString(paymentHash[:]) {
		t.Fatalf("extracted hash %x != expected %x", extracted, paymentHash[:])
	}
}
