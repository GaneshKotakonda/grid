import React from 'react';
import { Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, ShieldCheck, Zap } from 'lucide-react';
import MetricCard from './ui/MetricCard';
import StatusBadge from './ui/StatusBadge';

export default function MetricsOverview({ simResult }) {
  const hasResult = Boolean(simResult);
  const riskMean = simResult?.initial_grid_state?.gcn_risk_mean !== undefined
    ? (simResult.initial_grid_state.gcn_risk_mean * 100).toFixed(1)
    : null;
  const failedCount = simResult?.failed_lines?.length || 0;
  const loadServedPct = simResult?.final_load_served_percent !== undefined
    ? Number(simResult.final_load_served_percent).toFixed(1)
    : null;
  const finalServedMw = simResult?.final_load_served !== undefined
    ? Number(simResult.final_load_served).toFixed(1)
    : null;
  const initialLoadMw = simResult?.load_served_before_mitigation !== undefined
    ? Number(simResult.load_served_before_mitigation).toFixed(1)
    : null;
  const status = simResult?.final_system_status || 'READY';
  const loadShedMw = simResult?.audit_log?.reduce((acc, curr) => curr.load_shed_mw || acc, 0.0) || 0.0;
  const loadRestoredMw = simResult?.customer_load_restored_mw || 0.0;

  const statusMeta = {
    STABLE: { label: 'STABLE GRID', tone: 'safe', hint: 'Feasible AC operating equilibrium' },
    PARTIAL_BLACKOUT: { label: 'PARTIAL BLACKOUT', tone: 'warning', hint: 'Service curtailed under stress' },
    TOTAL_BLACKOUT: { label: 'TOTAL BLACKOUT', tone: 'danger', hint: 'Service curtailed under stress' },
    NON_CONVERGED: { label: 'NON-CONVERGED', tone: 'danger', hint: 'Power flow did not converge' },
    READY: { label: 'READY', tone: 'neutral', hint: 'Awaiting incident execution' },
  }[status] || { label: status, tone: 'neutral', hint: 'Final grid classification' };

  const loadTone = !hasResult
    ? 'neutral'
    : Number(loadServedPct) > 80
      ? 'safe'
      : Number(loadServedPct) > 30
        ? 'warning'
        : 'danger';

  return (
    <section className="metrics-grid" aria-label="System performance indicators">
      <MetricCard
        label="System Risk"
        value={hasResult ? `${riskMean}%` : '—'}
        icon={Activity}
        tone={hasResult && Number(riskMean) >= 20 ? 'warning' : 'info'}
        hint="Mean downstream failure probability"
        footer={<StatusBadge tone="purple">Predictive GCN v2</StatusBadge>}
      />

      <MetricCard
        label="Failed Lines"
        value={hasResult ? failedCount : '—'}
        unit={hasResult ? 'of 15 lines' : undefined}
        icon={AlertTriangle}
        tone={hasResult && failedCount > 1 ? 'danger' : 'warning'}
        hint="Outage plus secondary trips"
        footer={hasResult && simResult.failed_lines?.length > 0 ? (
          <div className="metric-card__chips">
            {simResult.failed_lines.map((line) => <StatusBadge key={line} tone="danger">L{line}</StatusBadge>)}
          </div>
        ) : null}
      />

      <MetricCard
        label="Load Served"
        value={hasResult ? `${loadServedPct}%` : '—'}
        unit={hasResult ? `${finalServedMw} / ${initialLoadMw} MW` : undefined}
        icon={Zap}
        tone={loadTone}
        hint="Customer load served after recovery"
      >
        <div className="metric-progress" aria-hidden="true">
          <div style={{ width: hasResult ? `${Math.min(100, Math.max(0, Number(loadServedPct)))}%` : '0%' }} />
        </div>
      </MetricCard>

      <MetricCard
        label="System State"
        value={statusMeta.label}
        icon={ShieldCheck}
        tone={statusMeta.tone}
        hint={statusMeta.hint}
        className="metric-card--status"
      />

      <MetricCard
        label="Load Shed (PPO)"
        value={hasResult ? Number(loadShedMw).toFixed(1) : '—'}
        unit={hasResult ? 'MW shed' : undefined}
        icon={ArrowDownRight}
        tone="warning"
        hint="Preventive action sacrifice"
      />

      <MetricCard
        label="Load Restored"
        value={hasResult ? `+${Number(loadRestoredMw).toFixed(1)}` : '—'}
        unit={hasResult ? 'MW restored' : undefined}
        icon={ArrowUpRight}
        tone="info"
        hint="Safety-constrained service recovery"
      />
    </section>
  );
}
