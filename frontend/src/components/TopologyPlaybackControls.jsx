import React from 'react';
import { Pause, Play, RotateCcw, SkipBack, SkipForward } from 'lucide-react';
import StatusBadge from './ui/StatusBadge';

export default function TopologyPlaybackControls({ frames, index, playing, speed, onPlay, onReplay, onSeek, onSpeed }) {
  const frame = frames[index];
  const last = frames.length - 1;
  return (
    <section className="topology-playback" aria-label="Incident playback">
      <div className="topology-playback__status" aria-live="polite" aria-atomic="true">
        <StatusBadge tone={frame?.tone || 'neutral'}>{frame?.title || 'Awaiting simulation'}</StatusBadge>
        <p>{frame?.detail || 'Run a scenario in Operations to replay its incident trace.'}</p>
        {frame && <span className="mono">Step {index} / {last}</span>}
      </div>
      {frame?.servedLoadMw != null && <p className="topology-playback__load mono">{frame.servedLoadMw.toFixed(2)} MW served</p>}
      <div className="topology-playback__buttons">
        <button className="site-button site-button--primary" disabled={!frame} onClick={onPlay}>
          {playing ? <Pause size={16} /> : <Play size={16} />}{playing ? 'Pause' : 'Play'}
        </button>
        <button className="site-button site-button--outline" disabled={!frame} onClick={onReplay}><RotateCcw size={16} /> Replay</button>
        <button className="site-button site-button--outline" aria-label="Previous step" disabled={!frame || index === 0} onClick={() => onSeek(index - 1)}><SkipBack size={16} /></button>
        <button className="site-button site-button--outline" aria-label="Next step" disabled={!frame || index === last} onClick={() => onSeek(index + 1)}><SkipForward size={16} /></button>
        <button className="site-button site-button--outline" disabled={!frame} onClick={() => onSeek(last)}>Show output</button>
        <label className="topology-playback__speed">Speed
          <select value={speed} onChange={(event) => onSpeed(Number(event.target.value))} disabled={!frame}>
            <option value={0.5}>0.5×</option><option value={1}>1×</option><option value={2}>2×</option>
          </select>
        </label>
      </div>
      <input type="range" aria-label="Playback step" min="0" max={Math.max(last, 0)} value={frame ? index : 0} disabled={!frame} onChange={(event) => onSeek(Number(event.target.value))} />
      {frame && <small>Recorded event sequence · Bus loads update each step. GCN overlay uses the latest recorded forecast.</small>}
    </section>
  );
}
