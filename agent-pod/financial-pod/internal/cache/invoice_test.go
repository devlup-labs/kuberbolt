package cache

import (
	"testing"
	"time"
)

func TestInvoiceCacheBasicOps(t *testing.T) {
	c := New()

	entry := &Entry{
		JobID:     "job-1",
		Invoice:   "lnbc1...",
		RHash:     []byte("hash-bytes-1"),
		RHashHex:  "hash-hex-1",
		Preimage:  []byte("preimage-1"),
		CreatedAt: time.Now(),
		ExpiresAt: time.Now().Add(1 * time.Minute),
	}

	c.Set("job-1", entry)

	// Get by jobID
	fetched := c.Get("job-1")
	if fetched == nil {
		t.Fatal("expected entry for job-1, got nil")
	}
	if fetched.RHashHex != "hash-hex-1" {
		t.Errorf("expected RHashHex hash-hex-1, got %s", fetched.RHashHex)
	}
	if fetched.JobID != "job-1" {
		t.Errorf("expected JobID job-1, got %s", fetched.JobID)
	}

	// Get by RHashHex
	fetchedByHash := c.GetByRHash("hash-hex-1")
	if fetchedByHash == nil {
		t.Fatal("expected entry for hash-hex-1, got nil")
	}
	if fetchedByHash.JobID != "job-1" {
		t.Errorf("expected JobID job-1, got %s", fetchedByHash.JobID)
	}

	// Non-existent
	if c.Get("non-existent") != nil {
		t.Error("expected nil for non-existent job")
	}
	if c.GetByRHash("non-existent") != nil {
		t.Error("expected nil for non-existent rhash")
	}

	// Delete by jobID
	c.Delete("job-1")
	if c.Get("job-1") != nil {
		t.Error("expected nil after Delete")
	}
}

func TestDeleteByRHash(t *testing.T) {
	c := New()

	entry := &Entry{
		JobID:     "job-2",
		Invoice:   "lnbc2...",
		RHashHex:  "hash-hex-2",
		CreatedAt: time.Now(),
		ExpiresAt: time.Now().Add(1 * time.Minute),
	}
	c.Set("job-2", entry)

	c.DeleteByRHash("hash-hex-2")
	if c.Get("job-2") != nil {
		t.Error("expected entry to be deleted by RHash")
	}
}

func TestCleanupExpired(t *testing.T) {
	c := New()

	// Active entry
	c.Set("active", &Entry{
		JobID:     "active",
		ExpiresAt: time.Now().Add(10 * time.Minute),
	})

	// Expired entry
	c.Set("expired-1", &Entry{
		JobID:     "expired-1",
		ExpiresAt: time.Now().Add(-1 * time.Minute),
	})
	c.Set("expired-2", &Entry{
		JobID:     "expired-2",
		ExpiresAt: time.Now().Add(-5 * time.Minute),
	})

	// Get on expired should return nil
	if c.Get("expired-1") != nil {
		t.Error("Get on expired entry should return nil")
	}

	removed := c.CleanupExpired()
	if removed != 2 {
		t.Errorf("expected 2 removed expired entries, got %d", removed)
	}

	if c.Get("active") == nil {
		t.Error("active entry should remain after CleanupExpired")
	}
}
