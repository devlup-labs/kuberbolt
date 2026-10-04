export default function Dashboard() {
  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Monitor your Kuberbolt network at a glance</p>
        </div>
      </div>

      <div className="card-grid">
        <div className="glass-panel stat-card">
          <div className="stat-header">
            <div className="stat-icon" style={{ background: 'var(--success-bg)' }}>🌐</div>
            <span className="stat-label">Network</span>
          </div>
          <div className="stat-value">
            <span className="badge badge-warning">● Status unavailable</span>
          </div>
          <div className="stat-meta">Connect the backend to view network status</div>
        </div>

        <div className="glass-panel stat-card">
          <div className="stat-header">
            <div className="stat-icon" style={{ background: 'var(--info-bg)' }}>🤖</div>
            <span className="stat-label">Active Pods</span>
          </div>
          <div className="stat-value">--</div>
          <div className="stat-meta">Financial Pod status is not connected</div>
        </div>

        <div className="glass-panel stat-card">
          <div className="stat-header">
            <div className="stat-icon" style={{ background: 'var(--warning-bg)' }}>⚡</div>
            <span className="stat-label">Transacted</span>
          </div>
          <div className="stat-value">--</div>
          <div className="stat-meta">Transaction totals are not connected</div>
        </div>
      </div>

      <div style={{ marginTop: '48px' }}>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 600, marginBottom: '20px', letterSpacing: '-0.3px' }}>Get Started</h2>
        <div className="quick-start-grid">
          <div className="glass-panel step-card">
            <div className="step-number">1</div>
            <div className="step-title">Register Your Agent</div>
            <div className="step-desc">
              Create a Nostr identity via the <strong>Register</strong> tab. Your private key is shown once — save it locally.
            </div>
          </div>

          <div className="glass-panel step-card">
            <div className="step-number">2</div>
            <div className="step-title">Deploy a Pod</div>
            <div className="step-desc">
              Run <code>./scripts/deploy-pod.sh --name my-agent</code> to launch a Financial Pod + LND node pair.
            </div>
          </div>

          <div className="glass-panel step-card">
            <div className="step-number">3</div>
            <div className="step-title">Discover & Trade</div>
            <div className="step-desc">
              Browse the <strong>Discover</strong> tab to find compute providers. L402 payments are handled automatically.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
