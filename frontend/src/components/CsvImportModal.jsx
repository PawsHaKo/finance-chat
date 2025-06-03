import React, { useState } from 'react';

export default function CsvImportModal({ open, onClose, onSuccess }) {
  const [file, setFile] = useState(null);
  const [mode, setMode] = useState('replace');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  if (!open) return null;

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
    setResult(null);
    setError('');
  };

  const handleImport = async (e) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a CSV file.');
      return;
    }
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('mode', mode);
      const resp = await fetch('http://localhost:8000/portfolio/import-csv/', {
        method: 'POST',
        body: formData,
      });
      if (!resp.ok) throw new Error('Import failed');
      const data = await resp.json();
      setResult(data);
      if (onSuccess) onSuccess();
    } catch (err) {
      setError('Import failed. Please check your CSV and try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="csv-import-modal-backdrop">
      <div className="csv-import-modal">
        <h2>Import Portfolio CSV</h2>
        <form onSubmit={handleImport}>
          <input type="file" accept=".csv" onChange={handleFileChange} disabled={loading} />
          <div style={{ margin: '1em 0' }}>
            <label>
              <input type="radio" name="mode" value="replace" checked={mode === 'replace'} onChange={() => setMode('replace')} disabled={loading} />
              Replace (clear all and import)
            </label>
            <label style={{ marginLeft: '1.5em' }}>
              <input type="radio" name="mode" value="append" checked={mode === 'append'} onChange={() => setMode('append')} disabled={loading} />
              Append/Update (merge by symbol)
            </label>
          </div>
          <div style={{ display: 'flex', gap: '1em', marginTop: '1em' }}>
            <button type="submit" disabled={loading}>{loading ? 'Importing...' : 'Import'}</button>
            <button type="button" onClick={onClose} disabled={loading}>Cancel</button>
          </div>
        </form>
        {error && <div className="error" style={{ marginTop: '1em' }}>{error}</div>}
        {result && (
          <div className="import-result" style={{ marginTop: '1em' }}>
            <div><b>Added:</b> {result.added}</div>
            <div><b>Updated:</b> {result.updated}</div>
            <div><b>Skipped:</b> {result.skipped}</div>
            {result.errors && result.errors.length > 0 && (
              <div style={{ color: '#f87171', marginTop: '0.5em' }}>
                <b>Errors:</b>
                <ul style={{ margin: 0, paddingLeft: '1.2em' }}>
                  {result.errors.map((err, i) => <li key={i}>{err}</li>)}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
      <style>{`
        .csv-import-modal-backdrop {
          position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
          background: rgba(24,28,38,0.75); z-index: 2000; display: flex; align-items: center; justify-content: center;
        }
        .csv-import-modal {
          background: #181c26; color: #fff; border-radius: 14px; box-shadow: 0 8px 32px #181c2633;
          padding: 2.2em 2.5em; min-width: 340px; max-width: 95vw;
        }
        .csv-import-modal h2 { margin-top: 0; color: #60a5fa; }
        .csv-import-modal input[type="file"] { margin-bottom: 1em; }
        .csv-import-modal button { background: linear-gradient(90deg, #2563eb 60%, #60a5fa 100%); color: #fff; border: none; border-radius: 6px; font-weight: 600; font-size: 1em; padding: 0.5em 1.3em; cursor: pointer; transition: background 0.2s; }
        .csv-import-modal button:disabled { opacity: 0.6; cursor: not-allowed; }
        .csv-import-modal .error { color: #f87171; background: #2b1a1a; border: 1px solid #7f1d1d; padding: 0.5rem 1rem; border-radius: 6px; margin-bottom: 1rem; text-align: center; font-weight: 500; box-shadow: 0 0 8px #7f1d1d33; }
      `}</style>
    </div>
  );
} 