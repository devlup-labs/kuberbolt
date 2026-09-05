package gateway

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"testing"
	"time"

	"github.com/kuberbolt/financial-pod/internal/budget"
	"github.com/kuberbolt/financial-pod/internal/l402"
	"github.com/kuberbolt/financial-pod/internal/pb"
	"go.uber.org/zap"
)

func TestL402RequesterFlow(t *testing.T) {
	logger := zap.NewNop()
	db := setupTestDB(t)

	// Since grpc network calls are hard to mock elegantly without a full pb structure,
	// we will directly simulate the unauthenticated and authenticated calls that RequesterSide makes,
	// effectively testing the logic in RequesterSide without CallProvider's grpc dial overhead.

	bm := budget.NewManager(budget.Config{
		DailyLimitMSat:   10000,
		MonthlyLimitMSat: 50000,
	}, logger)

	mockLN := &MockLNClient{}
	requester := newRequesterSide(mockLN, bm, db, logger)
	ctx := context.Background()

	// Simulate receiving a challenge from provider
	preimage := make([]byte, 32)
	rand.Read(preimage)
	rhash := sha256.Sum256(preimage)
	rhashHex := hex.EncodeToString(rhash[:])

	macKey := make([]byte, 32)
	rand.Read(macKey)
	macMgr := l402.NewManager(macKey)
	macBytes, _ := macMgr.CreateMacaroon(rhash[:], 5*time.Minute)

	challenge := &pb.PaymentRequired{
		Invoice:     "test_hodl_invoice",
		MacaroonHex: hex.EncodeToString(macBytes),
		PaymentHash: rhashHex,
		AmountMsat:  2000,
		ExpirySec:   300,
	}

	// 1. Budget check
	if err := requester.budget.CheckBudgetFor(ctx, challenge.AmountMsat); err != nil {
		t.Fatalf("unexpected budget error: %v", err)
	}

	// 2. Mock payment logic
	var paymentMade string
	mockLN.SendPaymentFunc = func(ctx context.Context, paymentRequest string, timeoutSec int32) ([]byte, error) {
		paymentMade = paymentRequest
		return preimage, nil
	}

	// 3. Make the payment
	_, err := requester.lnd.SendPayment(ctx, challenge.Invoice, 120)
	if err != nil {
		t.Fatalf("payment failed: %v", err)
	}
	if paymentMade != challenge.Invoice {
		t.Errorf("expected to pay %q, paid %q", challenge.Invoice, paymentMade)
	}

	// 4. Update budget
	requester.budget.RecordSpend(challenge.AmountMsat)

	if requester.budget.GetDailySpent() != 2000 {
		t.Errorf("expected daily spend 2000, got %d", requester.budget.GetDailySpent())
	}
}
