import React from 'react';
import { Activity, Shield, CheckCircle2, AlertCircle } from 'lucide-react';
import GridLogo from './GridLogo';

export default function Navbar({ isBackendHealthy, onSelectPreset }) {
  return (
    <header style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '16px 32px',
      borderBottom: '1px solid var(--border-subtle)',
      background: 'rgba(11, 15, 25, 0.85)',
      backdropFilter: 'blur(12px)',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <GridLogo size={44} />
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h1 style={{ fontSize: '20px', fontWeight: '800', letterSpacing: '-0.02em', margin: 0, color: '#f8fafc' }}>
              GridResilience
            </h1>
            <span className="badge badge-info" style={{ fontSize: '10px', padding: '2px 8px' }}>
              Phase 7 AI Platform
            </span>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0 }}>
            Predictive GCN + PPO Mitigation + Safety-Constrained Recovery on IEEE-14
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {/* Quick Presets */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 600 }}>PRESETS:</span>
          <button
            onClick={() => onSelectPreset({ line: 1, loadScale: 1.10, capScale: 0.02 })}
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-secondary)',
              padding: '6px 12px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '12px',
              cursor: 'pointer',
              fontWeight: 500,
            }}
          >
            Moderate (Line 1)
          </button>
          <button
            onClick={() => onSelectPreset({ line: 2, loadScale: 1.25, capScale: 0.015 })}
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-secondary)',
              padding: '6px 12px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '12px',
              cursor: 'pointer',
              fontWeight: 500,
            }}
          >
            Stressed (Line 2)
          </button>
          <button
            onClick={() => onSelectPreset({ line: 0, loadScale: 1.35, capScale: 0.012 })}
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-secondary)',
              padding: '6px 12px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '12px',
              cursor: 'pointer',
              fontWeight: 500,
            }}
          >
            Severe (Line 0)
          </button>
        </div>

        {/* Backend status badge */}
        <div className={`badge ${isBackendHealthy ? 'badge-safe' : 'badge-danger'}`} style={{ gap: '6px' }}>
          {isBackendHealthy ? <CheckCircle2 size={13} /> : <AlertCircle size={13} />}
          <span>{isBackendHealthy ? 'FastAPI Connected' : 'API Connecting...'}</span>
        </div>
      </div>
    </header>
  );
}
