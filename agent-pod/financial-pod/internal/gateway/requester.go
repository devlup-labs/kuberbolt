package gateway

import (
	"context"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/kuberbolt/financial-pod/internal/budget"
	"github.com/kuberbolt/financial-pod/internal/ledger"
	"github.com/kuberbolt/financial-pod/internal/ln"
	"github.com/kuberbolt/financial-pod/internal/pb"
	"go.uber.org/zap"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// defaultPaymentTimeoutSec is how long SendPayment blocks waiting for HODL to settle.
const defaultPaymentTimeoutSec = 120

// RequesterSide handles all outbound service calls: detects 402 challenges,
// pays invoices, and retries with the macaroon credential.
type RequesterSide struct {
	lnd    ln.ClientInterface
	budget *budget.Manager
	db     *ledger.DB
	logger *zap.Logger
}

func newRequesterSide(
	lnd ln.ClientInterface,
	bm *budget.Manager,
	db *ledger.DB,
	logger *zap.Logger,
) *RequesterSide {
	return &RequesterSide{
		lnd:    lnd,
		budget: bm,
		db:     db,
		logger: logger,
	}
}

// CallProvider executes the corrected client-side HODL L402 flow:
//
//  1. Dial the provider's gRPC endpoint.
//  2. Send unauthenticated CallService → receive 402 with invoice + macaroon.
//  3. Check budget.
//  4. Start paying the HODL invoice in a background goroutine.
//     (SendPayment blocks until the provider settles — after compute succeeds.)
//  5. Immediately retry CallService with the macaroon only (no preimage needed).
//     The provider verifies the HTLC is ACCEPTED, runs compute, then settles.
//  6. Wait for the payment goroutine to confirm settlement.
//  7. Return the compute result.
//
// Why send the authenticated retry before waiting for SendPayment?
// With HODL invoices the client can never know the preimage before the provider
// settles, and the provider only settles after compute — which only runs after
// it sees the authenticated retry. Sending the retry first breaks the deadlock.
func (r *RequesterSide) CallProvider(
	ctx context.Context,
	providerAddr string,
	req *pb.CallServiceRequest,
) (*pb.CallServiceResponse, error) {

	// 1. Dial provider FP (plain text for now; TLS between pods added in Phase 5).
	conn, err := grpc.DialContext(ctx, providerAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return nil, fmt.Errorf("requester: dial %s: %w", providerAddr, err)
	}
	defer conn.Close()

	// 2. Send unauthenticated request — expect a PaymentRequired error.
	challenge, err := r.sendUnauthenticated(ctx, conn, req)
	if err != nil {
		return nil, fmt.Errorf("requester: unauthenticated call: %w", err)
	}

	r.logger.Info("received L402 challenge",
		zap.String("payment_hash", shortStr(challenge.PaymentHash, 12)),
		zap.Int64("amount_msat", challenge.AmountMsat),
	)

	// 3. Check budget before committing to payment.
	if err := r.budget.CheckBudgetFor(ctx, challenge.AmountMsat); err != nil {
		return nil, fmt.Errorf("requester: budget check: %w", err)
	}

	// 4. Record pending outgoing payment.
	jobID := uuid.New().String()
	macaroonID := shortStr(challenge.MacaroonHex, 16)
	if err := r.db.RecordTransaction(&ledger.Transaction{
		JobID:              jobID,
		CounterpartyPubkey: providerAddr,
		Direction:          "outgoing",
		AmountMSat:         challenge.AmountMsat,
		InvoicePaymentHash: challenge.PaymentHash,
		MacaroonID:         macaroonID,
		Status:             "pending",
		CreatedAt:          time.Now(),
	}); err != nil {
		r.logger.Warn("failed to record pending outgoing transaction", zap.Error(err))
	}

	// 5. Pay the HODL invoice in a background goroutine.
	//    We MUST NOT block here: the provider settles the HODL only after it
	//    receives our authenticated retry (step 6 below). If we blocked here
	//    waiting for the preimage, we'd deadlock — the provider is waiting for
	//    us, and we'd be waiting for the provider.
	payErrCh := make(chan error, 1)
	go func() {
		r.logger.Info("paying HODL invoice in background",
			zap.String("payment_hash", shortStr(challenge.PaymentHash, 12)),
		)
		_, payErr := r.lnd.SendPayment(ctx, challenge.Invoice, defaultPaymentTimeoutSec)
		payErrCh <- payErr
	}()

	// 6. Immediately send the authenticated retry with the macaroon only.
	//    No preimage is included — the provider confirms payment by watching
	//    the LND invoice state for HTLC ACCEPTED (funds locked in channel).
	authReq := &pb.CallServiceRequest{
		ServiceKind: req.ServiceKind,
		JobSpec:     req.JobSpec,
		MacaroonHex: challenge.MacaroonHex,
	}
	result, err := r.sendAuthenticated(ctx, conn, authReq)
	if err != nil {
		// Provider rejected us or compute failed. Payment goroutine will
		// eventually time out; mark ledger accordingly.
		r.logger.Error("authenticated retry failed", zap.Error(err))
		_ = r.db.UpdateStatus(jobID, "expired")
		return nil, fmt.Errorf("requester: authenticated retry: %w", err)
	}

	// 7. Record spend in budget and mark ledger settled.
	r.budget.RecordSpend(challenge.AmountMsat)
	_ = r.db.UpdateStatus(jobID, "settled")

	r.logger.Info("CallProvider completed successfully",
		zap.String("job_id", jobID),
		zap.Int64("amount_msat", challenge.AmountMsat),
	)

	// 8. Wait for payment goroutine. The provider already called SettleInvoice,
	//    so SendPayment should return almost immediately here.
	select {
	case payErr := <-payErrCh:
		if payErr != nil {
			r.logger.Warn("background payment goroutine returned error",
				zap.String("job_id", jobID),
				zap.Error(payErr),
			)
		}
	case <-ctx.Done():
		r.logger.Warn("context cancelled while waiting for payment confirmation",
			zap.String("job_id", jobID),
		)
	}

	return result, nil
}

// sendUnauthenticated calls CallService without auth credentials and expects
// a PaymentRequired error back. Returns the parsed challenge or an error.
func (r *RequesterSide) sendUnauthenticated(
	ctx context.Context,
	conn *grpc.ClientConn,
	req *pb.CallServiceRequest,
) (*pb.PaymentRequired, error) {
	var challenge pb.PaymentRequired
	err := conn.Invoke(ctx, "/kuberbolt.v1.FinancialPodService/CallService", req, &challenge)
	if err == nil {
		return nil, fmt.Errorf("requester: expected 402 challenge, got success response")
	}

	parsed, parseErr := parsePaymentRequired(err)
	if parseErr != nil {
		return nil, fmt.Errorf("requester: unexpected error (not a 402): %w", err)
	}
	return parsed, nil
}

// sendAuthenticated retries the request with the macaroon credential.
func (r *RequesterSide) sendAuthenticated(
	ctx context.Context,
	conn *grpc.ClientConn,
	req *pb.CallServiceRequest,
) (*pb.CallServiceResponse, error) {
	var resp pb.CallServiceResponse
	err := conn.Invoke(ctx, "/kuberbolt.v1.FinancialPodService/CallService", req, &resp)
	if err != nil {
		return nil, fmt.Errorf("authenticated call failed: %w", err)
	}
	return &resp, nil
}

// parsePaymentRequired extracts PaymentRequired details from a gRPC error.
func parsePaymentRequired(err error) (*pb.PaymentRequired, error) {
	pErr, ok := err.(*ErrPaymentRequired)
	if !ok {
		return nil, fmt.Errorf("not a PaymentRequired error")
	}
	return &pb.PaymentRequired{
		Invoice:     pErr.Invoice,
		MacaroonHex: pErr.MacaroonHex,
		PaymentHash: pErr.PaymentHash,
		AmountMsat:  pErr.AmountMSat,
		ExpirySec:   pErr.ExpirySec,
	}, nil
}
