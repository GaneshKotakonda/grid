import React from 'react';
import { BarChart2, TrendingUp, ShieldCheck, Award } from 'lucide-react';

export default function ComparisonPanel({ benchmarkData }) {
  const rlData = benchmarkData?.phase_5_5_mitigation || [];
  const recData = benchmarkData?.phase_6_recovery || [];
  const findings = benchmarkData?.key_findings || {
    load_served_gain_pp: 4.17,
    load_shedding_reduction_percent: 69.5,
    blackout_rate_reduction_pp: 3.0,
  };

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <h3 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <BarChart2 size={18} color="#06b6d4" />
            Empirical Benchmark Comparison & Phase 5.5 Findings
          </h3>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '2px 0 0' }}>
            Held-out 300-scenario evaluation comparing mitigation controllers and recovery audit results from saved artifacts.
          </p>
        </div>
        <span className="badge badge-purple" style={{ fontSize: '11px', display: 'flex', alignItems: 'center', gap: '5px' }}>
          <Award size={13} />
          Phase 5.5 Validated
        </span>
      </div>

      {/* Research Highlight Badges / Callouts */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '14px',
      }}>
        <div style={{
          padding: '14px 18px',
          background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(6, 182, 212, 0.08) 100%)',
          border: '1px solid rgba(16, 185, 129, 0.35)',
          borderRadius: 'var(--radius-md)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#10b981', fontWeight: 700, fontSize: '13px' }}>
            <TrendingUp size={16} />
            <span>+{findings.load_served_gain_pp}% LOAD SERVED</span>
          </div>
          <div style={{ fontSize: '20px', fontWeight: 800, color: '#f8fafc', margin: '4px 0', fontFamily: 'JetBrains Mono' }}>
            30.65% vs 26.48%
          </div>
          <div style={{ fontSize: '11.5px', color: '#94a3b8' }}>
            Predictive GCN guidance outperforms No-GCN PPO by +4.17 pp across 300 test scenarios.
          </div>
        </div>

        <div style={{
          padding: '14px 18px',
          background: 'linear-gradient(135deg, rgba(6, 182, 212, 0.12) 0%, rgba(59, 130, 246, 0.08) 100%)',
          border: '1px solid rgba(6, 182, 212, 0.35)',
          borderRadius: 'var(--radius-md)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#06b6d4', fontWeight: 700, fontSize: '13px' }}>
            <ShieldCheck size={16} />
            <span>69.5% LESS LOAD SHED</span>
          </div>
          <div style={{ fontSize: '20px', fontWeight: 800, color: '#f8fafc', margin: '4px 0', fontFamily: 'JetBrains Mono' }}>
            2.91 MW vs 9.54 MW
          </div>
          <div style={{ fontSize: '11.5px', color: '#94a3b8' }}>
            Targeted failure prediction prevents unnecessary load cuts, preserving 6.63 MW customer load.
          </div>
        </div>

        <div style={{
          padding: '14px 18px',
          background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.12) 0%, rgba(236, 72, 153, 0.08) 100%)',
          border: '1px solid rgba(139, 92, 246, 0.35)',
          borderRadius: 'var(--radius-md)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#c084fc', fontWeight: 700, fontSize: '13px' }}>
            <Award size={16} />
            <span>3.0 pp BLACKOUT REDUCTION</span>
          </div>
          <div style={{ fontSize: '20px', fontWeight: 800, color: '#f8fafc', margin: '4px 0', fontFamily: 'JetBrains Mono' }}>
            68.33% vs 71.33%
          </div>
          <div style={{ fontSize: '11.5px', color: '#94a3b8' }}>
            Total blackout rate reduced from 71.33% (No-GCN) and 73.0% (Do-Nothing) to 68.33%.
          </div>
        </div>
      </div>

      {/* Comparison Table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8' }}>
              <th style={{ padding: '10px 12px' }}>Controller</th>
              <th style={{ padding: '10px 12px' }}>Samples</th>
              <th style={{ padding: '10px 12px' }}>Avg Load Served (%)</th>
              <th style={{ padding: '10px 12px' }}>Avg Load Shed (MW)</th>
              <th style={{ padding: '10px 12px' }}>Stable Rate (%)</th>
              <th style={{ padding: '10px 12px' }}>Total Blackout Rate (%)</th>
              <th style={{ padding: '10px 12px' }}>Cascade Reduction vs Base</th>
            </tr>
          </thead>
          <tbody>
            {rlData.map((row, idx) => {
              const isBest = row.controller?.includes('Predictive GCN');
              return (
                <tr
                  key={idx}
                  style={{
                    borderBottom: '1px solid #1e293b',
                    background: isBest ? 'rgba(6, 182, 212, 0.08)' : 'transparent',
                    fontWeight: isBest ? 700 : 500,
                  }}
                >
                  <td style={{ padding: '12px', color: isBest ? '#38bdf8' : '#f8fafc' }}>
                    {row.controller}
                    {isBest && <span className="badge badge-info" style={{ marginLeft: '8px', fontSize: '9px' }}>BEST</span>}
                  </td>
                  <td style={{ padding: '12px', color: '#cbd5e1' }} className="mono">{row.sample_count}</td>
                  <td style={{ padding: '12px', color: isBest ? '#10b981' : '#cbd5e1' }} className="mono">
                    {row.average_load_served_percent}%
                  </td>
                  <td style={{ padding: '12px', color: isBest ? '#38bdf8' : '#cbd5e1' }} className="mono">
                    {row.average_load_shed_mw} MW
                  </td>
                  <td style={{ padding: '12px', color: '#cbd5e1' }} className="mono">{row.stable_rate}%</td>
                  <td style={{ padding: '12px', color: isBest ? '#10b981' : '#ef4444' }} className="mono">
                    {row.total_blackout_rate}%
                  </td>
                  <td style={{ padding: '12px', color: isBest ? '#10b981' : '#cbd5e1' }} className="mono">
                    +{row.cascade_reduction_percent}%
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Phase 6 Recovery Audit Row */}
      {recData.length > 0 && (
        <div style={{
          marginTop: '8px',
          padding: '14px',
          background: '#0e1424',
          borderRadius: 'var(--radius-md)',
          border: '1px solid #1e293b',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '13px', fontWeight: 700, color: '#f8fafc' }}>
              Phase 6 Post-Cascade Recovery Invariant Audit
            </span>
            <span className="badge badge-safe" style={{ fontSize: '10px' }}>
              100% Invariant Conserved
            </span>
          </div>
          <p style={{ fontSize: '11.5px', color: '#94a3b8', margin: '0 0 10px' }}>
            The Phase 6 result-audit verified that Greedy Recovery never demotes or corrupts surviving grids:
            No-Recovery remaining blackout rate is exactly <strong style={{ color: '#f8fafc' }}>74.0%</strong>, and
            Greedy-Recovery remaining blackout rate is exactly <strong style={{ color: '#10b981' }}>74.0%</strong> with +0.28 MW average load restored.
          </p>
          <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap', fontSize: '11px', color: '#cbd5e1' }}>
            <div>No-Recovery Blackout: <span className="mono" style={{ fontWeight: 700, color: '#f8fafc' }}>74.0%</span></div>
            <div>Greedy-Recovery Blackout: <span className="mono" style={{ fontWeight: 700, color: '#10b981' }}>74.0%</span></div>
            <div>Average Load Restored: <span className="mono" style={{ fontWeight: 700, color: '#38bdf8' }}>+0.28 MW</span></div>
            <div>Survivor Integrity: <span className="mono" style={{ fontWeight: 700, color: '#10b981' }}>100% (0 Corrupted)</span></div>
          </div>
        </div>
      )}
    </div>
  );
}
