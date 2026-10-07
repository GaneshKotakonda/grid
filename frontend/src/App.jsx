import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import AppShell from './components/ui/AppShell';
import HomePage from './pages/HomePage';
import OperationsPage from './pages/OperationsPage';
import TopologyPage from './pages/TopologyPage';
import PredictionPage from './pages/PredictionPage';
import MitigationPage from './pages/MitigationPage';
import RecoveryPage from './pages/RecoveryPage';
import TimelinePage from './pages/TimelinePage';
import BenchmarksPage from './pages/BenchmarksPage';

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
    <AppShell isBackendHealthy={isBackendHealthy}>
      <Routes>
        <Route path="/" element={<HomePage benchmarkData={benchmarkData} />} />
        <Route path="/operations" element={<OperationsPage
          onSelectPreset={handleSelectPreset} simResult={simResult}
          initialOutage={initialOutage} setInitialOutage={setInitialOutage}
          loadScale={loadScale} setLoadScale={setLoadScale}
          capacityScale={capacityScale} setCapacityScale={setCapacityScale}
          seed={seed} setSeed={setSeed} onRunSimulation={handleRunSimulation}
          isLoading={isLoading} simStage={simStage}
        />} />
        <Route path="/topology" element={<TopologyPage gridData={gridData} simResult={simResult} selectedElement={selectedElement} setSelectedElement={setSelectedElement} />} />
        <Route path="/prediction" element={<PredictionPage predictions={simResult?.line_predictions} initialOutages={simResult?.initial_grid_state?.initial_outages} />} />
        <Route path="/mitigation" element={<MitigationPage mitigationActions={simResult?.mitigation_actions} auditLog={simResult?.audit_log} totalLoadShedMw={simResult?.total_load_shed_mw} />} />
        <Route path="/recovery" element={<RecoveryPage reconnectedLines={simResult?.reconnected_lines} customerLoadRestoredMw={simResult?.customer_load_restored_mw} finalLoadServed={simResult?.final_load_served} finalLoadServedPct={simResult?.final_load_served_percent} postCascadeServedMw={simResult?.load_served_after_mitigation} recoveryActions={simResult?.recovery_actions} finalStatus={simResult?.final_system_status} />} />
        <Route path="/timeline" element={<TimelinePage auditLog={simResult?.audit_log} finalStatus={simResult?.final_system_status} />} />
        <Route path="/benchmarks" element={<BenchmarksPage benchmarkData={benchmarkData} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
