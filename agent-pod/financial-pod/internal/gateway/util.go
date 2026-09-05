package gateway

// shortStr safely returns the first n characters of s followed by "…".
// Always use this instead of s[:n] on any string that arrives from the network.
// A malformed or attacker-crafted string shorter than n would cause a panic
// in s[:n]; grpc-go does not recover handler panics, so that kills the pod.
func shortStr(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "…"
}
