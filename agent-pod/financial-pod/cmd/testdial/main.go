package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os/exec"
	"time"

	"github.com/kuberbolt/financial-pod/internal/pb"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

func main() {
	targetFlag := flag.String("target", "127.0.0.1:6001", "gRPC server target host:port")
	promptFlag := flag.String("prompt", "The Lightning Network is a second-layer payment protocol that enables instant, low-cost off-chain micropayments.", "Text prompt to summarize")
	jsonFlag := flag.Bool("json", false, "Output machine-readable JSON")
	flag.Parse()

	target := *targetFlag
	prompt := *promptFlag

	if !*jsonFlag {
		fmt.Printf("⚡ [gRPC CLIENT] Connecting to Financial Pod at %s...\n", target)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	conn, err := grpc.DialContext(ctx, target,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithBlock(),
	)
	if err != nil {
		if *jsonFlag {
			res, _ := json.Marshal(map[string]any{"success": false, "error": fmt.Sprintf("dial failed: %v", err)})
			fmt.Println(string(res))
		} else {
			fmt.Printf("❌ Dial failed: %v\n", err)
		}
		return
	}
	defer conn.Close()

	if !*jsonFlag {
		fmt.Println(" Connected to Financial Pod!")
	}

	client := pb.NewFinancialPodServiceClient(conn)

	// Step 1: Send unauthenticated CallService
	if !*jsonFlag {
		fmt.Println("\n>>> [Step 1] Sending Unauthenticated CallService -> Expecting L402 Challenge...")
	}
	callCtx, callCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer callCancel()

	jobSpecJSON, _ := json.Marshal(map[string]string{
		"text": prompt,
	})

	_, err = client.CallService(callCtx, &pb.CallServiceRequest{
		ServiceKind: "text-summarization",
		JobSpec:     jobSpecJSON,
	})

	var challenge *pb.PaymentRequired
	if err != nil {
		st, ok := status.FromError(err)
		if ok {
			for _, detail := range st.Details() {
				if ch, ok := detail.(*pb.PaymentRequired); ok {
					challenge = ch
					break
				}
			}
		}
	}

	if challenge == nil {
		if *jsonFlag {
			res, _ := json.Marshal(map[string]any{"success": false, "error": fmt.Sprintf("expected L402 challenge, got: %v", err)})
			fmt.Println(string(res))
		} else {
			fmt.Printf("❌ Failed to get PaymentRequired challenge: %v\n", err)
		}
		return
	}

	if !*jsonFlag {
		fmt.Printf(">>> [Step 1 SUCCESS] Received L402 Challenge:\n")
		fmt.Printf("    Invoice:      %s...\n", challenge.Invoice[:30])
		fmt.Printf("    Payment Hash: %s\n", challenge.PaymentHash)
		fmt.Printf("    Amount:       %d sats\n", challenge.AmountMsat/1000)
		fmt.Printf("    Macaroon:     %s...\n", challenge.MacaroonHex[:24])
		fmt.Println("\n>>> [Step 2] Paying HODL invoice from Alice via Lightning Channel...")
	}

	// Step 2: Pay the invoice asynchronously via Alice (Lightning channel)
	go func() {
		exec.Command("docker", "exec", "alice", "lncli", "--network=regtest", "payinvoice", "--force", challenge.Invoice).CombinedOutput()
	}()

	// Wait 1.5s for HTLC to route and be accepted by Bob's node
	if !*jsonFlag {
		fmt.Println(">>> Waiting for HTLC to route and lock in channel...")
	}
	time.Sleep(1500 * time.Millisecond)

	// Step 3: Send Authenticated CallService with MacaroonHex
	if !*jsonFlag {
		fmt.Println("\n>>> [Step 3] Sending Authenticated CallService with MacaroonHex...")
	}
	authCtx, authCancel := context.WithTimeout(context.Background(), 25*time.Second)
	defer authCancel()

	authResp, err := client.CallService(authCtx, &pb.CallServiceRequest{
		ServiceKind: "text-summarization",
		JobSpec:     jobSpecJSON,
		MacaroonHex: challenge.MacaroonHex,
	})
	if err != nil {
		if *jsonFlag {
			res, _ := json.Marshal(map[string]any{"success": false, "error": fmt.Sprintf("authenticated call failed: %v", err)})
			fmt.Println(string(res))
		} else {
			fmt.Printf("❌ [Step 3 ERROR] Authenticated CallService failed: %v\n", err)
		}
		return
	}

	var outputParsed any
	if jsonErr := json.Unmarshal(authResp.OutputData, &outputParsed); jsonErr != nil {
		outputParsed = string(authResp.OutputData)
	}

	if *jsonFlag {
		res, _ := json.Marshal(map[string]any{
			"success":      true,
			"invoice":      challenge.Invoice,
			"payment_hash": challenge.PaymentHash,
			"amount_sats":  challenge.AmountMsat / 1000,
			"status":       authResp.Status,
			"output":       outputParsed,
		})
		fmt.Println(string(res))
	} else {
		fmt.Printf("\n>>> [Step 3 SUCCESS] Compute Result received from Financial Pod!\n")
		fmt.Printf("    Status: %s\n", authResp.Status)
		cleanOutput, _ := json.MarshalIndent(outputParsed, "    ", "  ")
		fmt.Printf("    Output: %s\n", string(cleanOutput))
	}
}
