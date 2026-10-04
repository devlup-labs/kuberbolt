// Package brain contains the Financial Pod's private client for its local
// compute service. The public payment gRPC port never exposes this endpoint.
package brain

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

type Client interface {
	Compute(ctx context.Context, serviceKind string, jobSpec []byte) ([]byte, error)
}

type HTTPClient struct {
	url    string
	client *http.Client
}

func NewHTTPClient(baseURL string) (*HTTPClient, error) {
	if strings.TrimSpace(baseURL) == "" {
		return nil, fmt.Errorf("brain: URL is required")
	}
	return &HTTPClient{url: strings.TrimRight(baseURL, "/") + "/compute", client: &http.Client{Timeout: 60 * time.Second}}, nil
}

type computeRequest struct {
	ServiceKind string `json:"service_kind"`
	JobSpec     string `json:"job_spec_base64"`
}
type computeResponse struct {
	Output string `json:"output_data_base64"`
	Error  string `json:"error"`
}

func (c *HTTPClient) Compute(ctx context.Context, serviceKind string, jobSpec []byte) ([]byte, error) {
	payload, err := json.Marshal(computeRequest{ServiceKind: serviceKind, JobSpec: base64.StdEncoding.EncodeToString(jobSpec)})
	if err != nil {
		return nil, fmt.Errorf("brain: encode request: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.url, bytes.NewReader(payload))
	if err != nil {
		return nil, fmt.Errorf("brain: create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("brain: call compute: %w", err)
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return nil, fmt.Errorf("brain: read response: %w", err)
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("brain: compute returned HTTP %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}
	var result computeResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("brain: decode response: %w", err)
	}
	if result.Error != "" {
		return nil, fmt.Errorf("brain: %s", result.Error)
	}
	output, err := base64.StdEncoding.DecodeString(result.Output)
	if err != nil {
		return nil, fmt.Errorf("brain: decode output: %w", err)
	}
	return output, nil
}
