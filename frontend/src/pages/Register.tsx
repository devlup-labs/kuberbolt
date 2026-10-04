import { useState } from 'react';
import { KeyDisplay } from '../components/KeyDisplay';

export default function Register() {
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    role: 'merchant',
    displayName: '',
    nodePubkey: '',
    lightningAddress: '',
    serviceName: '',
    serviceCategory: 'text-summarization',
    priceSats: 100
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const payload = {
      role: formData.role,
      display_name: formData.displayName,
      lightning: {
        node_pubkey: formData.nodePubkey,
        lightning_address: formData.lightningAddress
      },
      ...(formData.role === 'merchant' && {
        service: {
          service_name: formData.serviceName,
          category: formData.serviceCategory,
          price_sats: Number(formData.priceSats),
          price_unit: 'per_request'
        }
      })
    };

    try {
      const apiUrl = import.meta.env.VITE_API_URL || '';
      const res = await fetch(`${apiUrl}/api/agents/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const contentType = res.headers.get('content-type') || '';
      let data: any = null;
      if (contentType.includes('application/json')) {
        try {
          data = await res.json();
        } catch {
          data = null;
        }
      }

      if (res.ok && data) {
        setResult(data);
      } else if (data && data.detail) {
        setError(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
      } else if (data) {
        setError(JSON.stringify(data));
      } else {
        setError(`Registration failed (${res.status}). Make sure the backend server is running on port 8000.`);
      }
    } catch {
      setError('Could not connect to the API. Make sure the backend server is running on port 8000.');
    } finally {
      setLoading(false);
    }
  };

  if (result) {
    return (
      <div>
        <div className="page-header">
          <div>
            <h1 className="page-title">Registration Complete 🎉</h1>
            <p className="page-subtitle">Your agent identity has been created on the Nostr network</p>
          </div>
        </div>
        <KeyDisplay
          pubkey={result.agent_pubkey}
          privkey={result.agent_privkey}
          nsec={result.agent_nsec}
          sessionToken={result.session_token}
        />
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Register Agent</h1>
          <p className="page-subtitle">Create a new Nostr identity for your AI agent</p>
        </div>
      </div>

      <div className="glass-panel" style={{ maxWidth: '560px', margin: '0 auto' }}>
        {error && (
          <div className="banner banner-warning">
            ⚠️ {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Agent Name</label>
            <input
              className="input-field"
              value={formData.displayName}
              onChange={e => setFormData({ ...formData, displayName: e.target.value })}
              required
              placeholder="e.g. Trading Bot Alpha"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Lightning Node Pubkey</label>
            <input
              className="input-field"
              value={formData.nodePubkey}
              onChange={e => setFormData({ ...formData, nodePubkey: e.target.value })}
              required
              placeholder="02abcd1234..."
            />
          </div>

          <div className="form-group">
            <label className="form-label">Role</label>
            <select
              className="input-field"
              value={formData.role}
              onChange={e => setFormData({ ...formData, role: e.target.value })}
            >
              <option value="merchant">Merchant — Provides Compute Services</option>
              <option value="client">Client — Consumes Compute Services</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Lightning Address</label>
            <input
              className="input-field"
              value={formData.lightningAddress}
              onChange={e => setFormData({ ...formData, lightningAddress: e.target.value })}
              required
              placeholder="agent@example.com"
            />
          </div>

          {formData.role === 'merchant' && (
            <div className="form-section">
              <div className="form-section-title">Service Configuration</div>
              <div className="form-group">
                <label className="form-label">Service Name</label>
                <input
                  className="input-field"
                  value={formData.serviceName}
                  onChange={e => setFormData({ ...formData, serviceName: e.target.value })}
                  required
                  placeholder="e.g. LLM Inference"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Service Category</label>
                <input
                  className="input-field"
                  value={formData.serviceCategory}
                  onChange={e => setFormData({ ...formData, serviceCategory: e.target.value })}
                  required
                  placeholder="text-summarization"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Price per Request (sats)</label>
                <input
                  className="input-field"
                  type="number"
                  value={formData.priceSats}
                  onChange={e => setFormData({ ...formData, priceSats: Number(e.target.value) })}
                  required
                  min={1}
                />
              </div>
            </div>
          )}

          <button
            type="submit"
            className="btn"
            style={{ width: '100%', padding: '14px', fontSize: '0.95rem', marginTop: '8px' }}
            disabled={loading}
          >
            {loading ? 'Creating identity...' : '⚡ Register Agent'}
          </button>
        </form>
      </div>
    </div>
  );
}
