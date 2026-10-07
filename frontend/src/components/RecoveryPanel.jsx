import React from 'react';
import { RefreshCw, CheckCircle2, ShieldCheck, Zap, ArrowUpRight } from 'lucide-react';

export default function RecoveryPanel({
  reconnectedLines = [],
  customerLoadRestoredMw = 0,
  finalLoadServed = 0,
  finalLoadServedPct = 0,
  postCascadeServedMw = 0,
  recoveryActions = [],
  finalStatus = 'STABLE',
}) {
  const committedActions = recoveryActions.filter((a) => a.committed);

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <RefreshCw size={16} color="#10b981" />
          Safety-Constrained Grid Recovery
        </h3>
        <span className="badge badge-safe" style={{ fontSize: '10px' }}>
          Phase 6 Restoration
        </span>
      </div>
      <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0 }}>
        Greedy heuristic controller sequentially re-energizes tripped transmission lines and restores shed loads while enforcing AC feasibility.
      </p>

      {/* Stats Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
        gap: '12px',
        padding: '12px',
        background: '#0e1424',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid #1e293b',
      }}>
        <div>
          <span style={{ fontSize: '11px', color: '#94a3b8' }}>Load Restored</span>
          <div className="mono" style={{ fontSize: '18px', fontWeight: 700, color: '#10b981' }}>
            +{Number(customerLoadRestoredMw).toFixed(2)} MW
          </div>
        </div>
        <div>
          <span style={{ fontSize: '11px', color: '#94a3b8' }}>Lines Reconnected</span>
          <div className="mono" style={{ fontSize: '18px', fontWeight: 700, color: '#06b6d4' }}>
            {reconnectedLines.length}
          </div>
        </div>
        <div>
          <span style={{ fontSize: '11px', color: '#94a3b8' }}>Pre-Recovery Load</span>
          <div className="mono" style={{ fontSize: '18px', fontWeight: 700, color: '#cbd5e1' }}>
            {Number(postCascadeServedMw).toFixed(1)} MW
          </div>
        </div>
        <div>
          <span style={{ fontSize: '11px', color: '#94a3b8' }}>Final Load Served</span>
          <div className="mono" style={{ fontSize: '18px', fontWeight: 700, color: '#f8fafc' }}>
            {Number(finalLoadServed).toFixed(1)} MW ({Number(finalLoadServedPct).toFixed(1)}%)
          </div>
        </div>
      </div>

      {/* Reconnected Lines list */}
      <div>
        <span style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
          Reclosed Transmission Lines:
        </span>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '6px' }}>
          {reconnectedLines.length === 0 ? (
            <span style={{ fontSize: '12px', color: '#64748b' }}>No transmission lines reclosed.</span>
          ) : (
            reconnectedLines.map((l) => (
              <span key={l} className="badge badge-info" style={{ fontSize: '11px', padding: '3px 10px' }}>
                Line {l} (Reclosed Safely)
              </span>
            ))
          )}
        </div>
      </div>

      {/* Action history */}
      {committedActions.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
            Committed Restoration Actions ({committedActions.length}):
          </span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '180px', overflowY: 'auto' }}>
            {committedActions.map((act, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '6px 10px',
                  background: '#0e1424',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid #1e293b',
                  fontSize: '11.5px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <CheckCircle2 size={13} color="#10b981" />
                  <span className="mono" style={{ color: '#f8fafc', fontWeight: 600 }}>{act.action}</span>
                </div>
                <span className="mono" style={{ color: '#06b6d4', fontWeight: 700 }}>
                  {act.served_load_mw?.toFixed(1)} MW
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
