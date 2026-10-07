import React from 'react';
import { ShieldAlert, AlertTriangle, CheckCircle2, ChevronRight } from 'lucide-react';

export default function FailurePredictionPanel({ predictions, initialOutages = [] }) {
  if (!predictions || predictions.length === 0) {
    return (
      <div className="card" style={{ height: '360px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>Run a simulation to generate GCN line failure probabilities.</p>
      </div>
    );
  }

  // Sort by probability descending
  const sorted = [...predictions].sort((a, b) => b.probability - a.probability);

  const getRiskBadge = (prob, isInit) => {
    if (isInit) {
      return <span className="badge badge-neutral" style={{ fontSize: '10px' }}>OUTAGE TRIGGER</span>;
    }
    if (prob >= 0.50) {
      return <span className="badge badge-danger" style={{ fontSize: '10px' }}>CRITICAL (&ge;50%)</span>;
    }
    if (prob >= 0.20) {
      return <span className="badge badge-warning" style={{ fontSize: '10px' }}>HIGH (20-50%)</span>;
    }
    if (prob >= 0.05) {
      return <span className="badge badge-info" style={{ fontSize: '10px' }}>MODERATE</span>;
    }
    return <span className="badge badge-safe" style={{ fontSize: '10px' }}>LOW RISK</span>;
  };

  const getBarColor = (prob, isInit) => {
    if (isInit) return '#64748b';
    if (prob >= 0.50) return '#ef4444';
    if (prob >= 0.20) return '#f59e0b';
    if (prob >= 0.05) return '#06b6d4';
    return '#10b981';
  };

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ShieldAlert size={16} color="#ef4444" />
          Predictive GCN Failure Probabilities
        </h3>
        <span style={{ fontSize: '11px', color: '#94a3b8' }}>15 Transmission Lines</span>
      </div>
      <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0 }}>
        Downstream line failure probabilities predicted by predictive_v2 GCN under AC contingency conditions.
      </p>

      {/* Line list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '380px', overflowY: 'auto', paddingRight: '4px' }}>
        {sorted.map((item, idx) => {
          const isInitial = item.is_initial_outage || initialOutages.includes(item.line_index);
          const pct = (item.probability * 100).toFixed(1);
          const barColor = getBarColor(item.probability, isInitial);

          return (
            <div
              key={item.line_index}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
                padding: '8px 10px',
                background: '#0e1424',
                border: '1px solid #1e293b',
                borderRadius: 'var(--radius-sm)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="mono" style={{ fontSize: '11px', fontWeight: 700, color: '#38bdf8' }}>
                    #{idx + 1}
                  </span>
                  <span style={{ fontSize: '12px', fontWeight: 600, color: '#f1f5f9' }}>
                    Line {item.line_index} (Bus {item.from_bus + 1} ↔ Bus {item.to_bus + 1})
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {getRiskBadge(item.probability, isInitial)}
                  <span className="mono" style={{ fontSize: '12px', fontWeight: 800, color: barColor, minWidth: '46px', textAlign: 'right' }}>
                    {isInitial ? 'TRIPPED' : `${pct}%`}
                  </span>
                </div>
              </div>

              {/* Progress visual bar */}
              <div style={{ width: '100%', height: '4px', background: '#1e293b', borderRadius: '2px', overflow: 'hidden' }}>
                <div style={{
                  width: isInitial ? '100%' : `${pct}%`,
                  height: '100%',
                  background: barColor,
                  transition: 'width 0.3s ease',
                }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
