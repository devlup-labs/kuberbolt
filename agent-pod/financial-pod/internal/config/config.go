package config

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/kuberbolt/financial-pod/internal/budget"
	"gopkg.in/yaml.v3"
)

// Config is the complete agent configuration loaded from config.yaml.
type Config struct {
	Agent     AgentConfig     `yaml:"agent"`
	Services  []ServiceConfig `yaml:"services"`
	Network   NetworkConfig   `yaml:"network"`
	Lightning LightningConfig `yaml:"lightning"`
	Budget    budget.Config   `yaml:"budget"`
	Logging   LoggingConfig   `yaml:"logging"`
}

type AgentConfig struct {
	Name         string `yaml:"name"`
	NostrNPub    string `yaml:"nostr_npub"`
	NostrPrivKey string `yaml:"nostr_priv_key"` // hex encoded, stored at 0600
	Role         string `yaml:"role"`
	CreatedAt    string `yaml:"created_at"`
}

type ServiceConfig struct {
	Name        string `yaml:"name"`
	Kind        int    `yaml:"kind"`
	Description string `yaml:"description"`
	PriceMSat   int64  `yaml:"price_msat"`
	TimeoutSec  int    `yaml:"timeout_sec"`
}

type NetworkConfig struct {
	GRPCPort    int      `yaml:"grpc_port"`
	PublicHost  string   `yaml:"public_host"`
	NostrRelays []string `yaml:"nostr_relays"`
}

type LightningConfig struct {
	Network      string `yaml:"network"`       // "regtest", "testnet", "mainnet"
	LNDHost      string `yaml:"lnd_host"`
	LNDGRPCPort  int    `yaml:"lnd_grpc_port"`
	TLSCertPath  string `yaml:"tls_cert_path"`
	MacaroonPath string `yaml:"macaroon_path"`
}

type LoggingConfig struct {
	Level  string `yaml:"level"`
	Format string `yaml:"format"`
}

// DefaultDir returns the agent's config directory (~/.kuberbolt/<name>/).
func DefaultDir(agentName string) string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".kuberbolt", agentName)
}

// Initialize creates a fresh config for a new agent, generates a Nostr keypair,
// and writes config.yaml to the default directory.
func Initialize(agentName string) (*Config, error) {
	if agentName == "" {
		return nil, fmt.Errorf("config: agent name must not be empty")
	}

	dir := DefaultDir(agentName)
	if err := os.MkdirAll(dir, 0700); err != nil {
		return nil, fmt.Errorf("config: mkdir %q: %w", dir, err)
	}

	// Generate a random Nostr private key (32 bytes = secp256k1 scalar).
	privKeyBytes := make([]byte, 32)
	if _, err := rand.Read(privKeyBytes); err != nil {
		return nil, fmt.Errorf("config: generate keypair: %w", err)
	}
	privKeyHex := hex.EncodeToString(privKeyBytes)

	cfg := &Config{
		Agent: AgentConfig{
			Name:         agentName,
			NostrPrivKey: privKeyHex,
			NostrNPub:    "", // SDK will compute and fill this in Phase 3
			Role:         "agent",
			CreatedAt:    time.Now().UTC().Format(time.RFC3339),
		},
		Network: NetworkConfig{
			GRPCPort:    6001,
			PublicHost:  "127.0.0.1",
			NostrRelays: []string{"ws://127.0.0.1:8008"},
		},
		Lightning: LightningConfig{
			Network:      "regtest",
			LNDHost:      "127.0.0.1",
			LNDGRPCPort:  10009,
			TLSCertPath:  filepath.Join(dir, "tls.cert"),
			MacaroonPath: filepath.Join(dir, "admin.macaroon"),
		},
		Budget: budget.Config{
			DailyLimitMSat:   100_000_000, // 100 000 sats
			MonthlyLimitMSat: 3_000_000_000,
		},
		Logging: LoggingConfig{
			Level:  "info",
			Format: "json",
		},
	}

	if err := Save(cfg, filepath.Join(dir, "config.yaml")); err != nil {
		return nil, err
	}
	return cfg, nil
}

// LoadFromFile reads and parses a config.yaml file.
func LoadFromFile(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("config: read %q: %w", path, err)
	}
	cfg := &Config{}
	if err := yaml.Unmarshal(data, cfg); err != nil {
		return nil, fmt.Errorf("config: parse %q: %w", path, err)
	}
	return cfg, nil
}

// LoadFromDefaultLocation loads config.yaml from ~/.kuberbolt/<name>/config.yaml.
func LoadFromDefaultLocation(agentName string) (*Config, error) {
	return LoadFromFile(filepath.Join(DefaultDir(agentName), "config.yaml"))
}

// Save marshals cfg to YAML and writes it to path at mode 0600.
func Save(cfg *Config, path string) error {
	data, err := yaml.Marshal(cfg)
	if err != nil {
		return fmt.Errorf("config: marshal: %w", err)
	}
	if err := os.WriteFile(path, data, 0600); err != nil {
		return fmt.Errorf("config: write %q: %w", path, err)
	}
	return nil
}