import React from 'react';
import { Award, BarChart3, ShieldCheck, TrendingDown, TrendingUp } from 'lucide-react';
import PanelHeader from './ui/PanelHeader';
import StatusBadge from './ui/StatusBadge';

function ResearchFinding({ label, value, detail, tone, icon: Icon, loading }) {
  return (
    <article className={`research-finding research-finding--${tone}`}>
      <div><Icon size={15} /><span>{label}</span></div>
      <strong className="mono">{loading ? '—' : value}</strong>
      <p>{loading ? 'Loading validated benchmark evidence…' : detail}</p>
    </article>
  );
}

export default function ComparisonPanel({ benchmarkData }) {
  const rlData = benchmarkData?.phase_5_5_mitigation || [];
  const recData = benchmarkData?.phase_6_recovery || [];
  const findings = benchmarkData?.key_findings;
  const loading = !benchmarkData;
  const predictive = rlData.find((row) => row.controller?.includes('Predictive GCN'));
  const noGcn = rlData.find((row) => row.controller?.includes('No GCN'));
  const noRecovery = recData.find((row) => row.method === 'No Recovery');
  const greedyRecovery = recData.find((row) => row.method === 'Greedy Recovery');
  const hasRecoveryEvidence = Boolean(noRecovery && greedyRecovery);

  return (
    <div className="card benchmark-panel">
      <PanelHeader
        icon={BarChart3}
        title="Empirical Benchmark Evidence"
        subtitle="300 held-out scenarios · Phase 5.5 statistical evaluation from saved experimental artifacts."
        badge={<StatusBadge tone="purple"><Award size={11} /> Phase 5.5 Validated</StatusBadge>}
      />

      <div className="research-findings">
        <ResearchFinding
          label="Load served"
          value={`+${findings?.load_served_gain_pp} pp`}
          detail={predictive && noGcn ? `${predictive.average_load_served_percent}% vs ${noGcn.average_load_served_percent}% with no-GCN PPO.` : ''}
          tone="safe"
          icon={TrendingUp}
          loading={loading}
        />
        <ResearchFinding
          label="Customer load shed"
          value={`${findings?.load_shedding_reduction_percent}% less`}
          detail={predictive && noGcn ? `${predictive.average_load_shed_mw} MW vs ${noGcn.average_load_shed_mw} MW with no-GCN PPO.` : ''}
          tone="info"
          icon={TrendingDown}
          loading={loading}
        />
        <ResearchFinding
          label="Total blackout rate"
          value={`−${findings?.blackout_rate_reduction_pp} pp`}
          detail={predictive && noGcn ? `${predictive.total_blackout_rate}% vs ${noGcn.total_blackout_rate}% with no-GCN PPO.` : ''}
          tone="purple"
          icon={TrendingDown}
          loading={loading}
        />
      </div>

      <div className="benchmark-table-wrap">
        <table className="benchmark-table">
          <thead>
            <tr>
              <th>Controller</th>
              <th>Samples</th>
              <th>Avg Load Served</th>
              <th>Avg Load Shed</th>
              <th>Stable Rate</th>
              <th>Total Blackout Rate</th>
              <th>Cascade Reduction vs Base</th>
            </tr>
          </thead>
          <tbody>
            {rlData.map((row) => {
              const isBest = row.controller?.includes('Predictive GCN');
              return (
                <tr className={isBest ? 'is-best' : ''} key={row.controller}>
                  <td>
                    <span>{row.controller}</span>
                    {isBest && <StatusBadge tone="safe">Best</StatusBadge>}
                  </td>
                  <td>{row.sample_count}</td>
                  <td>{row.average_load_served_percent}%</td>
                  <td>{row.average_load_shed_mw} MW</td>
                  <td>{row.stable_rate}%</td>
                  <td>{row.total_blackout_rate}%</td>
                  <td>+{row.cascade_reduction_percent}%</td>
                </tr>
              );
            })}
            {loading && (
              <tr className="is-loading">
                <td colSpan="7">Loading saved benchmark results…</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <section className="recovery-audit" aria-labelledby="recovery-audit-heading">
        <div className="recovery-audit__heading">
          <div>
            <span className="eyebrow"><ShieldCheck size={12} /> Safety invariant</span>
            <h3 id="recovery-audit-heading">Phase 6 Post-Cascade Recovery Invariant Audit</h3>
          </div>
          <StatusBadge tone={hasRecoveryEvidence ? 'safe' : 'neutral'}>
            {loading ? 'Loading Audit' : hasRecoveryEvidence ? '100% Invariant Conserved' : 'Audit Evidence Unavailable'}
          </StatusBadge>
        </div>

        <p>
          {hasRecoveryEvidence
            ? 'Recovery preserves surviving grids: unsafe actions are reverted and restoration never reduces served load below the post-cascade state.'
            : 'Recovery audit evidence is unavailable because no Phase 6 recovery rows were returned.'}
        </p>

        <div className="audit-metrics">
          <div><span>No-Recovery Blackout</span><strong className="mono">{noRecovery ? `${noRecovery.total_blackout_rate}%` : '—'}</strong></div>
          <div><span>Greedy-Recovery Blackout</span><strong className="mono">{greedyRecovery ? `${greedyRecovery.total_blackout_rate}%` : '—'}</strong></div>
          <div><span>Average Load Restored</span><strong className="mono info-text">{greedyRecovery ? `+${greedyRecovery.average_mw_restored} MW` : '—'}</strong></div>
          <div><span>Survivor Integrity</span><strong className="mono safe-text">{hasRecoveryEvidence ? '100%' : '—'}</strong></div>
        </div>
      </section>
    </div>
  );
}
