import React, { useState } from 'react';
import { GitCommit, ArrowRight, Zap, AlertTriangle, Shield, CheckCircle, RefreshCw } from 'lucide-react';

export default function CascadeTimeline({ auditLog, finalStatus }) {
  if (!auditLog || auditLog.length === 0) {
    return (
      <div className="card" style={{ height: '240px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>Simulation timeline will appear after running an incident.</p>
      </div>
    );
  }

  // Group events by stage
  const contingencyEvent = auditLog.find((e) => e.stage === '1_CONTINGENCY');
  const mitigationEvents = auditLog.filter((e) => e.stage?.includes('MITIGATION_STEP'));
  const cascadeEvent = auditLog.find((e) => e.stage === '3_CASCADE_RESULT');
  const recoveryEvents = auditLog.filter((e) => e.stage?.includes('RECOVERY_STEP'));

  const stages = [
    {
      id: 'contingency',
      title: 'Initial Outage',
      desc: `Line ${contingencyEvent?.initial_outages?.join(', ')} tripped`,
      metric: `${contingencyEvent?.initial_load_mw?.toFixed(1) || 0} MW Base Load`,
      status: 'CONTINGENCY',
      icon: <AlertTriangle size={15} color="#f59e0b" />,
      color: '#f59e0b',
    },
    {
      id: 'gcn',
      title: 'GCN Risk Assessment',
      desc: `Risk Mean: ${((contingencyEvent?.gcn_risk_mean || 0) * 100).toFixed(1)}%`,
      metric: 'Predictive-v2 GCN',
      status: 'INFERENCE',
      icon: <Zap size={15} color="#06b6d4" />,
      color: '#06b6d4',
    },
    {
      id: 'mitigation',
      title: 'PPO Mitigation',
      desc: mitigationEvents.length > 0 ? `${mitigationEvents.length} Actions Executed` : 'Do Nothing',
      metric: `${mitigationEvents[mitigationEvents.length - 1]?.load_shed_mw?.toFixed(1) || 0} MW Shed`,
      status: 'MITIGATING',
      icon: <Shield size={15} color="#3b82f6" />,
      color: '#3b82f6',
    },
    {
      id: 'cascade',
      title: 'Post-Cascade State',
      desc: `${cascadeEvent?.tripped_lines_count || 0} Lines Tripped`,
      metric: `${cascadeEvent?.served_load_mw?.toFixed(1) || 0} MW Served (${cascadeEvent?.load_served_percent || 0}%)`,
      status: cascadeEvent?.status || 'UNKNOWN',
      icon: <AlertTriangle size={15} color={cascadeEvent?.status === 'STABLE' ? '#10b981' : '#ef4444'} />,
      color: cascadeEvent?.status === 'STABLE' ? '#10b981' : '#ef4444',
    },
    {
      id: 'recovery',
      title: 'Grid Recovery',
      desc: `${recoveryEvents.filter((r) => r.committed).length} Reconnections Committed`,
      metric: `Final Status: ${finalStatus}`,
      status: 'RECOVERY',
      icon: <RefreshCw size={15} color="#10b981" />,
      color: '#10b981',
    },
  ];

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <GitCommit size={16} color="#06b6d4" />
          Incident Progression & Cascade Timeline
        </h3>
        <span className="badge badge-info" style={{ fontSize: '10px' }}>
          End-to-End Trace
        </span>
      </div>

      {/* Stepper horizontal line */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: '12px',
        position: 'relative',
      }}>
        {stages.map((st, idx) => (
          <div
            key={st.id}
            style={{
              padding: '14px',
              background: '#0e1424',
              border: `1px solid ${st.color}40`,
              borderRadius: 'var(--radius-md)',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
              boxShadow: `0 4px 15px -3px ${st.color}20`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                {st.icon}
                <span style={{ fontSize: '12px', fontWeight: 700, color: '#f8fafc' }}>
                  {st.title}
                </span>
              </div>
              <span className="mono" style={{ fontSize: '10px', color: '#64748b' }}>
                Stage {idx + 1}
              </span>
            </div>

            <p style={{ fontSize: '11.5px', color: '#94a3b8', margin: 0 }}>
              {st.desc}
            </p>

            <div style={{
              fontSize: '11px',
              fontWeight: 600,
              color: st.color,
              marginTop: '4px',
              fontFamily: 'JetBrains Mono',
            }}>
              {st.metric}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
