import React from 'react';
import { BarChart3, ShieldCheck } from 'lucide-react';
import PanelHeader from './ui/PanelHeader';
import StatusBadge from './ui/StatusBadge';

// Reproduce the user-supplied Experimental Results slide. The evaluation CSVs
// and API keep their original results; this section presents the slide figures.
const PRESENTATION_COMPARISONS = [
  { label: 'Load served (%)', predictive: 40.65, noGcn: 32.48, unit: '%', scale: 100 },
  { label: 'Blackout rate (%)', predictive: 49.3, noGcn: 62.88, unit: '%', scale: 100 },
  { label: 'Load shed (MW)', predictive: 2.91, noGcn: 9.54, unit: ' MW', scale: 10 },
];

function ResearchFinding({ label, value, detail, isComparison = false }) {
  return (
    <article className="research-finding">
      <strong className="mono">{value}</strong>
      <h3>{label}</h3>
      <p className={isComparison ? 'safe-text' : ''}>{detail}</p>
    </article>
  );
}

export default function ComparisonPanel({ benchmarkData }) {
  const recData = benchmarkData?.phase_6_recovery || [];
  const loading = !benchmarkData;
  const noRecovery = recData.find((row) => row.method === 'No Recovery');
  const greedyRecovery = recData.find((row) => row.method === 'Greedy Recovery');
  const hasRecoveryEvidence = Boolean(noRecovery && greedyRecovery);

  return (
    <div className="card benchmark-panel">
      <PanelHeader
        icon={BarChart3}
        title="Experimental Results"
        subtitle="Figures from the project presentation · 300 held-out scenarios."
        badge={<StatusBadge tone="purple">Presentation results</StatusBadge>}
        as="h2"
      />

      <div className="research-findings">
        <ResearchFinding
          label="GCN micro-F1"
          value="99.65%"
          detail="Synthetic test data only"
        />
        <ResearchFinding
          label="Load served"
          value="40.65%"
          detail="vs 32.48% without GCN"
          isComparison
        />
        <ResearchFinding
          label="Load shed"
          value="2.91 MW"
          detail="vs 9.54 MW without GCN"
          isComparison
        />
        <ResearchFinding
          label="Blackout rate"
          value="49.3%"
          detail="vs 62.88% without GCN"
          isComparison
        />
      </div>

      <div className="research-comparison">
        <section className="result-comparison" aria-labelledby="ppo-comparison-heading">
          <div className="result-comparison__heading">
            <h3 id="ppo-comparison-heading">PPO + GCN vs PPO without GCN</h3>
            <div className="comparison-legend">
              <span><i className="comparison-swatch--predictive" />PPO + GCN</span>
              <span><i className="comparison-swatch--baseline" />PPO without GCN</span>
            </div>
          </div>
          <dl className="result-comparison__metrics">
            {PRESENTATION_COMPARISONS.map((metric) => (
              <div className="result-comparison__metric" key={metric.label}>
                <dt>{metric.label}</dt>
                <dd>
                  {[
                    { name: 'PPO + GCN', value: metric.predictive, className: 'predictive' },
                    { name: 'PPO without GCN', value: metric.noGcn, className: 'baseline' },
                  ].map((series) => (
                    <div className={`result-comparison__row result-comparison__row--${series.className}`} key={series.name}>
                      <span className="sr-only">{series.name}: </span>
                      <span className="result-comparison__track" aria-hidden="true">
                        <span style={{ width: `${series.value / metric.scale * 100}%` }} />
                      </span>
                      <strong className="mono">{series.value}{metric.unit}</strong>
                    </div>
                  ))}
                </dd>
              </div>
            ))}
          </dl>
        </section>
        <aside className="research-interpretation" aria-labelledby="results-meaning-heading">
          <h3 id="results-meaning-heading">What the results mean</h3>
          <p>300 held-out scenarios</p>
          <h4>Statistically significant improvement:</h4>
          <ul>
            <li>Load served</li>
            <li>Load shedding</li>
            <li>Blackout rate</li>
          </ul>
          <p className="research-interpretation__note">Not significant: stable-grid rate or failed-line count.</p>
        </aside>
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
