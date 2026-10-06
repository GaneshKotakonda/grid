import React from 'react';
import { AlertTriangle, BrainCircuit, GitCommit, RefreshCw, ShieldCheck } from 'lucide-react';
import PanelHeader from './ui/PanelHeader';
import StatusBadge from './ui/StatusBadge';

export default function CascadeTimeline({ auditLog, finalStatus }) {
  const hasTrace = Boolean(auditLog?.length);
  const contingencyEvent = auditLog?.find((event) => event.stage === '1_CONTINGENCY');
  const mitigationEvents = auditLog?.filter((event) => event.stage?.includes('MITIGATION_STEP')) || [];
  const cascadeEvent = auditLog?.find((event) => event.stage === '3_CASCADE_RESULT');
  const recoveryEvents = auditLog?.filter((event) => event.stage?.includes('RECOVERY_STEP')) || [];

  const stages = [
    {
      id: 'contingency',
      title: 'Initial Outage',
      desc: hasTrace ? `Line ${contingencyEvent?.initial_outages?.join(', ')} disconnected` : 'Selected line disconnected',
      metric: hasTrace ? `${contingencyEvent?.initial_load_mw?.toFixed(1) || 0} MW base load` : 'Waiting',
      tone: 'warning',
      icon: AlertTriangle,
    },
    {
      id: 'gcn',
      title: 'GCN Risk Assessment',
      desc: hasTrace ? `Mean risk ${((contingencyEvent?.gcn_risk_mean || 0) * 100).toFixed(1)}%` : 'Downstream propagation inferred',
      metric: hasTrace ? 'Predictive-v2 GCN' : 'Waiting',
      tone: 'purple',
      icon: BrainCircuit,
    },
    {
      id: 'mitigation',
      title: 'PPO Mitigation',
      desc: hasTrace
        ? (mitigationEvents.length > 0 ? `${mitigationEvents.length} actions executed` : 'Do nothing')
        : 'Preventive action applied',
      metric: hasTrace ? `${mitigationEvents[mitigationEvents.length - 1]?.load_shed_mw?.toFixed(1) || 0} MW shed` : 'Waiting',
      tone: 'info',
      icon: ShieldCheck,
    },
    {
      id: 'cascade',
      title: 'Post-Cascade State',
      desc: hasTrace ? `${cascadeEvent?.tripped_lines_count || 0} lines tripped` : 'AC redistribution evaluated',
      metric: hasTrace
        ? `${cascadeEvent?.served_load_mw?.toFixed(1) || 0} MW served · ${cascadeEvent?.load_served_percent || 0}%`
        : 'Waiting',
      tone: cascadeEvent?.status === 'STABLE' ? 'safe' : hasTrace ? 'danger' : 'neutral',
      icon: AlertTriangle,
    },
    {
      id: 'recovery',
      title: 'Grid Recovery',
      desc: hasTrace
        ? `${recoveryEvents.filter((event) => event.committed).length} actions committed`
        : 'Safe reclosure and load pickup',
      metric: hasTrace ? `Final state · ${finalStatus}` : 'Waiting',
      tone: hasTrace && finalStatus === 'STABLE' ? 'safe' : hasTrace ? 'warning' : 'neutral',
      icon: RefreshCw,
    },
  ];

  return (
    <div className="card timeline-panel">
      <PanelHeader
        icon={GitCommit}
        title="Incident Progression & Cascade Timeline"
        subtitle="One operational trace from initiating contingency through safety-constrained restoration."
        badge={<StatusBadge tone={hasTrace ? 'info' : 'neutral'}>{hasTrace ? 'Completed Trace' : 'Awaiting Incident'}</StatusBadge>}
      />

      <div className="timeline-track">
        {stages.map(({ id, title, desc, metric, tone, icon: Icon }, idx) => (
          <article className={`timeline-stage timeline-stage--${tone}`} key={id}>
            <div className="timeline-stage__top">
              <span className="timeline-stage__index mono">{idx + 1}</span>
              <Icon size={14} />
              <StatusBadge tone={hasTrace ? tone : 'neutral'}>{hasTrace ? 'Complete' : 'Waiting'}</StatusBadge>
            </div>
            <strong>{title}</strong>
            <p>{desc}</p>
            <span className="timeline-stage__metric mono">{metric}</span>
          </article>
        ))}
      </div>
    </div>
  );
}
