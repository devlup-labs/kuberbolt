package ledger

import (
	"database/sql"
	"fmt"
	"time"

	_ "modernc.org/sqlite"
)

// DB wraps a SQLite connection and provides typed methods for all ledger operations.
// The schema matches SRS §8 exactly.
type DB struct {
	db *sql.DB
}

// Transaction represents a complete payment record in the ledger (SRS §8).
type Transaction struct {
	JobID              string
	CounterpartyPubkey string
	Direction          string // "incoming" or "outgoing"
	AmountMSat         int64
	InvoicePaymentHash string
	MacaroonID         string
	Status             string // "pending", "settled", "cancelled", "expired"
	CreatedAt          time.Time
	SettledAt          sql.NullTime
}

// PaymentHold tracks the preimage ↔ hash ↔ job mapping for active HODL invoices.
// The preimage is stored here and ONLY revealed to LND on successful settlement.
type PaymentHold struct {
	HoldID            string
	RHash             string // hex
	Preimage          string // hex — NEVER logged or exposed outside FP
	HTLCTimeoutBlocks int
	JobID             string
}

// Open opens (or creates) the SQLite database at dbPath and applies the schema.
func Open(dbPath string) (*DB, error) {
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		return nil, fmt.Errorf("ledger: open %q: %w", dbPath, err)
	}
	db.SetMaxOpenConns(1) // SQLite is single-writer
	if err := applySchema(db); err != nil {
		db.Close()
		return nil, fmt.Errorf("ledger: apply schema: %w", err)
	}
	return &DB{db: db}, nil
}

func applySchema(db *sql.DB) error {
	_, err := db.Exec(`
		PRAGMA journal_mode=WAL;
		PRAGMA foreign_keys=ON;

		CREATE TABLE IF NOT EXISTS ledger (
			job_id               TEXT    PRIMARY KEY,
			counterparty_pubkey  TEXT    NOT NULL,
			direction            TEXT    NOT NULL CHECK (direction IN ('incoming','outgoing')),
			amount_msat          INTEGER NOT NULL,
			invoice_payment_hash TEXT    NOT NULL,
			macaroon_id          TEXT,
			status               TEXT    NOT NULL CHECK (status IN ('pending','settled','cancelled','expired')),
			created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			settled_at           DATETIME
		);

		CREATE TABLE IF NOT EXISTS payment_holds (
			hold_id             TEXT    PRIMARY KEY,
			rhash               TEXT    NOT NULL UNIQUE,
			preimage            TEXT    NOT NULL,
			htlc_timeout_blocks INTEGER NOT NULL,
			job_id              TEXT    NOT NULL REFERENCES ledger(job_id)
		);

		CREATE INDEX IF NOT EXISTS idx_ledger_status       ON ledger(status);
		CREATE INDEX IF NOT EXISTS idx_ledger_direction    ON ledger(direction);
		CREATE INDEX IF NOT EXISTS idx_holds_rhash         ON payment_holds(rhash);
	`)
	return err
}

