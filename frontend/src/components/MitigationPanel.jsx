import React from 'react';
import { Shield, Zap, ArrowDown, Activity, CheckCircle2 } from 'lucide-react';

export default function MitigationPanel({ mitigationActions, auditLog, totalLoadShedMw }) {
  const mitigationSteps = auditLog?.filter((l) => l.stage && l.stage.includes('MITIGATION_STEP')) || [];

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Shield size={16} color="#3b82f6" />
          PPO Preventive Mitigation
        </h3>
        <span className="badge badge-info" style={{ fontSize: '10px' }}>
          Predictive Policy
        </span>
      </div>
      <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0 }}>
        Reinforcement-learning agent takes actions guided by downstream failure probabilities to halt cascade propagation.
      </p>

      {/* Summary stats */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '12px',
        padding: '12px',
        background: '#0e1424',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid #1e293b',
      }}>
        <div>
          <span style={{ fontSize: '11px', color: '#94a3b8' }}>Total Load Shed</span>
          <div className="mono" style={{ fontSize: '18px', fontWeight: 700, color: '#f59e0b' }}>
            {Number(totalLoadShedMw || 0).toFixed(2)} MW
          </div>
        </div>
        <div>
          <span style={{ fontSize: '11px', color: '#94a3b8' }}>Mitigation Steps</span>
          <div className="mono" style={{ fontSize: '18px', fontWeight: 700, color: '#38bdf8' }}>
            {mitigationSteps.length}
          </div>
        </div>
      </div>

      {/* Steps List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <span style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
          Action Execution Sequence:
        </span>
        {mitigationSteps.length === 0 ? (
          <div style={{ padding: '12px', background: '#0e1424', borderRadius: 'var(--radius-sm)', fontSize: '12px', color: '#94a3b8', textAlign: 'center' }}>
            No mitigation actions triggered yet.
          </div>
        ) : (
          mitigationSteps.map((step, idx) => (
            <div
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 12px',
                background: '#0e1424',
                border: '1px solid #1e293b',
                borderRadius: 'var(--radius-sm)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span className="mono" style={{ fontSize: '11px', color: '#64748b' }}>
                  #{idx + 1}
                </span>
                <span className="mono" style={{ fontSize: '12px', fontWeight: 600, color: '#f8fafc' }}>
                  {step.action}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                {step.load_shed_mw > 0 && (
                  <span className="badge badge-warning" style={{ fontSize: '10px' }}>
                    -{step.load_shed_mw.toFixed(1)} MW
                  </span>
                )}
                <span className="badge badge-safe" style={{ fontSize: '10px' }}>
                  Reward: {step.reward}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
