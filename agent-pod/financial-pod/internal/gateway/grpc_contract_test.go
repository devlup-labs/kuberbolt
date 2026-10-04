package gateway

import (
	"context"
	"net"
	"testing"

	"github.com/kuberbolt/financial-pod/internal/pb"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/test/bufconn"
)

// contractServer exercises the generated service registration used by Server.
// It proves a payment challenge survives an actual gRPC connection rather than
// relying on a Go-only error type.
type contractServer struct {
	pb.UnimplementedFinancialPodServiceServer
}

func (contractServer) CallService(context.Context, *pb.CallServiceRequest) (*pb.CallServiceResponse, error) {
	return nil, paymentRequiredStatus(&ErrPaymentRequired{
		Invoice: "lnbc-test", MacaroonHex: "deadbeef", PaymentHash: "hash", AmountMSat: 1000, ExpirySec: 120,
	})
}

func TestPaymentChallengeCrossesGRPCBoundary(t *testing.T) {
	lis := bufconn.Listen(1024 * 1024)
	server := grpc.NewServer()
	pb.RegisterFinancialPodServiceServer(server, contractServer{})
	go func() { _ = server.Serve(lis) }()
	t.Cleanup(server.Stop)

	conn, err := grpc.DialContext(context.Background(), "bufnet",
		grpc.WithContextDialer(func(context.Context, string) (net.Conn, error) { return lis.Dial() }),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil { t.Fatalf("dial: %v", err) }
	t.Cleanup(func() { _ = conn.Close() })

	_, err = pb.NewFinancialPodServiceClient(conn).CallService(context.Background(), &pb.CallServiceRequest{})
	if err == nil { t.Fatal("expected payment challenge") }
	challenge, err := parsePaymentRequired(err)
	if err != nil { t.Fatalf("parse payment challenge: %v", err) }
	if challenge.Invoice != "lnbc-test" || challenge.AmountMsat != 1000 || challenge.MacaroonHex != "deadbeef" {
		t.Fatalf("unexpected challenge: %#v", challenge)
	}
}
