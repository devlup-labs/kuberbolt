package gateway

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"github.com/kuberbolt/financial-pod/internal/ledger"
	"github.com/kuberbolt/financial-pod/internal/ln"
)

// MockLNClient mocks the LND operations.
type MockLNClient struct {
	AddHoldInvoiceFunc         func(ctx context.Context, rhash []byte, amountMSat int64, expirySec int64, memo string) (string, error)
	SubscribeSingleInvoiceFunc func(ctx context.Context, rhash []byte) (<-chan ln.InvoiceUpdate, error)
	CancelInvoiceFunc          func(ctx context.Context, paymentHash []byte) error
	SettleInvoiceFunc          func(ctx context.Context, preimage []byte) error
	SendPaymentFunc            func(ctx context.Context, paymentRequest string, timeoutSec int32) ([]byte, error)
}

func (m *MockLNClient) AddHoldInvoice(ctx context.Context, rhash []byte, amountMSat int64, expirySec int64, memo string) (string, error) {
	if m.AddHoldInvoiceFunc != nil {
		return m.AddHoldInvoiceFunc(ctx, rhash, amountMSat, expirySec, memo)
	}
	return "mock_invoice", nil
}

func (m *MockLNClient) SubscribeSingleInvoice(ctx context.Context, rhash []byte) (<-chan ln.InvoiceUpdate, error) {
	if m.SubscribeSingleInvoiceFunc != nil {
		return m.SubscribeSingleInvoiceFunc(ctx, rhash)
	}
	ch := make(chan ln.InvoiceUpdate)
	close(ch)
	return ch, nil
}

func (m *MockLNClient) CancelInvoice(ctx context.Context, paymentHash []byte) error {
	if m.CancelInvoiceFunc != nil {
		return m.CancelInvoiceFunc(ctx, paymentHash)
	}
	return nil
}

func (m *MockLNClient) SettleInvoice(ctx context.Context, preimage []byte) error {
	if m.SettleInvoiceFunc != nil {
		return m.SettleInvoiceFunc(ctx, preimage)
	}
	return nil
}

func (m *MockLNClient) SendPayment(ctx context.Context, paymentRequest string, timeoutSec int32) ([]byte, error) {
	if m.SendPaymentFunc != nil {
		return m.SendPaymentFunc(ctx, paymentRequest, timeoutSec)
	}
	return []byte("mock_preimage"), nil
}

func (m *MockLNClient) Close() error { return nil }

func setupTestDB(t *testing.T) *ledger.DB {
	dir := t.TempDir()
	dbPath := filepath.Join(dir, "test_ledger.db")
	db, err := ledger.Open(dbPath)
	if err != nil {
		t.Fatalf("failed to open test db: %v", err)
	}
	t.Cleanup(func() {
		db.Close()
		os.Remove(dbPath)
	})
	return db
}
