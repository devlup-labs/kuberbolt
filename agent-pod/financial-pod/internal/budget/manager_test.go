package budget

import (
	"context"
	"strings"
	"testing"

	"go.uber.org/zap"
)

func TestBudgetManager(t *testing.T) {
	cfg := Config{
		DailyLimitMSat:   100000,
		MonthlyLimitMSat: 500000,
	}
	logger := zap.NewNop()
	bm := NewManager(cfg, logger)

	ctx := context.Background()

	// Initially 0 spend
	if err := bm.CheckBudget(ctx); err != nil {
		t.Fatalf("unexpected CheckBudget error on fresh manager: %v", err)
	}
	if err := bm.CheckBudgetFor(ctx, 50000); err != nil {
		t.Fatalf("unexpected CheckBudgetFor error: %v", err)
	}
	if bm.GetDailyAvailable() != 100000 {
		t.Errorf("expected 100000 daily available, got %d", bm.GetDailyAvailable())
	}

	// Record 60000 spend
	bm.RecordSpend(60000)
	if bm.GetDailySpent() != 60000 {
		t.Errorf("expected 60000 daily spent, got %d", bm.GetDailySpent())
	}
	if bm.GetDailyAvailable() != 40000 {
		t.Errorf("expected 40000 daily available, got %d", bm.GetDailyAvailable())
	}

	// Check for payment of 30000 (should pass, 60000 + 30000 <= 100000)
	if err := bm.CheckBudgetFor(ctx, 30000); err != nil {
		t.Errorf("expected 30000 payment to pass, got error: %v", err)
	}

	// Check for payment of 50000 (should fail, 60000 + 50000 > 100000)
	err := bm.CheckBudgetFor(ctx, 50000)
	if err == nil {
		t.Fatal("expected CheckBudgetFor to fail on daily limit exceed, got nil")
	}
	if !strings.Contains(err.Error(), "would exceed daily limit") {
		t.Errorf("unexpected error message: %v", err)
	}

	// Record another 40000 spend -> exactly at limit
	bm.RecordSpend(40000)
	if bm.GetDailyAvailable() != 0 {
		t.Errorf("expected 0 daily available at limit, got %d", bm.GetDailyAvailable())
	}

	// CheckBudget should now fail
	if err := bm.CheckBudget(ctx); err == nil {
		t.Fatal("expected CheckBudget to fail when daily budget exhausted, got nil")
	}

	// Test LoadSpend
	bm.LoadSpend(10000, 20000)
	if bm.GetDailySpent() != 10000 {
		t.Errorf("expected 10000 after LoadSpend, got %d", bm.GetDailySpent())
	}
	if bm.GetMonthlySpent() != 20000 {
		t.Errorf("expected 20000 after LoadSpend, got %d", bm.GetMonthlySpent())
	}
}
