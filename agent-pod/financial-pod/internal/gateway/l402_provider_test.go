package gateway

import (
	"context"
	"crypto/rand"
	"testing"

	"github.com/kuberbolt/financial-pod/internal/cache"
	"github.com/kuberbolt/financial-pod/internal/l402"
	"github.com/kuberbolt/financial-pod/internal/ln"
	"github.com/kuberbolt/financial-pod/internal/pb"
	"go.uber.org/zap"
)

func TestL402ProviderFlow(t *testing.T) {
	logger := zap.NewNop()
	db := setupTestDB(t)

	mockLN := &MockLNClient{}

	macKey := make([]byte, 32)
	rand.Read(macKey)
	macMgr := l402.NewManager(macKey)
	invoices := cache.New()

	provider := newProviderSide(mockLN, macMgr, invoices, db, 1000, logger)

	ctx := context.Background()
	req := &pb.CallServiceRequest{}

	// Phase 1: Unauthenticated request should return 402 challenge
	resp, err := provider.HandleCallService(ctx, req)
	if resp != nil {
		t.Fatalf("expected nil response for unauthenticated request, got %v", resp)
	}
	pErr, ok := err.(*ErrPaymentRequired)
	if !ok {
		t.Fatalf("expected ErrPaymentRequired, got %T: %v", err, err)
	}
	if pErr.Invoice != "mock_invoice" {
		t.Errorf("expected invoice 'mock_invoice', got %q", pErr.Invoice)
	}
	if pErr.AmountMSat != 1000 {
		t.Errorf("expected amount 1000, got %d", pErr.AmountMSat)
	}

	cached := invoices.GetByRHash(pErr.PaymentHash)
	if cached == nil {
		t.Fatalf("expected invoice in cache for rhash %s", pErr.PaymentHash)
	}

	// Phase 2: Authenticated request
	mockLN.SubscribeSingleInvoiceFunc = func(ctx context.Context, rhash []byte) (<-chan ln.InvoiceUpdate, error) {
		ch := make(chan ln.InvoiceUpdate, 1)
		ch <- ln.InvoiceUpdate{
			State:   ln.InvoiceAccepted,
			RHash:   rhash,
			AmtMSat: 1000,
		}
		close(ch)
		return ch, nil
	}

	var settledPreimage []byte
	mockLN.SettleInvoiceFunc = func(ctx context.Context, preimage []byte) error {
		settledPreimage = preimage
		return nil
	}

	authReq := &pb.CallServiceRequest{
		JobSpec:     []byte("test_job"),
		MacaroonHex: pErr.MacaroonHex,
		// No PreimageHex — provider confirms payment via LND HTLC state,
		// not by client-supplied preimage.
	}

	authResp, authErr := provider.HandleCallService(ctx, authReq)
	if authErr != nil {
		t.Fatalf("authenticated request failed: %v", authErr)
	}
	if authResp.Status != "success" {
		t.Errorf("expected status 'success', got %q", authResp.Status)
	}
	if string(authResp.OutputData) != "test_job" {
		t.Errorf("expected OutputData 'test_job', got %q", string(authResp.OutputData))
	}

	if string(settledPreimage) != string(cached.Preimage) {
		t.Errorf("settled preimage mismatch")
	}

	// Ensure cache is cleared
	if invoices.GetByRHash(pErr.PaymentHash) != nil {
		t.Errorf("cache was not cleared after settlement")
	}
}
