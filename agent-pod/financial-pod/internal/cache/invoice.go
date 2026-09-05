package cache

import (
	"sync"
	"time"
)

// Entry holds the in-memory state of an active L402 challenge.
type Entry struct {
	Invoice   string
	RHash     []byte // raw bytes
	RHashHex  string
	Preimage  []byte // raw bytes — kept secret, written to ledger at settlement
	MacaroonBytes []byte
	CreatedAt time.Time
	ExpiresAt time.Time
}

// IsExpired reports whether this entry has passed its expiry time.
func (e *Entry) IsExpired() bool {
	return time.Now().After(e.ExpiresAt)
}

// InvoiceCache maps job_id → Entry for all active (unsettled) HODL invoices.
// It is safe for concurrent access.
type InvoiceCache struct {
	mu    sync.RWMutex
	items map[string]*Entry
}

// New creates an empty InvoiceCache.
func New() *InvoiceCache {
	return &InvoiceCache{
		items: make(map[string]*Entry),
	}
}

// Set stores or replaces the entry for jobID.
func (c *InvoiceCache) Set(jobID string, entry *Entry) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.items[jobID] = entry
}

// Get returns the entry for jobID, or nil if not found or expired.
func (c *InvoiceCache) Get(jobID string) *Entry {
	c.mu.RLock()
	defer c.mu.RUnlock()
	e, ok := c.items[jobID]
	if !ok || e.IsExpired() {
		return nil
	}
	return e
}

// GetByRHash finds an entry whose RHashHex matches the provided hex string.
func (c *InvoiceCache) GetByRHash(rhashHex string) *Entry {
	c.mu.RLock()
	defer c.mu.RUnlock()
	for _, e := range c.items {
		if e.RHashHex == rhashHex && !e.IsExpired() {
			return e
		}
	}
	return nil
}

// Delete removes an entry from the cache (call after settlement or cancellation).
func (c *InvoiceCache) Delete(jobID string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	delete(c.items, jobID)
}

// DeleteByRHash removes the entry whose RHashHex matches. Used by the provider
// after settlement when only the rhash is known (not the internal jobID).
func (c *InvoiceCache) DeleteByRHash(rhashHex string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	for k, e := range c.items {
		if e.RHashHex == rhashHex {
			delete(c.items, k)
			return
		}
	}
}

// CleanupExpired removes all expired entries. Called by the background task goroutine.
func (c *InvoiceCache) CleanupExpired() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	removed := 0
	for k, e := range c.items {
		if e.IsExpired() {
			delete(c.items, k)
			removed++
		}
	}
	return removed
}

// Snapshot returns a copy of all current (non-expired) entries keyed by jobID.
func (c *InvoiceCache) Snapshot() map[string]*Entry {
	c.mu.RLock()
	defer c.mu.RUnlock()
	out := make(map[string]*Entry, len(c.items))
	for k, e := range c.items {
		if !e.IsExpired() {
			out[k] = e
		}
	}
	return out
}