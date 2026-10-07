import React from 'react';
import { Activity, AlertTriangle, ShieldCheck, Zap, ArrowDownRight, ArrowUpRight } from 'lucide-react';

export default function MetricsOverview({ simResult }) {
  if (!simResult) {
    return null;
  }

  const riskMean = simResult.initial_grid_state?.gcn_risk_mean !== undefined
    ? (simResult.initial_grid_state.gcn_risk_mean * 100).toFixed(1)
    : '0.0';

  const failedCount = simResult.failed_lines?.length || 0;
  const loadServedPct = simResult.final_load_served_percent !== undefined
    ? Number(simResult.final_load_served_percent).toFixed(1)
    : '100.0';

  const finalServedMw = simResult.final_load_served !== undefined
    ? Number(simResult.final_load_served).toFixed(1)
    : '0.0';

  const initialLoadMw = simResult.load_served_before_mitigation !== undefined
    ? Number(simResult.load_served_before_mitigation).toFixed(1)
    : '0.0';

  const status = simResult.final_system_status || 'STABLE';
  const loadShedMw = simResult.audit_log?.reduce((acc, curr) => curr.load_shed_mw || acc, 0.0) || 0.0;
  const loadRestoredMw = simResult.customer_load_restored_mw || 0.0;

  const getStatusBadge = (st) => {
    switch (st) {
      case 'STABLE':
        return { label: 'STABLE GRID', class: 'badge-safe' };
      case 'PARTIAL_BLACKOUT':
        return { label: 'PARTIAL BLACKOUT', class: 'badge-warning' };
      case 'TOTAL_BLACKOUT':
        return { label: 'TOTAL BLACKOUT', class: 'badge-danger' };
      case 'NON_CONVERGED':
        return { label: 'NON-CONVERGENT DIVERGENCE', class: 'badge-danger' };
      default:
        return { label: st, class: 'badge-neutral' };
    }
  };

  const stBadge = getStatusBadge(status);

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
      gap: '16px',
      marginBottom: '24px',
    }}>
      {/* 1. GCN System Risk */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: '#94a3b8' }}>SYSTEM RISK</span>
          <Activity size={16} color="#06b6d4" />
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
          <span className="mono" style={{ fontSize: '26px', fontWeight: 800, color: '#f8fafc' }}>
            {riskMean}%
          </span>
          <span style={{ fontSize: '11px', color: '#64748b' }}>mean GCN</span>
        </div>
        <span className="badge badge-info" style={{ alignSelf: 'flex-start', fontSize: '10px' }}>
          Predictive GCN v2
        </span>
      </div>

      {/* 2. Failed Lines */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: '#94a3b8' }}>FAILED LINES</span>
          <AlertTriangle size={16} color={failedCount > 1 ? '#ef4444' : '#f59e0b'} />
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
          <span className="mono" style={{ fontSize: '26px', fontWeight: 800, color: failedCount > 1 ? '#ef4444' : '#f59e0b' }}>
            {failedCount}
          </span>
          <span style={{ fontSize: '11px', color: '#64748b' }}>of 15 lines</span>
        </div>
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
          {simResult.failed_lines?.map((l) => (
            <span key={l} className="badge badge-danger" style={{ fontSize: '10px', padding: '1px 6px' }}>
              L{l}
            </span>
          ))}
        </div>
      </div>

      {/* 3. Load Served Percent */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: '#94a3b8' }}>LOAD SERVED</span>
          <Zap size={16} color="#10b981" />
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
          <span className="mono" style={{ fontSize: '26px', fontWeight: 800, color: Number(loadServedPct) > 80 ? '#10b981' : Number(loadServedPct) > 30 ? '#f59e0b' : '#ef4444' }}>
            {loadServedPct}%
          </span>
          <span style={{ fontSize: '11px', color: '#64748b' }}>{finalServedMw} / {initialLoadMw} MW</span>
        </div>
        <div style={{ width: '100%', height: '6px', background: '#1e293b', borderRadius: '3px', overflow: 'hidden' }}>
          <div style={{
            width: `${Math.min(100, Math.max(0, Number(loadServedPct)))}%`,
            height: '100%',
            background: Number(loadServedPct) > 80 ? '#10b981' : Number(loadServedPct) > 30 ? '#f59e0b' : '#ef4444',
            transition: 'width 0.4s ease',
          }} />
        </div>
      </div>

      {/* 4. Blackout Status */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: '#94a3b8' }}>SYSTEM STATE</span>
          <ShieldCheck size={16} color={status === 'STABLE' ? '#10b981' : '#ef4444'} />
        </div>
        <div style={{ marginTop: '2px' }}>
          <span className={`badge ${stBadge.class}`} style={{ fontSize: '12px', padding: '6px 12px' }}>
            {stBadge.label}
          </span>
        </div>
        <p style={{ fontSize: '11px', color: '#64748b', margin: '4px 0 0' }}>
          {status === 'STABLE' ? 'Feasible AC operating equilibrium' : 'Service curtailed under stress'}
        </p>
      </div>

      {/* 5. Load Shed MW */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: '#94a3b8' }}>LOAD SHED (PPO)</span>
          <ArrowDownRight size={16} color="#f59e0b" />
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
          <span className="mono" style={{ fontSize: '26px', fontWeight: 800, color: '#f59e0b' }}>
            {Number(loadShedMw).toFixed(1)}
          </span>
          <span style={{ fontSize: '11px', color: '#64748b' }}>MW shed</span>
        </div>
        <p style={{ fontSize: '11px', color: '#64748b', margin: 0 }}>
          Preventive action sacrifice
        </p>
      </div>

      {/* 6. Load Restored MW */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: '#94a3b8' }}>LOAD RESTORED</span>
          <ArrowUpRight size={16} color="#06b6d4" />
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
          <span className="mono" style={{ fontSize: '26px', fontWeight: 800, color: '#06b6d4' }}>
            +{Number(loadRestoredMw).toFixed(1)}
          </span>
          <span style={{ fontSize: '11px', color: '#64748b' }}>MW restored</span>
        </div>
        <p style={{ fontSize: '11px', color: '#64748b', margin: 0 }}>
          Post-cascade service restoration
        </p>
      </div>
    </div>
  );
}
