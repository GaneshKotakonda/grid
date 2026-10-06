import React from 'react';
import { AlertCircle, CheckCircle2, Network, Zap } from 'lucide-react';
import StatusBadge from './ui/StatusBadge';

export default function Navbar({ isBackendHealthy, onSelectPreset }) {
  return (
    <header className="topbar">
      <div className="topbar__identity">
        <div className="topbar__mark" aria-hidden="true">
          <Zap size={19} />
        </div>
        <div>
          <div className="topbar__title-row">
            <h1>GridResilience</h1>
            <span>Operations Console</span>
          </div>
          <p>Predictive GCN + PPO Mitigation + Safety-Constrained Recovery on IEEE-14</p>
        </div>
      </div>

      <div className="topbar__controls">
        <div className="preset-group" aria-label="Scenario presets">
          <span className="preset-group__label">Presets</span>
          <button onClick={() => onSelectPreset({ line: 1, loadScale: 1.10, capScale: 0.02 })}>
            Moderate
          </button>
          <button onClick={() => onSelectPreset({ line: 2, loadScale: 1.25, capScale: 0.015 })}>
            Stressed
          </button>
          <button onClick={() => onSelectPreset({ line: 0, loadScale: 1.35, capScale: 0.012 })}>
            Severe
          </button>
        </div>

        <div className="topbar__model-badges" aria-label="Active platform components">
          <StatusBadge tone="neutral"><Network size={11} /> IEEE-14</StatusBadge>
          <StatusBadge tone="purple">Predictive GCN</StatusBadge>
          <StatusBadge tone="info">PPO Policy</StatusBadge>
        </div>

        <StatusBadge tone={isBackendHealthy ? 'safe' : 'danger'} dot>
          {isBackendHealthy ? <CheckCircle2 size={11} /> : <AlertCircle size={11} />}
          {isBackendHealthy ? 'FastAPI Connected' : 'API Connecting'}
        </StatusBadge>
      </div>
    </header>
  );
}
