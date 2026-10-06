import React from 'react';
import { Activity, ArrowDownRight, ArrowUpRight, ShieldCheck } from 'lucide-react';

function Finding({ label, value, tone, icon: Icon, loading }) {
  return (
    <div className={`hero-finding hero-finding--${tone}`}>
      <div className="hero-finding__label">
        <Icon size={13} />
        <span>{label}</span>
      </div>
      <strong className={loading ? 'is-loading' : ''}>{loading ? '—' : value}</strong>
    </div>
  );
}

export default function OperationalHero({ benchmarkData }) {
  const findings = benchmarkData?.key_findings;
  const loading = !findings;

  return (
    <section className="operational-hero" aria-labelledby="operations-heading">
      <div className="operational-hero__message">
        <div className="eyebrow">
          <Activity size={13} />
          Predict · Mitigate · Recover
        </div>
        <h2 id="operations-heading">Operate one step ahead of the cascade.</h2>
        <p>
          Forecast downstream failures, apply predictive PPO control, and recover service under AC-feasibility constraints.
        </p>
        <div className="operational-hero__flow" aria-label="Incident workflow">
          <span>01 Contingency</span>
          <span>02 GCN forecast</span>
          <span>03 PPO control</span>
          <span>04 Grid recovery</span>
        </div>
      </div>

      <div className="operational-hero__impact" aria-label="Validated Phase 5.5 findings">
        <div className="operational-hero__impact-heading">
          <div>
            <strong>Validated impact</strong>
            <span>Held-out Phase 5.5 evaluation</span>
          </div>
          <ShieldCheck size={17} />
        </div>
        <div className="operational-hero__findings">
          <Finding
            label="Load served"
            value={`+${findings?.load_served_gain_pp} pp`}
            tone="safe"
            icon={ArrowUpRight}
            loading={loading}
          />
          <Finding
            label="Load shed"
            value={`${findings?.load_shedding_reduction_percent}% less`}
            tone="info"
            icon={ArrowDownRight}
            loading={loading}
          />
          <Finding
            label="Blackout rate"
            value={`−${findings?.blackout_rate_reduction_pp} pp`}
            tone="purple"
            icon={ArrowDownRight}
            loading={loading}
          />
        </div>
      </div>
    </section>
  );
}
