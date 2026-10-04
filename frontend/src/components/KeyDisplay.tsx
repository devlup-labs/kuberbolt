import { useState } from 'react';

interface KeyDisplayProps {
  pubkey: string;
  privkey: string;
  nsec: string;
  sessionToken: string;
}

export const KeyDisplay = ({ pubkey, privkey, nsec, sessionToken }: KeyDisplayProps) => {
  const [copied, setCopied] = useState<string | null>(null);

  const downloadKeyFile = () => {
    const data = JSON.stringify({ npub: pubkey, privkey, nsec, session_token: sessionToken }, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `kuberbolt-keys-${pubkey.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const copyToClipboard = async (text: string, label: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <div className="glass-panel" style={{ maxWidth: '560px' }}>
      <div className="banner banner-warning">
        ⚠️ <span><strong>Save your private key now.</strong> It will never be shown again.</span>
      </div>

      <div className="form-group">
        <label className="form-label">Public Key (npub)</label>
        <div className="code-block">{pubkey}</div>
        <button
          className="btn btn-outline btn-sm"
          style={{ marginTop: '8px' }}
          onClick={() => copyToClipboard(pubkey, 'pubkey')}
        >
          {copied === 'pubkey' ? '✓ Copied' : 'Copy'}
        </button>
      </div>

      <div className="form-group">
        <label className="form-label">Session Token</label>
        <div className="code-block">{sessionToken}</div>
        <button
          className="btn btn-outline btn-sm"
          style={{ marginTop: '8px' }}
          onClick={() => copyToClipboard(sessionToken, 'session')}
        >
          {copied === 'session' ? '✓ Copied' : 'Copy Session Token'}
        </button>
      </div>

      <div className="form-group">
        <label className="form-label" style={{ color: 'var(--danger)' }}>Secret Key (nsec)</label>
        <div className="code-block" style={{ color: 'var(--danger)' }}>{nsec}</div>
        <button
          className="btn btn-sm btn-danger"
          style={{ marginTop: '8px' }}
          onClick={() => copyToClipboard(nsec, 'nsec')}
        >
          {copied === 'nsec' ? '✓ Copied' : 'Copy Secret'}
        </button>
      </div>

      <button
        className="btn"
        onClick={downloadKeyFile}
        style={{ width: '100%', padding: '14px', fontSize: '0.95rem', marginTop: '16px' }}
      >
        ⬇️ Download Key File (.json)
      </button>
    </div>
  );
};
