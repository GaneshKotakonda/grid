import React, { useEffect, useMemo, useState } from 'react';
import { Layers } from 'lucide-react';
import PanelHeader from './ui/PanelHeader';
import StatusBadge from './ui/StatusBadge';
import TopologyPlaybackControls from './TopologyPlaybackControls';
import { buildTopologyPlayback } from './topologyPlayback';

export default function TopologyGraph({
  gridData,
  simResult,
  selectedElement,
  setSelectedElement,
}) {
  const [showLabels, setShowLabels] = useState(true);
  const [showGcnOverlay, setShowGcnOverlay] = useState(true);
  const frames = useMemo(() => buildTopologyPlayback(simResult), [simResult]);
  const [frameIndex, setFrameIndex] = useState(() => Math.max(frames.length - 1, 0));
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const frame = frames[frameIndex];
  const isOutput = !frame || frame.isOutput;

  useEffect(() => {
    if (!playing) return;
    const timer = setTimeout(() => {
      const next = Math.min(frameIndex + 1, frames.length - 1);
      setFrameIndex(next);
      if (next === frames.length - 1) setPlaying(false);
    }, 1500 / speed);
    return () => clearTimeout(timer);
  }, [playing, frameIndex, frames.length, speed]);

  const seek = (index) => { setPlaying(false); setFrameIndex(index); };
  const replay = () => { setFrameIndex(0); setPlaying(true); };
  const togglePlayback = () => {
    if (playing) setPlaying(false);
    else {
      if (frameIndex === frames.length - 1) setFrameIndex(0);
      setPlaying(true);
    }
  };

  if (!gridData || !gridData.buses) {
    return (
      <div className="card topology-loading">
        <span className="spinner" />
        <p>Loading IEEE-14 topology...</p>
      </div>
    );
  }

  const buses = gridData.buses;
  const lines = gridData.lines;
  const trafos = gridData.transformers || [];

  // Determine line state from simulation result
  const failedLines = frame?.failedLines || [];
  const reconnectedLines = frame?.reconnectedLines || [];
  const gcnProbs = simResult?.gcn_failure_probabilities || [];

  const getLineStatus = (lineId) => {
    const isReconnected = reconnectedLines.includes(lineId);
    const isFailed = failedLines.includes(lineId);

    if (isReconnected) {
      return { color: 'var(--color-info)', status: 'RECONNECTED', class: 'line-reconnected', width: 4 };
    }
    if (isFailed) {
      return { color: 'var(--text-muted)', status: 'FAILED', class: 'line-tripped', width: 2.5 };
    }

    const prob = gcnProbs[lineId] !== undefined ? gcnProbs[lineId] : 0.0;
    if (isOutput && showGcnOverlay && prob >= 0.50) {
      return { color: 'var(--color-danger)', status: 'PREDICTED_FAILURE', class: 'line-danger', width: 4.5, prob };
    }
    if (isOutput && showGcnOverlay && prob >= 0.20) {
      return { color: 'var(--color-warning)', status: 'HIGH_RISK', class: 'line-warning', width: 3.5, prob };
    }
    return { color: 'var(--color-safe)', status: isOutput ? 'SAFE' : 'IN_SERVICE', class: 'line-safe', width: 2.5, ...(isOutput ? { prob } : {}) };
  };

  const busMap = {};
  buses.forEach((b) => { busMap[b.id] = b; });

  return (
    <div className="card topology-panel">
      <PanelHeader
        icon={Layers}
        title="Interactive IEEE 14-Bus Transmission Topology"
        subtitle="Simulation output and playback of recorded outages, trip waves, and recovery."
        badge={<StatusBadge tone="info">{playing ? 'Playing trace' : isOutput && simResult ? 'Simulation output' : frame ? 'Incident replay' : 'Base topology'}</StatusBadge>}
        as="h2"
        actions={(
          <>
          <label className="layer-toggle">
            <input
              type="checkbox"
              checked={showGcnOverlay}
              disabled={!isOutput}
              onChange={(e) => setShowGcnOverlay(e.target.checked)}
            />
            GCN Overlay
          </label>
          <label className="layer-toggle">
            <input
              type="checkbox"
              checked={showLabels}
              onChange={(e) => setShowLabels(e.target.checked)}
            />
            Line Labels
          </label>
          </>
        )}
      />

      <div className="topology-canvas">
        <svg
          viewBox="0 0 760 520"
          className="topology-canvas__svg"
        >
          <defs>
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            <linearGradient id="gridBg" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="var(--topology-start)" />
              <stop offset="100%" stopColor="var(--topology-end)" />
            </linearGradient>
          </defs>

          {/* Grid pattern background lines */}
          <rect width="760" height="520" fill="url(#gridBg)" />
          {Array.from({ length: 15 }).map((_, i) => (
            <line key={`gx-${i}`} x1={i * 50} y1="0" x2={i * 50} y2="520" stroke="var(--topology-grid)" strokeWidth="0.45" opacity="0.55" />
          ))}
          {Array.from({ length: 11 }).map((_, i) => (
            <line key={`gy-${i}`} x1="0" y1={i * 50} x2="760" y2={i * 50} stroke="var(--topology-grid)" strokeWidth="0.45" opacity="0.55" />
          ))}

          {/* Render Transformers */}
          {trafos.map((t) => {
            const b1 = busMap[t.hv_bus];
            const b2 = busMap[t.lv_bus];
            if (!b1 || !b2) return null;
            return (
              <g key={`trafo-${t.id}`}>
                <line
                  x1={b1.x}
                  y1={b1.y}
                  x2={b2.x}
                  y2={b2.y}
                  stroke="var(--text-muted)"
                  strokeWidth="2"
                  strokeDasharray="4,4"
                  opacity="0.8"
                />
              </g>
            );
          })}

          {/* Render Transmission Lines */}
          {lines.map((l) => {
            const b1 = busMap[l.from_bus];
            const b2 = busMap[l.to_bus];
            if (!b1 || !b2) return null;

            const st = getLineStatus(l.id);
            const midX = (b1.x + b2.x) / 2;
            const midY = (b1.y + b2.y) / 2;
            const isSelected = selectedElement?.type === 'line' && selectedElement?.id === l.id;
            const justTripped = frame?.activeTrips.includes(l.id);
            const justReconnected = frame?.activeReconnections.includes(l.id);

            return (
              <g
                key={`line-${l.id}`}
                role="button"
                tabIndex="0"
                aria-label={`Line ${l.id}: ${st.status}`}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    setSelectedElement({ type: 'line', id: l.id, data: l, status: st });
                  }
                }}
                onClick={() => setSelectedElement({ type: 'line', id: l.id, data: l, status: st })}
                style={{ cursor: 'pointer' }}
              >
                {/* Wider invisible stroke for easy clicking */}
                <line
                  x1={b1.x}
                  y1={b1.y}
                  x2={b2.x}
                  y2={b2.y}
                  stroke="transparent"
                  strokeWidth="16"
                />
                {/* Visual line */}
                <path
                  d={st.status === 'FAILED'
                    ? `M${b1.x},${b1.y} L${b1.x + (b2.x - b1.x) * 0.46},${b1.y + (b2.y - b1.y) * 0.46} M${b1.x + (b2.x - b1.x) * 0.54},${b1.y + (b2.y - b1.y) * 0.54} L${b2.x},${b2.y}`
                    : `M${b1.x},${b1.y} L${b2.x},${b2.y}`}
                  fill="none"
                  className={`${st.class} topology-line${justTripped ? ' topology-line--trip' : ''}`}
                  stroke={st.color}
                  strokeWidth={isSelected ? st.width + 3 : st.width}
                  filter={st.status === 'PREDICTED_FAILURE' ? 'url(#glow)' : undefined}
                />
                {/* A break marker denotes a recorded disconnection, not physical damage. */}
                {st.status === 'FAILED' && (
                  <g className={justTripped ? 'topology-fault-marker' : ''} transform={`translate(${midX}, ${midY - (showLabels ? 20 : 0)})`} aria-hidden="true">
                    <circle r="8" fill="var(--bg-panel)" stroke="var(--color-danger)" />
                    <path d="M-3,-3 L3,3 M3,-3 L-3,3" stroke="var(--color-danger)" strokeWidth="2" />
                  </g>
                )}
                {justReconnected && <circle className="topology-reclosure-marker" cx={midX} cy={midY} r="16" fill="none" stroke="var(--color-info)" strokeWidth="2" aria-hidden="true" />}
                {/* Line badge / label */}
                {showLabels && (
                  <g transform={`translate(${midX}, ${midY})`}>
                    <rect
                      x="-18"
                      y="-10"
                      width="36"
                      height="20"
                      rx="4"
                      fill="var(--bg-panel)"
                      stroke={st.color}
                      strokeWidth="1"
                      opacity="0.95"
                    />
                    <text
                      x="0"
                      y="4"
                      textAnchor="middle"
                      fill="var(--text-primary)"
                      fontSize="9"
                      fontWeight="700"
                      fontFamily="JetBrains Mono"
                    >
                      L{l.id}
                    </text>
                  </g>
                )}
              </g>
            );
          })}

          {/* Render Buses */}
          {buses.map((b) => {
            const isSelected = selectedElement?.type === 'bus' && selectedElement?.id === b.id;
            const isSlack = b.type === 'slack';
            const isGen = b.type === 'generator';
            const nodeFill = isSlack ? 'var(--color-info)' : isGen ? 'var(--color-purple)' : 'var(--color-info)';

            return (
              <g
                key={`bus-${b.id}`}
                transform={`translate(${b.x}, ${b.y})`}
                onClick={() => setSelectedElement({ type: 'bus', id: b.id, data: b })}
                style={{ cursor: 'pointer' }}
              >
                {/* Outer halo */}
                <circle
                  r={isSelected ? 18 : 14}
                  fill="none"
                  stroke={nodeFill}
                  strokeWidth={isSelected ? 3 : 1.5}
                  strokeDasharray={isSlack ? '3,3' : undefined}
                  opacity="0.8"
                />
                {/* Node body */}
                <circle
                  r="10"
                  fill="var(--bg-panel)"
                  stroke={nodeFill}
                  strokeWidth="2.5"
                />
                {/* Bus Number Label */}
                <text
                  textAnchor="middle"
                  dy="3.5"
                  fill="var(--text-primary)"
                  fontSize="9.5"
                  fontWeight="800"
                  fontFamily="JetBrains Mono"
                >
                  {b.id + 1}
                </text>
                {/* Node tag below */}
                <text
                  textAnchor="middle"
                  y="24"
                  fill="var(--text-muted)"
                  fontSize="9"
                  fontWeight="600"
                >
                  {b.name}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Selected element mini drawer overlay */}
        {selectedElement && (
          <div className="topology-drawer">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-info)' }}>
                {selectedElement.type === 'line' ? `Line ${selectedElement.id}` : `Bus ${selectedElement.id + 1}`}
              </span>
              <button
                onClick={() => setSelectedElement(null)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '14px' }}
              >
                ✕
              </button>
            </div>
            {selectedElement.type === 'line' && (
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div>Connection: Bus {selectedElement.data.from_bus + 1} ↔ Bus {selectedElement.data.to_bus + 1}</div>
                <div>Status: <span style={{ color: getLineStatus(selectedElement.id).color, fontWeight: 700 }}>{getLineStatus(selectedElement.id).status}</span></div>
                {getLineStatus(selectedElement.id).prob !== undefined && (
                  <div>GCN Failure Prob: <span className="mono" style={{ fontWeight: 700 }}>{(getLineStatus(selectedElement.id).prob * 100).toFixed(1)}%</span></div>
                )}
                <div>Thermal Rating: {selectedElement.data.max_i_ka?.toFixed(1)} kA</div>
              </div>
            )}
            {selectedElement.type === 'bus' && (
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div>Name: {selectedElement.data.name} ({selectedElement.data.type})</div>
                <div>Base Voltage: {selectedElement.data.vn_kv} kV</div>
                <div>Load Active: {selectedElement.data.load_mw} MW</div>
                <div>Generation: {selectedElement.data.gen_mw} MW</div>
              </div>
            )}
          </div>
        )}
      </div>

      <TopologyPlaybackControls frames={frames} index={frameIndex} playing={playing} speed={speed} onPlay={togglePlayback} onReplay={replay} onSeek={seek} onSpeed={setSpeed} />

      <div className="topology-legend">
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '14px', height: '3px', background: 'var(--color-safe)', borderRadius: '2px' }} />
          <span>In service / Low predicted risk</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '14px', height: '4px', background: 'var(--color-warning)', borderRadius: '2px' }} />
          <span>High Risk (20-50%)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '14px', height: '4px', background: 'var(--color-danger)', borderRadius: '2px' }} />
          <span>Predicted Failure (&ge;50%)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '14px', height: '3px', background: 'var(--text-muted)', borderStyle: 'dashed' }} />
          <span>Tripped / Outage</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '14px', height: '4px', background: 'var(--color-info)', borderRadius: '2px' }} />
          <span>Reconnected (Recovery)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '14px', height: '2px', background: 'var(--text-muted)', borderStyle: 'dotted' }} />
          <span>Transformer</span>
        </div>
      </div>
    </div>
  );
}
