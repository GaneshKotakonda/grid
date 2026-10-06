import React from 'react';
import { CheckCircle2, RefreshCw } from 'lucide-react';
import PanelHeader from './ui/PanelHeader';
import StatusBadge from './ui/StatusBadge';

export default function RecoveryPanel({
  reconnectedLines = [],
  customerLoadRestoredMw = 0,
  finalLoadServed = 0,
  finalLoadServedPct = 0,
  postCascadeServedMw = 0,
  recoveryActions = [],
  finalStatus = null,
}) {
  const committedActions = recoveryActions.filter((action) => action.committed);
  const hasResult = Boolean(finalStatus);
  const statusTone = finalStatus === 'STABLE' ? 'safe' : finalStatus === 'PARTIAL_BLACKOUT' ? 'warning' : 'danger';

  return (
    <div className="card intelligence-panel recovery-panel">
      <PanelHeader
        icon={RefreshCw}
        title="Safety-Constrained Grid Recovery"
        subtitle="Sequential reclosure and load restoration under AC-feasibility constraints."
        badge={(
          <StatusBadge tone={hasResult ? statusTone : 'neutral'}>
            {hasResult ? `Phase 6 · ${finalStatus}` : 'Awaiting Incident'}
          </StatusBadge>
        )}
      />

      <div className="panel-stat-grid">
        <div><span>Load Restored</span><strong className="mono safe-text">+{Number(customerLoadRestoredMw).toFixed(2)} MW</strong></div>
        <div><span>Lines Reconnected</span><strong className="mono info-text">{reconnectedLines.length}</strong></div>
        <div><span>Pre-Recovery Load</span><strong className="mono">{Number(postCascadeServedMw).toFixed(1)} MW</strong></div>
        <div><span>Final Load Served</span><strong className="mono">{Number(finalLoadServed).toFixed(1)} MW · {Number(finalLoadServedPct).toFixed(1)}%</strong></div>
      </div>

      <div className="action-block">
        <div className="action-block__label"><span>Reclosed Transmission Lines</span></div>
        <div className="reclosed-lines">
          {reconnectedLines.length === 0
            ? <span>No transmission lines reclosed.</span>
            : reconnectedLines.map((line) => <StatusBadge key={line} tone="info">Line {line} · Reclosed</StatusBadge>)}
        </div>
      </div>

      <div className="action-block">
        <div className="action-block__label">
          <span>Committed Restoration Actions</span>
          <span>{committedActions.length}</span>
        </div>
        <div className="action-list recovery-actions">
          {committedActions.length === 0 ? (
            <div className="panel-empty panel-empty--compact">No restoration actions committed.</div>
          ) : committedActions.map((action, idx) => (
            <div className="action-row" key={`${action.action}-${idx}`}>
              <div className="action-row__name">
                <CheckCircle2 size={13} />
                <strong className="mono">{action.action}</strong>
              </div>
              <strong className="mono info-text">{action.served_load_mw?.toFixed(1)} MW</strong>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
