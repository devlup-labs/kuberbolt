package l402

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strconv"
	"strings"
	"time"

	"gopkg.in/macaroon.v2"
)

// Manager creates and verifies L402 macaroons bound to LND payment hashes.
type Manager struct {
	rootKey []byte
}

// NewManager creates a Manager with the given 32-byte root signing key.
// The root key must be persisted across restarts; if it changes, all
// previously issued macaroons become invalid.
func NewManager(rootKey []byte) *Manager {
	return &Manager{rootKey: rootKey}
}

// CreateMacaroon bakes a macaroon bound to a specific payment hash.
// Two first-party caveats are added:
//   - "time < <unix_timestamp>"  — enforces expiry
//   - "account = <hex_hash>"    — binds to the payment hash so the
//     macaroon is useless without the matching preimage
func (m *Manager) CreateMacaroon(paymentHash []byte, ttl time.Duration) ([]byte, error) {
	mac, err := macaroon.New(m.rootKey, paymentHash, "kuberbolt", macaroon.LatestVersion)
	if err != nil {
		return nil, fmt.Errorf("l402: macaroon.New: %w", err)
	}

	expiresAt := time.Now().Add(ttl).Unix()
	if err := mac.AddFirstPartyCaveat([]byte(
		fmt.Sprintf("time < %d", expiresAt),
	)); err != nil {
		return nil, fmt.Errorf("l402: add time caveat: %w", err)
	}

	if err := mac.AddFirstPartyCaveat([]byte(
		fmt.Sprintf("account = %s", hex.EncodeToString(paymentHash)),
	)); err != nil {
		return nil, fmt.Errorf("l402: add account caveat: %w", err)
	}

	raw, err := mac.MarshalBinary()
	if err != nil {
		return nil, fmt.Errorf("l402: marshal: %w", err)
	}
	return raw, nil
}

// Verify checks the HMAC chain and both caveats of a macaroon.
// It does NOT check the preimage — use VerifyWithPreimage for the full check.
func (m *Manager) Verify(macBytes []byte) error {
	mac := &macaroon.Macaroon{}
	if err := mac.UnmarshalBinary(macBytes); err != nil {
		return fmt.Errorf("l402: unmarshal: %w", err)
	}

	caveatChecker := func(caveat string) error {
		return m.checkCaveat(caveat, nil)
	}

	if err := mac.Verify(m.rootKey, caveatChecker, nil); err != nil {
		return fmt.Errorf("l402: HMAC verification failed: %w", err)
	}
	return nil
}

// VerifyWithPreimage performs the full L402 verification:
//  1. Checks HMAC chain integrity
//  2. Checks "time < X" caveat — rejects expired macaroons
//  3. Checks "account = Y" caveat — verifies SHA256(preimage) == Y
//
// This is the function called by the L402 interceptor on authenticated requests.
func (m *Manager) VerifyWithPreimage(macBytes []byte, preimage []byte) error {
	mac := &macaroon.Macaroon{}
	if err := mac.UnmarshalBinary(macBytes); err != nil {
		return fmt.Errorf("l402: unmarshal: %w", err)
	}

	caveatChecker := func(caveat string) error {
		return m.checkCaveat(caveat, preimage)
	}

	if err := mac.Verify(m.rootKey, caveatChecker, nil); err != nil {
		return fmt.Errorf("l402: verification failed: %w", err)
	}
	return nil
}

// ExtractPaymentHash extracts the payment hash from the "account" caveat.
// Returns the hash bytes or an error if the caveat is missing or malformed.
func (m *Manager) ExtractPaymentHash(macBytes []byte) ([]byte, error) {
	mac := &macaroon.Macaroon{}
	if err := mac.UnmarshalBinary(macBytes); err != nil {
		return nil, fmt.Errorf("l402: unmarshal: %w", err)
	}

	for _, cav := range mac.Caveats() {
		cavStr := string(cav.Id)
		if strings.HasPrefix(cavStr, "account = ") {
			hexHash := strings.TrimPrefix(cavStr, "account = ")
			hashBytes, err := hex.DecodeString(hexHash)
			if err != nil {
				return nil, fmt.Errorf("l402: malformed account caveat: %w", err)
			}
			return hashBytes, nil
		}
	}
	return nil, fmt.Errorf("l402: no account caveat found")
}

// checkCaveat validates a single first-party caveat string.
// preimage may be nil when only checking expiry (not the full flow).
func (m *Manager) checkCaveat(caveat string, preimage []byte) error {
	// "time < <unix_timestamp>"
	if strings.HasPrefix(caveat, "time < ") {
		expiryStr := strings.TrimPrefix(caveat, "time < ")
		expiry, err := strconv.ParseInt(expiryStr, 10, 64)
		if err != nil {
			return fmt.Errorf("malformed time caveat: %w", err)
		}
		if time.Now().Unix() >= expiry {
			return fmt.Errorf("macaroon expired at %d (now: %d)", expiry, time.Now().Unix())
		}
		return nil
	}

	// "account = <hex_payment_hash>"
	if strings.HasPrefix(caveat, "account = ") {
		hexHash := strings.TrimPrefix(caveat, "account = ")
		paymentHash, err := hex.DecodeString(hexHash)
		if err != nil {
			return fmt.Errorf("malformed account caveat: %w", err)
		}

		// If preimage is provided, verify SHA256(preimage) == paymentHash.
		if preimage != nil {
			// Guard: reject before any slice indexing. A short or zero-length
			// preimage from a forged/malformed request would panic at [:4].
			if len(preimage) != 32 {
				return fmt.Errorf("invalid preimage: expected 32 bytes, got %d", len(preimage))
			}
			computed := sha256.Sum256(preimage)
			computedHex := hex.EncodeToString(computed[:])
			if computedHex != hexHash {
				// No attacker-controlled data in error strings.
				return fmt.Errorf("preimage does not match payment hash")
			}
		}
		_ = paymentHash
		return nil
	}

	return fmt.Errorf("unknown caveat: %q", caveat)
}