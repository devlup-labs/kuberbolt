package gateway

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/kuberbolt/financial-pod/internal/cache"
	"github.com/kuberbolt/financial-pod/internal/l402"
	"github.com/kuberbolt/financial-pod/internal/ledger"
	"github.com/kuberbolt/financial-pod/internal/ln"
	"github.com/kuberbolt/financial-pod/internal/pb"
	"go.uber.org/zap"
)

// defaultHODLExpiry is how long the provider waits for the client to pay
// before the invoice expires and the hold is released.
const defaultHODLExpiry = 3600 // seconds

// defaultInvoiceTTL is the lifetime of the L402 macaroon/invoice pair in the cache.
const defaultInvoiceTTL = 2 * time.Minute

// defaultHTLCTimeoutBlocks is the maximum blocks the HTLC may be in-flight.
const defaultHTLCTimeoutBlocks = 40

// ProviderSide handles all inbound service requests: issuing L402 challenges,
// watching for payment, running compute, and settling or cancelling the HODL.
type ProviderSide struct {
	lnd        ln.ClientInterface
	macManager *l402.Manager
	invoices   *cache.InvoiceCache
	db         *ledger.DB
	logger     *zap.Logger

	// servicePriceMSat is the price charged per CallService request.
	// In production this would vary per service kind.
	servicePriceMSat int64
}

func newProviderSide(
	lnd ln.ClientInterface,
	macManager *l402.Manager,
	invoices *cache.InvoiceCache,
	db *ledger.DB,
	servicePriceMSat int64,
	logger *zap.Logger,
) *ProviderSide {
	return &ProviderSide{
		lnd:              lnd,
		macManager:       macManager,
		invoices:         invoices,
		db:               db,
		servicePriceMSat: servicePriceMSat,
		logger:           logger,
	}
}

// HandleCallService is the entry point for every inbound CallService request.
// It implements the HODL L402 state machine:
//
//	 No macaroon → issue 402 challenge (HODL invoice + macaroon)
//	 Macaroon present → verify HMAC + wait for HTLC ACCEPTED → compute → settle
//
// Note: the client does NOT send a preimage on the authenticated retry.
// Payment is confirmed by watching the LND invoice state (HTLC ACCEPTED),
// not by a client-supplied preimage. This avoids the deadlock that would
// occur if the client tried to supply the preimage before compute completes.
func (p *ProviderSide) HandleCallService(
	ctx context.Context,
	req *pb.CallServiceRequest,
) (*pb.CallServiceResponse, error) {

	// ── UNAUTHENTICATED REQUEST ───────────────────────────────────────────
	if req.MacaroonHex == "" {
		return nil, p.issueL402Challenge(ctx)
	}

	// ── AUTHENTICATED REQUEST ─────────────────────────────────────────────
	return p.handleAuthenticatedRequest(ctx, req)
}

// issueL402Challenge creates a HODL invoice + macaroon and returns a
// PaymentRequired error. The caller (interceptor layer) converts this
// into a proper gRPC PermissionDenied status with details.
func (p *ProviderSide) issueL402Challenge(ctx context.Context) error {
	// 1. Generate a random 32-byte preimage. This is the secret.
	//    Only the provider FP ever knows this until settlement.
	preimage := make([]byte, 32)
	if _, err := rand.Read(preimage); err != nil {
		return fmt.Errorf("provider: generate preimage: %w", err)
	}
	rhash := sha256.Sum256(preimage)
	rhashBytes := rhash[:]
	rhashHex := hex.EncodeToString(rhashBytes)
	jobID := uuid.New().String()

	p.logger.Info("issuing L402 challenge",
		zap.String("job_id", jobID),
		zap.String("rhash", shortStr(rhashHex, 12)),
		zap.Int64("price_msat", p.servicePriceMSat),
	)

	// 2. Create the HODL invoice on LND with the hash (NOT the preimage).
	payReq, err := p.lnd.AddHoldInvoice(
		ctx,
		rhashBytes,
		p.servicePriceMSat,
		defaultHODLExpiry,
		fmt.Sprintf("kuberbolt job %s", jobID[:8]),
	)
	if err != nil {
		return fmt.Errorf("provider: AddHoldInvoice: %w", err)
	}

	// 3. Bake a macaroon bound to this payment hash.
	macBytes, err := p.macManager.CreateMacaroon(rhashBytes, defaultInvoiceTTL)
	if err != nil {
		return fmt.Errorf("provider: CreateMacaroon: %w", err)
	}
	macHex := hex.EncodeToString(macBytes)

	// 4. Store the preimage (secret) in the in-memory cache.
	p.invoices.Set(jobID, &cache.Entry{
		Invoice:       payReq,
		RHash:         rhashBytes,
		RHashHex:      rhashHex,
		Preimage:      preimage,
		MacaroonBytes: macBytes,
		CreatedAt:     time.Now(),
		ExpiresAt:     time.Now().Add(defaultInvoiceTTL),
	})

	// 5. Write a PENDING transaction to the ledger.
	if err := p.db.RecordTransaction(&ledger.Transaction{
		JobID:              jobID,
		CounterpartyPubkey: "unknown", // filled in on authenticated retry
		Direction:          "incoming",
		AmountMSat:         p.servicePriceMSat,
		InvoicePaymentHash: rhashHex,
		MacaroonID:         shortStr(macHex, 16),
		Status:             "pending",
		CreatedAt:          time.Now(),
	}); err != nil {
		p.logger.Warn("failed to record pending transaction", zap.Error(err))
	}

	// 6. Store the hold in the ledger for audit.
	if err := p.db.RecordPaymentHold(&ledger.PaymentHold{
		HoldID:            uuid.New().String(),
		RHash:             rhashHex,
		Preimage:          hex.EncodeToString(preimage),
		HTLCTimeoutBlocks: defaultHTLCTimeoutBlocks,
		JobID:             jobID,
	}); err != nil {
		p.logger.Warn("failed to record payment hold", zap.Error(err))
	}

	// 7. Return the challenge as a structured error. The gRPC interceptor
	//    wraps this into a PermissionDenied status with PaymentRequired details.
	return &ErrPaymentRequired{
		Invoice:     payReq,
		MacaroonHex: macHex,
		PaymentHash: rhashHex,
		AmountMSat:  p.servicePriceMSat,
		ExpirySec:   int32(defaultInvoiceTTL.Seconds()),
	}
}

