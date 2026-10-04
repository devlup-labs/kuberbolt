package ledger

import (
	"path/filepath"
	"testing"
	"time"
)

func setupTestDB(t *testing.T) *DB {
	tmpDir := t.TempDir()
	dbPath := filepath.Join(tmpDir, "test_ledger.db")
	db, err := Open(dbPath)
	if err != nil {
		t.Fatalf("failed to open test ledger db: %v", err)
	}
	t.Cleanup(func() {
		db.Close()
	})
	return db
}

func TestRecordAndGetTransaction(t *testing.T) {
	db := setupTestDB(t)

	tx := &Transaction{
		JobID:              "job-101",
		CounterpartyPubkey: "pubkey-101",
		Direction:          "incoming",
		AmountMSat:         50000,
		InvoicePaymentHash: "hash-101",
		MacaroonID:         "mac-101",
		Status:             "pending",
		CreatedAt:          time.Now(),
	}

	if err := db.RecordTransaction(tx); err != nil {
		t.Fatalf("RecordTransaction failed: %v", err)
	}

	fetched, err := db.GetTransaction("job-101")
	if err != nil {
		t.Fatalf("GetTransaction failed: %v", err)
	}

	if fetched.JobID != tx.JobID {
		t.Errorf("expected JobID %q, got %q", tx.JobID, fetched.JobID)
	}
	if fetched.AmountMSat != tx.AmountMSat {
		t.Errorf("expected AmountMSat %d, got %d", tx.AmountMSat, fetched.AmountMSat)
	}
	if fetched.Status != "pending" {
		t.Errorf("expected Status pending, got %q", fetched.Status)
	}
}

func TestUpdateStatusByJobID(t *testing.T) {
	db := setupTestDB(t)

	tx := &Transaction{
		JobID:              "job-102",
		CounterpartyPubkey: "pubkey-102",
		Direction:          "outgoing",
		AmountMSat:         25000,
		InvoicePaymentHash: "hash-102",
		MacaroonID:         "mac-102",
		Status:             "pending",
		CreatedAt:          time.Now(),
	}

	if err := db.RecordTransaction(tx); err != nil {
		t.Fatalf("RecordTransaction failed: %v", err)
	}

	if err := db.UpdateStatus("job-102", "settled"); err != nil {
		t.Fatalf("UpdateStatus failed: %v", err)
	}

	fetched, err := db.GetTransaction("job-102")
	if err != nil {
		t.Fatalf("GetTransaction failed: %v", err)
	}
	if fetched.Status != "settled" {
		t.Errorf("expected status settled, got %q", fetched.Status)
	}
	if !fetched.SettledAt.Valid {
		t.Error("expected settled_at to be valid for settled transaction")
	}

	// Non-existent jobID should return error
	if err := db.UpdateStatus("job-non-existent", "settled"); err == nil {
		t.Error("expected error updating non-existent job, got nil")
	}
}

func TestUpdateStatusByPaymentHash(t *testing.T) {
	db := setupTestDB(t)

	tx := &Transaction{
		JobID:              "job-103",
		CounterpartyPubkey: "pubkey-103",
		Direction:          "incoming",
		AmountMSat:         100000,
		InvoicePaymentHash: "rhash-unique-103",
		MacaroonID:         "mac-103",
		Status:             "pending",
		CreatedAt:          time.Now(),
	}

	if err := db.RecordTransaction(tx); err != nil {
		t.Fatalf("RecordTransaction failed: %v", err)
	}

	if err := db.UpdateStatusByPaymentHash("rhash-unique-103", "settled"); err != nil {
		t.Fatalf("UpdateStatusByPaymentHash failed: %v", err)
	}

	fetched, err := db.GetTransaction("job-103")
	if err != nil {
		t.Fatalf("GetTransaction failed: %v", err)
	}
	if fetched.Status != "settled" {
		t.Errorf("expected status settled, got %q", fetched.Status)
	}

	// Non-existent payment hash should return error
	if err := db.UpdateStatusByPaymentHash("non-existent-rhash", "cancelled"); err == nil {
		t.Error("expected error updating non-existent rhash, got nil")
	}
}

func TestRecordAndGetPaymentHold(t *testing.T) {
	db := setupTestDB(t)

	tx := &Transaction{
		JobID:              "job-104",
		CounterpartyPubkey: "pubkey-104",
		Direction:          "incoming",
		AmountMSat:         75000,
		InvoicePaymentHash: "hash-104",
		Status:             "pending",
		CreatedAt:          time.Now(),
	}
	if err := db.RecordTransaction(tx); err != nil {
		t.Fatalf("RecordTransaction failed: %v", err)
	}

	hold := &PaymentHold{
		HoldID:            "hold-104",
		RHash:             "hash-104",
		Preimage:          "preimage-secret-104",
		HTLCTimeoutBlocks: 40,
		JobID:             "job-104",
	}

	if err := db.RecordPaymentHold(hold); err != nil {
		t.Fatalf("RecordPaymentHold failed: %v", err)
	}

	fetchedHold, err := db.GetPaymentHoldByRHash("hash-104")
	if err != nil {
		t.Fatalf("GetPaymentHoldByRHash failed: %v", err)
	}

	if fetchedHold.HoldID != hold.HoldID {
		t.Errorf("expected HoldID %q, got %q", hold.HoldID, fetchedHold.HoldID)
	}
	if fetchedHold.Preimage != hold.Preimage {
		t.Errorf("expected Preimage %q, got %q", hold.Preimage, fetchedHold.Preimage)
	}
}

func TestSumOutgoingSettled(t *testing.T) {
	db := setupTestDB(t)

	// Add settled outgoing transaction
	tx1 := &Transaction{
		JobID:              "job-out-1",
		CounterpartyPubkey: "pubkey-1",
		Direction:          "outgoing",
		AmountMSat:         30000,
		InvoicePaymentHash: "hash-out-1",
		Status:             "settled",
		CreatedAt:          time.Now(),
	}
	if err := db.RecordTransaction(tx1); err != nil {
		t.Fatalf("RecordTransaction failed: %v", err)
	}

	// Add pending outgoing transaction (should not be summed)
	tx2 := &Transaction{
		JobID:              "job-out-2",
		CounterpartyPubkey: "pubkey-2",
		Direction:          "outgoing",
		AmountMSat:         50000,
		InvoicePaymentHash: "hash-out-2",
		Status:             "pending",
		CreatedAt:          time.Now(),
	}
	if err := db.RecordTransaction(tx2); err != nil {
		t.Fatalf("RecordTransaction failed: %v", err)
	}

	// Add settled incoming transaction (should not be summed in outgoing)
	tx3 := &Transaction{
		JobID:              "job-in-1",
		CounterpartyPubkey: "pubkey-3",
		Direction:          "incoming",
		AmountMSat:         70000,
		InvoicePaymentHash: "hash-in-1",
		Status:             "settled",
		CreatedAt:          time.Now(),
	}
	if err := db.RecordTransaction(tx3); err != nil {
		t.Fatalf("RecordTransaction failed: %v", err)
	}

	today, err := db.SumOutgoingSettledToday()
	if err != nil {
		t.Fatalf("SumOutgoingSettledToday failed: %v", err)
	}
	if today != 30000 {
		t.Errorf("expected today's outgoing settled sum 30000, got %d", today)
	}

	thisMonth, err := db.SumOutgoingSettledThisMonth()
	if err != nil {
		t.Fatalf("SumOutgoingSettledThisMonth failed: %v", err)
	}
	if thisMonth != 30000 {
		t.Errorf("expected this month's outgoing settled sum 30000, got %d", thisMonth)
	}
}
