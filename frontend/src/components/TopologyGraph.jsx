import React, { useState } from 'react';
import { Layers, Info, ShieldAlert, CheckCircle, Zap } from 'lucide-react';

export default function TopologyGraph({
  gridData,
  simResult,
  selectedElement,
  setSelectedElement,
}) {
  const [showLabels, setShowLabels] = useState(true);
  const [showGcnOverlay, setShowGcnOverlay] = useState(true);

  if (!gridData || !gridData.buses) {
    return (
      <div className="card" style={{ height: '520px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p style={{ color: 'var(--text-muted)' }}>Loading IEEE-14 Topology...</p>
      </div>
    );
  }

  const buses = gridData.buses;
  const lines = gridData.lines;
  const trafos = gridData.transformers || [];

  // Determine line state from simulation result
  const failedLines = simResult?.failed_lines || [];
  const reconnectedLines = simResult?.reconnected_lines || [];
  const initialOutages = simResult?.initial_grid_state?.initial_outages || [];
  const gcnProbs = simResult?.gcn_failure_probabilities || [];

  const getLineStatus = (lineId) => {
    const isReconnected = reconnectedLines.includes(lineId);
    const isFailed = failedLines.includes(lineId) || initialOutages.includes(lineId);

    if (isReconnected) {
      return { color: '#06b6d4', status: 'RECONNECTED', class: 'line-reconnected', width: 4 };
    }
    if (isFailed) {
      return { color: '#64748b', status: 'FAILED', class: 'line-tripped', width: 2.5 };
    }

    const prob = gcnProbs[lineId] !== undefined ? gcnProbs[lineId] : 0.0;
    if (showGcnOverlay && prob >= 0.50) {
      return { color: '#ef4444', status: 'PREDICTED_FAILURE', class: 'line-danger', width: 4.5, prob };
    }
    if (showGcnOverlay && prob >= 0.20) {
      return { color: '#f59e0b', status: 'HIGH_RISK', class: 'line-warning', width: 3.5, prob };
    }
    return { color: '#10b981', status: 'SAFE', class: 'line-safe', width: 2.5, prob };
  };

  const busMap = {};
  buses.forEach((b) => { busMap[b.id] = b; });

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '14px', position: 'relative' }}>
      {/* Header with layer toggles */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <h2 style={{ fontSize: '17px', fontWeight: 700, margin: 0, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Layers size={18} color="#06b6d4" />
            Interactive IEEE 14-Bus Transmission Topology
          </h2>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '2px 0 0' }}>
            Real-time physical grid status, GCN failure risk propagation, and reclosure tracking
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#cbd5e1', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={showGcnOverlay}
              onChange={(e) => setShowGcnOverlay(e.target.checked)}
              style={{ accentColor: '#06b6d4' }}
            />
            GCN Failure Risk Overlay
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#cbd5e1', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={showLabels}
              onChange={(e) => setShowLabels(e.target.checked)}
              style={{ accentColor: '#06b6d4' }}
            />
            Line Labels
          </label>
        </div>
      </div>

      {/* SVG Canvas */}
      <div style={{
        background: '#090d16',
        borderRadius: 'var(--radius-md)',
        border: '1px solid #1e293b',
        position: 'relative',
        overflow: 'hidden',
      }}>
        <svg
          viewBox="0 0 760 520"
          style={{ width: '100%', height: 'auto', maxHeight: '520px', display: 'block' }}
        >
          <defs>
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            <linearGradient id="gridBg" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#0b101c" />
              <stop offset="100%" stopColor="#080c15" />
            </linearGradient>
          </defs>

          {/* Grid pattern background lines */}
          <rect width="760" height="520" fill="url(#gridBg)" />
          {Array.from({ length: 15 }).map((_, i) => (
            <line key={`gx-${i}`} x1={i * 50} y1="0" x2={i * 50} y2="520" stroke="#111827" strokeWidth="0.5" />
          ))}
          {Array.from({ length: 11 }).map((_, i) => (
            <line key={`gy-${i}`} x1="0" y1={i * 50} x2="760" y2={i * 50} stroke="#111827" strokeWidth="0.5" />
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
                  stroke="#475569"
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

            return (
              <g
                key={`line-${l.id}`}
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
                <line
                  x1={b1.x}
                  y1={b1.y}
                  x2={b2.x}
                  y2={b2.y}
                  className={st.class}
                  stroke={st.color}
                  strokeWidth={isSelected ? st.width + 3 : st.width}
                  filter={st.status === 'PREDICTED_FAILURE' ? 'url(#glow)' : undefined}
                />
                {/* Line badge / label */}
                {showLabels && (
                  <g transform={`translate(${midX}, ${midY})`}>
                    <rect
                      x="-18"
                      y="-10"
                      width="36"
                      height="20"
                      rx="4"
                      fill="#0e1424"
                      stroke={st.color}
                      strokeWidth="1"
                      opacity="0.95"
                    />
                    <text
                      x="0"
                      y="4"
                      textAnchor="middle"
                      fill="#f8fafc"
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
            const nodeFill = isSlack ? '#06b6d4' : isGen ? '#a855f7' : '#3b82f6';

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
                  fill="#0b0f19"
                  stroke={nodeFill}
                  strokeWidth="2.5"
                />
                {/* Bus Number Label */}
                <text
                  textAnchor="middle"
                  dy="3.5"
                  fill="#ffffff"
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
                  fill="#94a3b8"
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
          <div style={{
            position: 'absolute',
            bottom: '16px',
            right: '16px',
            background: 'rgba(14, 20, 36, 0.95)',
            border: '1px solid #334155',
            borderRadius: 'var(--radius-md)',
            padding: '12px 16px',
            boxShadow: '0 10px 25px rgba(0,0,0,0.6)',
            maxWidth: '300px',
            backdropFilter: 'blur(8px)',
            zIndex: 10,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '12px', fontWeight: 700, color: '#38bdf8' }}>
                {selectedElement.type === 'line' ? `Line ${selectedElement.id}` : `Bus ${selectedElement.id + 1}`}
              </span>
              <button
                onClick={() => setSelectedElement(null)}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '14px' }}
              >
                ✕
              </button>
            </div>
            {selectedElement.type === 'line' && (
              <div style={{ fontSize: '11px', color: '#cbd5e1', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div>Connection: Bus {selectedElement.data.from_bus + 1} ↔ Bus {selectedElement.data.to_bus + 1}</div>
                <div>Status: <span style={{ color: selectedElement.status?.color, fontWeight: 700 }}>{selectedElement.status?.status}</span></div>
                {selectedElement.status?.prob !== undefined && (
                  <div>GCN Failure Prob: <span className="mono" style={{ fontWeight: 700 }}>{(selectedElement.status.prob * 100).toFixed(1)}%</span></div>
                )}
                <div>Thermal Rating: {selectedElement.data.max_i_ka?.toFixed(1)} kA</div>
              </div>
            )}
            {selectedElement.type === 'bus' && (
              <div style={{ fontSize: '11px', color: '#cbd5e1', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div>Name: {selectedElement.data.name} ({selectedElement.data.type})</div>
                <div>Base Voltage: {selectedElement.data.vn_kv} kV</div>
                <div>Load Active: {selectedElement.data.load_mw} MW</div>
                <div>Generation: {selectedElement.data.gen_mw} MW</div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Legend row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '20px', flexWrap: 'wrap', fontSize: '11px', color: '#94a3b8' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '14px', height: '3px', background: '#10b981', borderRadius: '2px' }} />
          <span>Safe (&lt;20% Risk)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '14px', height: '4px', background: '#f59e0b', borderRadius: '2px' }} />
          <span>High Risk (20-50%)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '14px', height: '4px', background: '#ef4444', borderRadius: '2px' }} />
          <span>Predicted Failure (&ge;50%)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '14px', height: '3px', background: '#64748b', borderStyle: 'dashed' }} />
          <span>Tripped / Outage</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '14px', height: '4px', background: '#06b6d4', borderRadius: '2px' }} />
          <span>Reconnected (Recovery)</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '14px', height: '2px', background: '#475569', borderStyle: 'dotted' }} />
          <span>Transformer</span>
        </div>
      </div>
    </div>
  );
}
