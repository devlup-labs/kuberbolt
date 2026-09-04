package ln

import (
	"context"
	"crypto/x509"
	"encoding/hex"
	"fmt"
	"os"

	"github.com/lightningnetwork/lnd/lnrpc"
	"github.com/lightningnetwork/lnd/lnrpc/invoicesrpc"
	"github.com/lightningnetwork/lnd/lnrpc/routerrpc"
	"go.uber.org/zap"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/metadata"
)

// InvoiceState represents the state of a Lightning invoice.
type InvoiceState int32

const (
	InvoiceOpen      InvoiceState = 0
	InvoiceSettled   InvoiceState = 1
	InvoiceCancelled InvoiceState = 2
	InvoiceAccepted  InvoiceState = 3
)

// Config holds all connection parameters for a single LND node.
type Config struct {
	Host        string
	GRPCPort    int
	TLSCertPath string
	MacaroonPath string
}

// macaroonCred injects the admin macaroon into every outgoing gRPC call.
// It implements google.golang.org/grpc/credentials.PerRPCCredentials.
type macaroonCred struct {
	hexMacaroon string
}

func (m macaroonCred) GetRequestMetadata(_ context.Context, _ ...string) (map[string]string, error) {
	return map[string]string{"macaroon": m.hexMacaroon}, nil
}

func (m macaroonCred) RequireTransportSecurity() bool { return true }

// Client is a fully authenticated gRPC client to a single LND node.
// It exposes only the operations the Financial Pod needs.
type Client struct {
	cfg    *Config
	logger *zap.Logger

	conn      *grpc.ClientConn
	Lightning lnrpc.LightningClient
	Invoices  invoicesrpc.InvoicesClient
	Router    routerrpc.RouterClient
}

// NewClient creates and connects a Client. Returns error if TLS cert or
// macaroon cannot be read, or if the initial GetInfo call fails.
func NewClient(ctx context.Context, cfg *Config, logger *zap.Logger) (*Client, error) {
	// 1. Load TLS certificate from disk.
	tlsBytes, err := os.ReadFile(cfg.TLSCertPath)
	if err != nil {
		return nil, fmt.Errorf("ln: read TLS cert %q: %w", cfg.TLSCertPath, err)
	}
	certPool := x509.NewCertPool()
	if !certPool.AppendCertsFromPEM(tlsBytes) {
		return nil, fmt.Errorf("ln: failed to parse TLS cert from %q", cfg.TLSCertPath)
	}
	tlsCreds := credentials.NewClientTLSFromCert(certPool, "")

	// 2. Load macaroon from disk and hex-encode.
	macBytes, err := os.ReadFile(cfg.MacaroonPath)
	if err != nil {
		return nil, fmt.Errorf("ln: read macaroon %q: %w", cfg.MacaroonPath, err)
	}
	macHex := hex.EncodeToString(macBytes)

	// 3. Dial LND with TLS transport + per-RPC macaroon credential.
	addr := fmt.Sprintf("%s:%d", cfg.Host, cfg.GRPCPort)
	conn, err := grpc.DialContext(
		ctx,
		addr,
		grpc.WithTransportCredentials(tlsCreds),
		grpc.WithPerRPCCredentials(macaroonCred{hexMacaroon: macHex}),
		grpc.WithBlock(),
	)
	if err != nil {
		return nil, fmt.Errorf("ln: dial %s: %w", addr, err)
	}

	c := &Client{
		cfg:       cfg,
		logger:    logger,
		conn:      conn,
		Lightning: lnrpc.NewLightningClient(conn),
		Invoices:  invoicesrpc.NewInvoicesClient(conn),
		Router:    routerrpc.NewRouterClient(conn),
	}

	// 4. Verify connection with GetInfo.
	info, err := c.Lightning.GetInfo(ctx, &lnrpc.GetInfoRequest{})
	if err != nil {
		conn.Close()
		return nil, fmt.Errorf("ln: GetInfo failed (wrong credentials?): %w", err)
	}
	logger.Info("connected to LND",
		zap.String("alias", info.Alias),
		zap.String("pubkey", info.IdentityPubkey),
		zap.String("version", info.Version),
		zap.Bool("synced", info.SyncedToChain),
	)

	return c, nil
}

// GetInfo returns basic node information.
func (c *Client) GetInfo(ctx context.Context) (*lnrpc.GetInfoResponse, error) {
	return c.Lightning.GetInfo(ctx, &lnrpc.GetInfoRequest{})
}

// AddHoldInvoice creates a HODL invoice on this LND node.
// The rhash is the SHA256 of the preimage — LND does NOT receive the preimage here.
// Funds are locked when the HTLC arrives; they are not settled until SettleInvoice is called.
func (c *Client) AddHoldInvoice(ctx context.Context, rhash []byte, amountMSat int64, expirySec int64, memo string) (paymentRequest string, err error) {
	resp, err := c.Invoices.AddHoldInvoice(ctx, &invoicesrpc.AddHoldInvoiceRequest{
		Hash:      rhash,
		ValueMsat: amountMSat,
		Expiry:    expirySec,
		Memo:      memo,
	})
	if err != nil {
		return "", fmt.Errorf("ln: AddHoldInvoice: %w", err)
	}
	return resp.PaymentRequest, nil
}

// InvoiceUpdate is sent over the channel returned by SubscribeSingleInvoice.
type InvoiceUpdate struct {
	State   InvoiceState
	RHash   []byte
	AmtMSat int64
	Err     error
}

