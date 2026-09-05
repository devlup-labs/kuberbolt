package budget

import (
	"context"
	"fmt"
	"sync"

	"go.uber.org/zap"
)

// Config holds spending limits loaded from agent config.yaml.
type Config struct {
	DailyLimitMSat   int64 `yaml:"daily_limit_msat"`
	MonthlyLimitMSat int64 `yaml:"monthly_limit_msat"`
}

// Manager tracks outbound spending and enforces daily/monthly limits.
// All operations are safe for concurrent use.
type Manager struct {
	cfg          Config
	logger       *zap.Logger
	mu           sync.RWMutex
	dailySpent   int64
	monthlySpent int64
}

// NewManager creates a Manager. Initial spend counters start at zero;
// call LoadFromLedger after construction to restore persisted values.
func NewManager(cfg Config, logger *zap.Logger) *Manager {
	return &Manager{
		cfg:    cfg,
		logger: logger,
	}
}

// LoadSpend sets the initial counters from persisted ledger data.
// Call once at startup after reading totals from the SQLite ledger.
func (m *Manager) LoadSpend(dailyMSat, monthlyMSat int64) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.dailySpent = dailyMSat
	m.monthlySpent = monthlyMSat
}

// CheckBudget returns an error if the daily or monthly limit is already
// reached. It does not reserve capacity; call RecordSpend after payment.
func (m *Manager) CheckBudget(_ context.Context) error {
	m.mu.RLock()
	defer m.mu.RUnlock()
	if m.dailySpent >= m.cfg.DailyLimitMSat {
		return fmt.Errorf("daily budget exhausted (%d/%d msat)", m.dailySpent, m.cfg.DailyLimitMSat)
	}
	if m.monthlySpent >= m.cfg.MonthlyLimitMSat {
		return fmt.Errorf("monthly budget exhausted (%d/%d msat)", m.monthlySpent, m.cfg.MonthlyLimitMSat)
	}
	return nil
}

// CheckBudgetFor returns an error if adding amount would exceed either limit.
// Use this before initiating a payment to pre-validate the amount.
func (m *Manager) CheckBudgetFor(_ context.Context, amountMSat int64) error {
	m.mu.RLock()
	defer m.mu.RUnlock()
	if m.dailySpent+amountMSat > m.cfg.DailyLimitMSat {
		return fmt.Errorf("payment of %d msat would exceed daily limit (%d/%d msat spent)",
			amountMSat, m.dailySpent, m.cfg.DailyLimitMSat)
	}
	if m.monthlySpent+amountMSat > m.cfg.MonthlyLimitMSat {
		return fmt.Errorf("payment of %d msat would exceed monthly limit (%d/%d msat spent)",
			amountMSat, m.monthlySpent, m.cfg.MonthlyLimitMSat)
	}
	return nil
}

// RecordSpend adds amount to the running spend counters.
// Call after a payment is confirmed settled.
func (m *Manager) RecordSpend(amountMSat int64) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.dailySpent += amountMSat
	m.monthlySpent += amountMSat
	m.logger.Info("spend recorded",
		zap.Int64("amount_msat", amountMSat),
		zap.Int64("daily_total_msat", m.dailySpent),
		zap.Int64("daily_limit_msat", m.cfg.DailyLimitMSat),
	)
}

// GetDailySpent returns the current daily spend counter.
func (m *Manager) GetDailySpent() int64 {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.dailySpent
}

// GetMonthlySpent returns the current monthly spend counter.
func (m *Manager) GetMonthlySpent() int64 {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.monthlySpent
}

// GetDailyAvailable returns remaining daily spend capacity.
// Never returns negative (returns 0 if limit is exceeded).
func (m *Manager) GetDailyAvailable() int64 {
	m.mu.RLock()
	defer m.mu.RUnlock()
	avail := m.cfg.DailyLimitMSat - m.dailySpent
	if avail < 0 {
		return 0
	}
	return avail
}