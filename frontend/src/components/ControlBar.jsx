import React from 'react';
import { AlertTriangle, Play, SlidersHorizontal } from 'lucide-react';
import PanelHeader from './ui/PanelHeader';
import StatusBadge from './ui/StatusBadge';

const LINE_NAMES = [
  'Line 0 (Bus 1 - Bus 2)',
  'Line 1 (Bus 1 - Bus 5)',
  'Line 2 (Bus 2 - Bus 3)',
  'Line 3 (Bus 2 - Bus 4)',
  'Line 4 (Bus 2 - Bus 5)',
  'Line 5 (Bus 3 - Bus 4)',
  'Line 6 (Bus 4 - Bus 5)',
  'Line 7 (Bus 6 - Bus 11)',
  'Line 8 (Bus 6 - Bus 12)',
  'Line 9 (Bus 6 - Bus 13)',
  'Line 10 (Bus 9 - Bus 10)',
  'Line 11 (Bus 9 - Bus 14)',
  'Line 12 (Bus 10 - Bus 11)',
  'Line 13 (Bus 12 - Bus 13)',
  'Line 14 (Bus 13 - Bus 14)',
];

export default function ControlBar({
  initialOutage,
  setInitialOutage,
  loadScale,
  setLoadScale,
  capacityScale,
  setCapacityScale,
  seed,
  setSeed,
  onRunSimulation,
  isLoading,
  simStage,
}) {
  return (
    <section className="command-deck" aria-labelledby="command-deck-heading">
      <PanelHeader
        icon={SlidersHorizontal}
        title="Scenario Command Deck"
        subtitle="Configure an initiating outage and operating stress, then execute the full predictive incident workflow."
        badge={<StatusBadge tone="neutral">Seed-Locked Run</StatusBadge>}
        as="h2"
        headingId="command-deck-heading"
      />

      <div className="command-deck__controls">
        <label className="field field--outage">
          <span><AlertTriangle size={12} /> Initiating outage</span>
          <select
            value={initialOutage}
            onChange={(e) => setInitialOutage(Number(e.target.value))}
            disabled={isLoading}
          >
            {LINE_NAMES.map((name, idx) => (
              <option key={idx} value={idx}>{name}</option>
            ))}
          </select>
        </label>

        <label className="field field--range">
          <span>
            Load stress
            <strong className="mono">{(loadScale * 100).toFixed(0)}% · {loadScale.toFixed(2)}x</strong>
          </span>
          <input
            type="range"
            min="0.80"
            max="1.50"
            step="0.05"
            value={loadScale}
            onChange={(e) => setLoadScale(Number(e.target.value))}
            disabled={isLoading}
          />
        </label>

        <label className="field">
          <span>Line capacity</span>
          <select
            value={capacityScale}
            onChange={(e) => setCapacityScale(Number(e.target.value))}
            disabled={isLoading}
          >
            <option value={0.012}>0.012 · Heavily Stressed</option>
            <option value={0.015}>0.015 · Stressed</option>
            <option value={0.020}>0.020 · Nominal Design</option>
            <option value={0.025}>0.025 · Relaxed</option>
          </select>
        </label>

        <label className="field field--seed">
          <span>Seed</span>
          <input
            type="number"
            min="0"
            step="1"
            value={seed}
            onChange={(e) => setSeed(Number(e.target.value))}
            disabled={isLoading}
          />
        </label>

        <button className="run-button" onClick={onRunSimulation} disabled={isLoading}>
          {isLoading ? <span className="spinner" aria-hidden="true" /> : <Play size={16} fill="currentColor" />}
          <span>{isLoading ? 'Running Pipeline' : 'Run GridResilience'}</span>
        </button>
      </div>

      <div className={`command-deck__status ${isLoading ? 'is-running' : ''}`} role="status">
        <span className="command-deck__status-dot" />
        {isLoading
          ? (simStage || 'Executing incident pipeline...')
          : 'Ready. Configure a scenario and execute the predictive incident workflow.'}
      </div>
    </section>
  );
}