// ClientInterface defines the LND operations the Financial Pod depends on.
// Using an interface here (instead of *Client directly) allows the gateway
// layer to be tested with a mock without a live LND connection.
type ClientInterface interface {
	AddHoldInvoice(ctx context.Context, rhash []byte, amountMSat int64, expirySec int64, memo string) (string, error)
	SubscribeSingleInvoice(ctx context.Context, rhash []byte) (<-chan InvoiceUpdate, error)
	SettleInvoice(ctx context.Context, preimage []byte) error
	CancelInvoice(ctx context.Context, paymentHash []byte) error
	SendPayment(ctx context.Context, paymentRequest string, timeoutSec int32) ([]byte, error)
	Close() error
}

// SubscribeSingleInvoice watches a specific invoice identified by rhash and
// sends state transitions over the returned channel. The caller must drain
// the channel; it is closed when ctx is cancelled or a terminal state is reached.
func (c *Client) SubscribeSingleInvoice(ctx context.Context, rhash []byte) (<-chan InvoiceUpdate, error) {
	stream, err := c.Invoices.SubscribeSingleInvoice(ctx, &invoicesrpc.SubscribeSingleInvoiceRequest{
		RHash: rhash,
	})
	if err != nil {
		return nil, fmt.Errorf("ln: SubscribeSingleInvoice: %w", err)
	}

	ch := make(chan InvoiceUpdate, 8)
	go func() {
		defer close(ch)
		for {
			inv, err := stream.Recv()
			if err != nil {
				ch <- InvoiceUpdate{Err: err}
				return
			}
			update := InvoiceUpdate{
				State:   InvoiceState(inv.State),
				RHash:   inv.RHash,
				AmtMSat: inv.AmtPaidMsat,
			}
			ch <- update
			if update.State == InvoiceSettled || update.State == InvoiceCancelled {
				return
			}
		}
	}()

	return ch, nil
}

// SettleInvoice reveals the preimage to LND, which settles the HTLC and
// transfers funds from the payer to this node. Must only be called after
// the invoice is in the ACCEPTED state (HTLC locked).
func (c *Client) SettleInvoice(ctx context.Context, preimage []byte) error {
	_, err := c.Invoices.SettleInvoice(ctx, &invoicesrpc.SettleInvoiceMsg{
		Preimage: preimage,
	})
	if err != nil {
		return fmt.Errorf("ln: SettleInvoice: %w", err)
	}
	return nil
}

// CancelInvoice cancels a HODL invoice, releasing locked HTLCs back to the payer.
// Safe to call if compute failed or timed out.
func (c *Client) CancelInvoice(ctx context.Context, paymentHash []byte) error {
	_, err := c.Invoices.CancelInvoice(ctx, &invoicesrpc.CancelInvoiceMsg{
		PaymentHash: paymentHash,
	})
	if err != nil {
		return fmt.Errorf("ln: CancelInvoice: %w", err)
	}
	return nil
}

// SendPayment pays a BOLT11 invoice. For HODL invoices this call blocks until
// the provider calls SettleInvoice or CancelInvoice (or timeout expires).
// Returns the payment preimage on success.
func (c *Client) SendPayment(ctx context.Context, paymentRequest string, timeoutSec int32) (preimage []byte, err error) {
	stream, err := c.Router.SendPaymentV2(ctx, &routerrpc.SendPaymentRequest{
		PaymentRequest: paymentRequest,
		TimeoutSeconds: int32(timeoutSec),
		FeeLimitMsat:   int64(10_000), // 10 sat fee limit
	})
	if err != nil {
		return nil, fmt.Errorf("ln: SendPaymentV2: %w", err)
	}

	for {
		update, err := stream.Recv()
		if err != nil {
			return nil, fmt.Errorf("ln: payment stream error: %w", err)
		}
		switch update.Status {
		case lnrpc.Payment_IN_FLIGHT:
			c.logger.Debug("payment in flight",
				zap.String("hash", update.PaymentHash))
		case lnrpc.Payment_SUCCEEDED:
			c.logger.Info("payment succeeded",
				zap.String("hash", update.PaymentHash),
				zap.Int64("amount_msat", update.ValueMsat))
			preimage, err := hex.DecodeString(update.PaymentPreimage)
			if err != nil {
				return nil, fmt.Errorf("ln: failed to decode preimage: %w", err)
			}
			return preimage, nil
		case lnrpc.Payment_FAILED:
			return nil, fmt.Errorf("ln: payment failed: %s", update.FailureReason)
		}
	}
}

// ListChannels returns all active channels on this node.
func (c *Client) ListChannels(ctx context.Context) ([]*lnrpc.Channel, error) {
	resp, err := c.Lightning.ListChannels(ctx, &lnrpc.ListChannelsRequest{
		ActiveOnly: true,
	})
	if err != nil {
		return nil, fmt.Errorf("ln: ListChannels: %w", err)
	}
	return resp.Channels, nil
}

// Close shuts down the gRPC connection.
func (c *Client) Close() error {
	if c.conn != nil {
		return c.conn.Close()
	}
	return nil
}

// AppendMacaroonToCtx adds the node's macaroon to an outgoing gRPC context.
// Used when the FP calls another FP's gRPC service.
func AppendMacaroonToCtx(ctx context.Context, macHex string) context.Context {
	return metadata.AppendToOutgoingContext(ctx, "macaroon", macHex)
}