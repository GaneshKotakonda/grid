import React from 'react';
import { BrainCircuit } from 'lucide-react';
import PanelHeader from './ui/PanelHeader';
import StatusBadge from './ui/StatusBadge';

export default function FailurePredictionPanel({ predictions, initialOutages = [] }) {
  const getRiskBadge = (prob, isInit) => {
    if (isInit) return <StatusBadge tone="neutral">Outage Trigger · Tripped</StatusBadge>;
    if (prob >= 0.50) return <StatusBadge tone="danger">Critical</StatusBadge>;
    if (prob >= 0.20) return <StatusBadge tone="warning">High</StatusBadge>;
    if (prob >= 0.05) return <StatusBadge tone="info">Moderate</StatusBadge>;
    return <StatusBadge tone="safe">Low</StatusBadge>;
  };

  const getBarColor = (prob, isInit) => {
    if (isInit) return 'var(--text-muted)';
    if (prob >= 0.50) return 'var(--color-danger)';
    if (prob >= 0.20) return 'var(--color-warning)';
    if (prob >= 0.05) return 'var(--color-info)';
    return 'var(--color-safe)';
  };

  const sorted = predictions ? [...predictions].sort((a, b) => b.probability - a.probability) : [];

  return (
    <div className="card intelligence-panel forecast-panel">
      <PanelHeader
        icon={BrainCircuit}
        title="Predictive GCN Failure Probabilities"
        subtitle="Predictive v2 GCN · downstream secondary propagation horizon"
        badge={<StatusBadge tone="purple">{sorted.length || 15} Lines</StatusBadge>}
      />

      {sorted.length === 0 ? (
        <div className="panel-empty">
          <BrainCircuit size={22} />
          <strong>Awaiting GCN forecast</strong>
          <span>Run a scenario to generate all 15 line failure probabilities.</span>
        </div>
      ) : (
        <div className="forecast-list">
          {sorted.map((item, idx) => {
            const isInitial = item.is_initial_outage || initialOutages.includes(item.line_index);
            const pct = (item.probability * 100).toFixed(1);
            const barColor = getBarColor(item.probability, isInitial);

            return (
              <article className={`forecast-row ${isInitial ? 'is-outage' : ''}`} key={item.line_index}>
                <div className="forecast-row__main">
                  <span className="forecast-row__rank mono">#{idx + 1}</span>
                  <div className="forecast-row__line">
                    <strong>Line {item.line_index}</strong>
                    <span>Bus {item.from_bus + 1} ↔ Bus {item.to_bus + 1}</span>
                  </div>
                  <div className="forecast-row__risk">
                    {getRiskBadge(item.probability, isInitial)}
                    <strong className="mono" style={{ color: barColor }}>
                      {isInitial ? 'TRIPPED' : `${pct}%`}
                    </strong>
                  </div>
                </div>
                <div className="forecast-row__bar">
                  <div style={{ width: isInitial ? '100%' : `${pct}%`, background: barColor }} />
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