// RecordTransaction inserts a new transaction row. Returns an error if job_id already exists.
func (d *DB) RecordTransaction(tx *Transaction) error {
	_, err := d.db.Exec(`
		INSERT INTO ledger
		  (job_id, counterparty_pubkey, direction, amount_msat, invoice_payment_hash, macaroon_id, status, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
		tx.JobID, tx.CounterpartyPubkey, tx.Direction, tx.AmountMSat,
		tx.InvoicePaymentHash, tx.MacaroonID, tx.Status, tx.CreatedAt,
	)
	if err != nil {
		return fmt.Errorf("ledger: RecordTransaction: %w", err)
	}
	return nil
}

// UpdateStatus transitions a transaction to a new status and optionally records settled_at.
func (d *DB) UpdateStatus(jobID, status string) error {
	var settledAt interface{}
	if status == "settled" || status == "cancelled" {
		settledAt = time.Now()
	}
	_, err := d.db.Exec(
		`UPDATE ledger SET status = ?, settled_at = ? WHERE job_id = ?`,
		status, settledAt, jobID,
	)
	if err != nil {
		return fmt.Errorf("ledger: UpdateStatus %q→%q: %w", jobID, status, err)
	}
	return nil
}

// GetTransaction fetches a single transaction by job_id.
func (d *DB) GetTransaction(jobID string) (*Transaction, error) {
	row := d.db.QueryRow(
		`SELECT job_id, counterparty_pubkey, direction, amount_msat,
		        invoice_payment_hash, macaroon_id, status, created_at, settled_at
		 FROM ledger WHERE job_id = ?`, jobID,
	)
	tx := &Transaction{}
	err := row.Scan(
		&tx.JobID, &tx.CounterpartyPubkey, &tx.Direction, &tx.AmountMSat,
		&tx.InvoicePaymentHash, &tx.MacaroonID, &tx.Status, &tx.CreatedAt, &tx.SettledAt,
	)
	if err != nil {
		return nil, fmt.Errorf("ledger: GetTransaction %q: %w", jobID, err)
	}
	return tx, nil
}

// RecordPaymentHold inserts a HODL invoice hold. Called at invoice creation time.
func (d *DB) RecordPaymentHold(hold *PaymentHold) error {
	_, err := d.db.Exec(`
		INSERT INTO payment_holds (hold_id, rhash, preimage, htlc_timeout_blocks, job_id)
		VALUES (?, ?, ?, ?, ?)`,
		hold.HoldID, hold.RHash, hold.Preimage, hold.HTLCTimeoutBlocks, hold.JobID,
	)
	if err != nil {
		return fmt.Errorf("ledger: RecordPaymentHold: %w", err)
	}
	return nil
}

// GetPaymentHoldByRHash retrieves a hold by the payment hash hex string.
func (d *DB) GetPaymentHoldByRHash(rhash string) (*PaymentHold, error) {
	row := d.db.QueryRow(
		`SELECT hold_id, rhash, preimage, htlc_timeout_blocks, job_id
		 FROM payment_holds WHERE rhash = ?`, rhash,
	)
	hold := &PaymentHold{}
	err := row.Scan(&hold.HoldID, &hold.RHash, &hold.Preimage, &hold.HTLCTimeoutBlocks, &hold.JobID)
	if err != nil {
		return nil, fmt.Errorf("ledger: GetPaymentHoldByRHash %q: %w", rhash, err)
	}
	return hold, nil
}

// SumOutgoingSettledToday returns the sum of settled outgoing payments since midnight UTC.
func (d *DB) SumOutgoingSettledToday() (int64, error) {
	midnight := time.Now().UTC().Truncate(24 * time.Hour)
	row := d.db.QueryRow(`
		SELECT COALESCE(SUM(amount_msat), 0)
		FROM ledger
		WHERE direction = 'outgoing'
		  AND status    = 'settled'
		  AND created_at >= ?`, midnight,
	)
	var total int64
	if err := row.Scan(&total); err != nil {
		return 0, fmt.Errorf("ledger: SumOutgoingSettledToday: %w", err)
	}
	return total, nil
}

// SumOutgoingSettledThisMonth returns the sum of settled outgoing payments since the 1st of the month UTC.
func (d *DB) SumOutgoingSettledThisMonth() (int64, error) {
	now := time.Now().UTC()
	monthStart := time.Date(now.Year(), now.Month(), 1, 0, 0, 0, 0, time.UTC)
	row := d.db.QueryRow(`
		SELECT COALESCE(SUM(amount_msat), 0)
		FROM ledger
		WHERE direction = 'outgoing'
		  AND status    = 'settled'
		  AND created_at >= ?`, monthStart,
	)
	var total int64
	if err := row.Scan(&total); err != nil {
		return 0, fmt.Errorf("ledger: SumOutgoingSettledThisMonth: %w", err)
	}
	return total, nil
}

// Close closes the underlying database connection.
func (d *DB) Close() error {
	return d.db.Close()
}