// handleAuthenticatedRequest verifies the macaroon, waits for HTLC ACCEPTED,
// runs compute, then settles or cancels the HODL invoice.
//
// Payment confirmation comes from LND invoice state (HTLC ACCEPTED = funds
// locked in channel), NOT from a client-supplied preimage. This avoids the
// deadlock where the client blocks on SendPayment waiting for a preimage that
// only the provider can reveal after compute completes.
func (p *ProviderSide) handleAuthenticatedRequest(
	ctx context.Context,
	req *pb.CallServiceRequest,
) (*pb.CallServiceResponse, error) {

	// 1. Decode macaroon.
	macBytes, err := hex.DecodeString(req.MacaroonHex)
	if err != nil {
		return nil, fmt.Errorf("provider: decode macaroon: %w", err)
	}

	// 2. Verify macaroon HMAC chain + time caveat.
	//    We do NOT verify a preimage here — payment is confirmed via LND state.
	if err := p.macManager.Verify(macBytes); err != nil {
		return nil, fmt.Errorf("provider: macaroon verification failed: %w", err)
	}

	// 3. Extract the payment hash from the macaroon's account caveat.
	rhashBytes, err := p.macManager.ExtractPaymentHash(macBytes)
	if err != nil {
		return nil, fmt.Errorf("provider: extract payment hash: %w", err)
	}
	rhashHex := hex.EncodeToString(rhashBytes)

	// 4. Look up the cached entry (preimage + invoice) by rhash.
	cached := p.invoices.GetByRHash(rhashHex)
	if cached == nil {
		return nil, fmt.Errorf("provider: unknown or expired payment hash %s", shortStr(rhashHex, 12))
	}

	p.logger.Info("processing authenticated request",
		zap.String("rhash", shortStr(rhashHex, 12)),
	)

	// 5. Subscribe to invoice state — wait for HTLC ACCEPTED (funds locked).
	updates, err := p.lnd.SubscribeSingleInvoice(ctx, rhashBytes)
	if err != nil {
		return nil, fmt.Errorf("provider: subscribe invoice: %w", err)
	}

	htlcAccepted := false
	for update := range updates {
		if update.Err != nil {
			p.logger.Warn("invoice subscription error", zap.Error(update.Err))
			break
		}
		p.logger.Debug("invoice state update",
			zap.Int32("state", int32(update.State)),
		)
		if update.State == ln.InvoiceAccepted {
			htlcAccepted = true
			break
		}
		if update.State == ln.InvoiceCancelled {
			return nil, fmt.Errorf("provider: invoice cancelled by network")
		}
	}

	if !htlcAccepted {
		return nil, fmt.Errorf("provider: HTLC was not locked (payment not received)")
	}

	p.logger.Info("HTLC accepted — funds locked, running compute",
		zap.String("rhash", rhashHex[:12]+"…"),
	)

	// 7. Run compute. On failure → cancel invoice → client gets refund.
	result, computeErr := p.runCompute(ctx, req.JobSpec)
	if computeErr != nil {
		p.logger.Error("compute failed, cancelling HODL invoice",
			zap.Error(computeErr),
			zap.String("rhash", rhashHex[:12]+"…"),
		)
		if err := p.lnd.CancelInvoice(ctx, rhashBytes); err != nil {
			p.logger.Error("failed to cancel invoice after compute failure",
				zap.Error(err))
		}
		_ = p.db.UpdateStatus(cached.RHashHex, "cancelled")
		p.invoices.DeleteByRHash(cached.RHashHex)
		return nil, fmt.Errorf("provider: compute failed, invoice cancelled: %w", computeErr)
	}

	// 8. Compute succeeded → settle the HODL invoice (reveal preimage).
	if err := p.lnd.SettleInvoice(ctx, cached.Preimage); err != nil {
		p.logger.Error("failed to settle invoice after successful compute",
			zap.Error(err),
			zap.String("rhash", rhashHex[:12]+"…"),
		)
		// We cannot cancel here — compute was done. Log and return result anyway.
		// A retry of SettleInvoice should be added in production.
	} else {
		p.logger.Info("HODL invoice settled — funds received",
			zap.String("rhash", rhashHex[:12]+"…"),
		)
	}

	// 9. Update ledger to settled.
	_ = p.db.UpdateStatus(cached.RHashHex, "settled")
	p.invoices.DeleteByRHash(cached.RHashHex)

	return &pb.CallServiceResponse{
		OutputData: result,
		Status:     "success",
	}, nil
}

// runCompute is the stub that the Agent implements in production.
// For now it echoes the job spec back to demonstrate the flow works end-to-end.
func (p *ProviderSide) runCompute(_ context.Context, jobSpec []byte) ([]byte, error) {
	if len(jobSpec) == 0 {
		return []byte(`{"result":"ok","note":"empty job spec"}`), nil
	}
	// In production: forward jobSpec to the agent brain and wait for result.
	return jobSpec, nil
}
