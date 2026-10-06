import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import ControlBar from './components/ControlBar';
import TopologyGraph from './components/TopologyGraph';
import MetricsOverview from './components/MetricsOverview';
import FailurePredictionPanel from './components/FailurePredictionPanel';
import MitigationPanel from './components/MitigationPanel';
import CascadeTimeline from './components/CascadeTimeline';
import RecoveryPanel from './components/RecoveryPanel';
import ComparisonPanel from './components/ComparisonPanel';
import AppShell from './components/ui/AppShell';
import OperationalHero from './components/ui/OperationalHero';

export default function App() {
  const [isBackendHealthy, setIsBackendHealthy] = useState(false);
  const [gridData, setGridData] = useState(null);
  const [benchmarkData, setBenchmarkData] = useState(null);

  // Simulation parameters
  const [initialOutage, setInitialOutage] = useState(1);
  const [loadScale, setLoadScale] = useState(1.10);
  const [capacityScale, setCapacityScale] = useState(0.02);
  const [seed, setSeed] = useState(42);

  // Simulation execution state
  const [isLoading, setIsLoading] = useState(false);
  const [simStage, setSimStage] = useState('');
  const [simResult, setSimResult] = useState(null);
  const [selectedElement, setSelectedElement] = useState(null);

  // Initial load
  useEffect(() => {
    async function init() {
      try {
        const healthRes = await fetch('/health');
        if (healthRes.ok) {
          setIsBackendHealthy(true);
        }
      } catch (err) {
        console.warn('Health check failed:', err);
      }

      try {
        const gridRes = await fetch('/grid');
        if (gridRes.ok) {
          const gData = await gridRes.json();
          setGridData(gData);
        }
      } catch (err) {
        console.warn('Grid topology fetch failed:', err);
      }

      try {
        const benchRes = await fetch('/benchmarks');
        if (benchRes.ok) {
          const bData = await benchRes.json();
          setBenchmarkData(bData);
        }
      } catch (err) {
        console.warn('Benchmarks fetch failed:', err);
      }
    }

    init();
  }, []);

  // Preset scenario selector handler
  const handleSelectPreset = (preset) => {
    setInitialOutage(preset.line);
    setLoadScale(preset.loadScale);
    setCapacityScale(preset.capScale);
  };

  // Run simulation handler
  const handleRunSimulation = async () => {
    setIsLoading(true);
    setSimStage('Triggering Outage...');

    try {
      setTimeout(() => setSimStage('GCN Downstream Risk Prediction...'), 250);
      setTimeout(() => setSimStage('PPO Preventive Mitigation...'), 600);
      setTimeout(() => setSimStage('Cascade Power Flow Propagation...'), 1000);
      setTimeout(() => setSimStage('Safety-Constrained Grid Recovery...'), 1400);

      const res = await fetch('/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          initial_outage: initialOutage,
          load_scale: loadScale,
          capacity_scale: capacityScale,
          seed: seed,
        }),
      });

      if (!res.ok) {
        throw new Error(`Simulation failed with HTTP ${res.status}`);
      }

      const data = await res.json();
      setSimResult(data);
    } catch (err) {
      console.error('Simulation error:', err);
      alert(`Simulation failed: ${err.message}`);
    } finally {
      setIsLoading(false);
      setSimStage('');
    }
  };

  return (
    <AppShell
      header={(
        <Navbar
          isBackendHealthy={isBackendHealthy}
          onSelectPreset={handleSelectPreset}
        />
      )}
    >
      <div id="operations" className="dashboard-container">
        <OperationalHero benchmarkData={benchmarkData} />

        <ControlBar
          initialOutage={initialOutage}
          setInitialOutage={setInitialOutage}
          loadScale={loadScale}
          setLoadScale={setLoadScale}
          capacityScale={capacityScale}
          setCapacityScale={setCapacityScale}
          seed={seed}
          setSeed={setSeed}
          onRunSimulation={handleRunSimulation}
          isLoading={isLoading}
          simStage={simStage}
        />

        <MetricsOverview simResult={simResult} />

        <div className="operations-workspace">
          <div className="operations-workspace__topology">
            <TopologyGraph
              gridData={gridData}
              simResult={simResult}
              selectedElement={selectedElement}
              setSelectedElement={setSelectedElement}
            />

          </div>

          <div className="operations-workspace__intelligence">
            <section id="prediction" className="anchor-section">
              <FailurePredictionPanel
                predictions={simResult?.line_predictions}
                initialOutages={simResult?.initial_grid_state?.initial_outages}
              />
            </section>

            <section id="mitigation" className="anchor-section">
              <MitigationPanel
                mitigationActions={simResult?.mitigation_actions}
                auditLog={simResult?.audit_log}
                totalLoadShedMw={simResult?.total_load_shed_mw}
              />
            </section>

            <section id="recovery" className="anchor-section">
              <RecoveryPanel
                reconnectedLines={simResult?.reconnected_lines}
                customerLoadRestoredMw={simResult?.customer_load_restored_mw}
                finalLoadServed={simResult?.final_load_served}
                finalLoadServedPct={simResult?.final_load_served_percent}
                postCascadeServedMw={simResult?.load_served_after_mitigation}
                recoveryActions={simResult?.recovery_actions}
                finalStatus={simResult?.final_system_status}
              />
            </section>
          </div>
        </div>

        <section className="timeline-section">
          <CascadeTimeline
            auditLog={simResult?.audit_log}
            finalStatus={simResult?.final_system_status}
          />
        </section>

        <section id="benchmarks" className="anchor-section">
          <ComparisonPanel benchmarkData={benchmarkData} />
        </section>
      </div>
    </AppShell>
  );
}
