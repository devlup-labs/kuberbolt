package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/kuberbolt/financial-pod/internal/config"
	"github.com/kuberbolt/financial-pod/internal/gateway"
	"go.uber.org/zap"
)

func main() {
	cfgPath  := flag.String("config", "", "Path to config.yaml (overrides default location)")
	agentName := flag.String("name", "", "Agent name (used to locate default config directory)")
	initMode  := flag.Bool("init", false, "Initialize a new agent and exit")
	flag.Parse()

	logger, err := zap.NewProduction()
	if err != nil {
		log.Fatalf("failed to build logger: %v", err)
	}
	defer logger.Sync()

	// Init mode: create config + keypair, then exit.
	if *initMode {
		if *agentName == "" {
			fmt.Fprintln(os.Stderr, "error: --name is required with --init")
			os.Exit(1)
		}
		cfg, err := config.Initialize(*agentName)
		if err != nil {
			logger.Fatal("init failed", zap.Error(err))
		}
		logger.Info("agent initialized",
			zap.String("name", cfg.Agent.Name),
			zap.String("config_dir", config.DefaultDir(cfg.Agent.Name)),
		)
		return
	}

	// Load config.
	var cfg *config.Config
	if *cfgPath != "" {
		cfg, err = config.LoadFromFile(*cfgPath)
	} else if *agentName != "" {
		cfg, err = config.LoadFromDefaultLocation(*agentName)
	} else {
		fmt.Fprintln(os.Stderr, "error: provide --config <path> or --name <agent>")
		os.Exit(1)
	}
	if err != nil {
		logger.Fatal("failed to load config", zap.Error(err))
	}

	// Root context wired to OS signals.
	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	// Build and start the Financial Pod server.
	fp, err := gateway.NewServer(ctx, cfg, logger)
	if err != nil {
		logger.Fatal("failed to build Financial Pod", zap.Error(err))
	}

	logger.Info("starting Financial Pod",
		zap.String("agent", cfg.Agent.Name),
		zap.Int("grpc_port", cfg.Network.GRPCPort),
	)

	if err := fp.Start(ctx); err != nil {
		logger.Fatal("Financial Pod start failed", zap.Error(err))
	}

	// Block until SIGINT/SIGTERM.
	<-ctx.Done()
	logger.Info("shutdown signal received, stopping gracefully…")

	stopCtx, stopCancel := context.WithTimeout(context.Background(), 30*1e9) // 30 s
	defer stopCancel()
	if err := fp.Stop(stopCtx); err != nil {
		logger.Error("error during shutdown", zap.Error(err))
	}
	logger.Info("shutdown complete")
}