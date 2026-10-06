import React from 'react';
import { ShieldCheck } from 'lucide-react';
import PanelHeader from './ui/PanelHeader';
import StatusBadge from './ui/StatusBadge';

export default function MitigationPanel({ mitigationActions, auditLog, totalLoadShedMw }) {
  const mitigationSteps = auditLog?.filter((item) => item.stage && item.stage.includes('MITIGATION_STEP')) || [];

  return (
    <div className="card intelligence-panel mitigation-panel">
      <PanelHeader
        icon={ShieldCheck}
        title="PPO Preventive Mitigation"
        subtitle="Predictive policy actions selected before downstream propagation."
        badge={<StatusBadge tone="safe">Predictive Policy</StatusBadge>}
      />

      <div className="panel-stat-grid panel-stat-grid--two">
        <div>
          <span>Total Load Shed</span>
          <strong className="mono warning-text">{Number(totalLoadShedMw || 0).toFixed(2)} MW</strong>
        </div>
        <div>
          <span>Mitigation Steps</span>
          <strong className="mono info-text">{mitigationSteps.length}</strong>
        </div>
      </div>

      <div className="action-block">
        <div className="action-block__label">
          <span>Action Execution Sequence</span>
          {mitigationActions?.length > 0 && <span>{mitigationActions.length} policy outputs</span>}
        </div>
        <div className="action-list">
          {mitigationSteps.length === 0 ? (
            <div className="panel-empty panel-empty--compact">No mitigation actions triggered yet.</div>
          ) : (
            mitigationSteps.map((step, idx) => (
              <div className="action-row" key={`${step.stage}-${idx}`}>
                <div className="action-row__name">
                  <span className="mono">{String(idx + 1).padStart(2, '0')}</span>
                  <strong className="mono">{step.action}</strong>
                </div>
                <div className="action-row__meta">
                  {step.load_shed_mw > 0 && <StatusBadge tone="warning">−{step.load_shed_mw.toFixed(1)} MW</StatusBadge>}
                  <StatusBadge tone="safe">Reward {step.reward}</StatusBadge>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
