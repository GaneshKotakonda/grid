import React from 'react';
import { Play, RotateCcw, Sliders, AlertTriangle } from 'lucide-react';

const LINE_NAMES = [
  "Line 0 (Bus 1 - Bus 2)",
  "Line 1 (Bus 1 - Bus 5)",
  "Line 2 (Bus 2 - Bus 3)",
  "Line 3 (Bus 2 - Bus 4)",
  "Line 4 (Bus 2 - Bus 5)",
  "Line 5 (Bus 3 - Bus 4)",
  "Line 6 (Bus 4 - Bus 5)",
  "Line 7 (Bus 6 - Bus 11)",
  "Line 8 (Bus 6 - Bus 12)",
  "Line 9 (Bus 6 - Bus 13)",
  "Line 10 (Bus 9 - Bus 10)",
  "Line 11 (Bus 9 - Bus 14)",
  "Line 12 (Bus 10 - Bus 11)",
  "Line 13 (Bus 12 - Bus 13)",
  "Line 14 (Bus 13 - Bus 14)",
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
    <div className="card" style={{
      marginBottom: '24px',
      background: 'linear-gradient(180deg, #161e33 0%, var(--bg-card) 100%)',
      border: '1px solid #2a3754',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '20px',
      }}>
        {/* Controls row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px', flexWrap: 'wrap' }}>
          {/* Outage selector */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '12px', fontWeight: 700, color: '#cbd5e1', display: 'flex', alignItems: 'center', gap: '5px' }}>
              <AlertTriangle size={14} color="#f59e0b" />
              INITIATING OUTAGE
            </label>
            <select
              value={initialOutage}
              onChange={(e) => setInitialOutage(Number(e.target.value))}
              disabled={isLoading}
              style={{
                background: '#0e1424',
                border: '1px solid #334155',
                color: '#f8fafc',
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '13px',
                fontWeight: 600,
                outline: 'none',
                cursor: 'pointer',
                minWidth: '220px',
              }}
            >
              {LINE_NAMES.map((name, idx) => (
                <option key={idx} value={idx}>
                  {name}
                </option>
              ))}
            </select>
          </div>

          {/* Load Scale Slider */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', minWidth: '180px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label style={{ fontSize: '12px', fontWeight: 700, color: '#cbd5e1' }}>
                LOAD STRESS
              </label>
              <span className="mono" style={{ fontSize: '12px', fontWeight: 700, color: '#38bdf8' }}>
                {(loadScale * 100).toFixed(0)}% ({loadScale.toFixed(2)}x)
              </span>
            </div>
            <input
              type="range"
              min="0.80"
              max="1.50"
              step="0.05"
              value={loadScale}
              onChange={(e) => setLoadScale(Number(e.target.value))}
              disabled={isLoading}
              style={{
                width: '100%',
                accentColor: '#38bdf8',
                cursor: 'pointer',
              }}
            />
          </div>

          {/* Capacity Scale */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '12px', fontWeight: 700, color: '#cbd5e1' }}>
              LINE CAPACITY
            </label>
            <select
              value={capacityScale}
              onChange={(e) => setCapacityScale(Number(e.target.value))}
              disabled={isLoading}
              style={{
                background: '#0e1424',
                border: '1px solid #334155',
                color: '#f8fafc',
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '13px',
                fontWeight: 600,
                outline: 'none',
                cursor: 'pointer',
              }}
            >
              <option value={0.012}>0.012 (Heavily Stressed)</option>
              <option value={0.015}>0.015 (Stressed)</option>
              <option value={0.020}>0.020 (Nominal Design)</option>
              <option value={0.025}>0.025 (Relaxed)</option>
            </select>
          </div>

          {/* Random Seed */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '12px', fontWeight: 700, color: '#cbd5e1' }}>
              SEED
            </label>
            <input
              type="number"
              value={seed}
              onChange={(e) => setSeed(Number(e.target.value))}
              disabled={isLoading}
              style={{
                background: '#0e1424',
                border: '1px solid #334155',
                color: '#f8fafc',
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '13px',
                width: '70px',
                textAlign: 'center',
                fontWeight: 600,
                outline: 'none',
              }}
            />
          </div>
        </div>

        {/* Action Button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={onRunSimulation}
            disabled={isLoading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              background: isLoading
                ? '#334155'
                : 'linear-gradient(135deg, #06b6d4 0%, #2563eb 100%)',
              color: '#ffffff',
              border: 'none',
              padding: '12px 24px',
              borderRadius: 'var(--radius-md)',
              fontSize: '14px',
              fontWeight: 700,
              cursor: isLoading ? 'not-allowed' : 'pointer',
              boxShadow: isLoading ? 'none' : '0 0 25px rgba(6, 182, 212, 0.45)',
              transition: 'all 0.2s ease',
            }}
          >
            {isLoading ? (
              <>
                <div style={{
                  width: '16px',
                  height: '16px',
                  border: '2px solid rgba(255,255,255,0.3)',
                  borderTopColor: '#ffffff',
                  borderRadius: '50%',
                  animation: 'spin 0.8s linear infinite',
                }} />
                <span>{simStage || 'Executing Pipeline...'}</span>
              </>
            ) : (
              <>
                <Play size={18} fill="#ffffff" />
                <span>Run GridResilience</span>
              </>
            )}
          </button>
        </div>
      </div>
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
