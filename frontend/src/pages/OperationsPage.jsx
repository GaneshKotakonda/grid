import React from 'react';
import { Link } from 'react-router-dom';
import PageIntro from '../components/site/PageIntro';
import ControlBar from '../components/ControlBar';
import MetricsOverview from '../components/MetricsOverview';
export default function OperationsPage({ onSelectPreset, simResult, ...controlProps }) {
  return <div className="feature-page"><PageIntro path="/operations" /><div className="operations-presets"><span>Start with a preset</span>{[{ label: 'Moderate', line: 1, loadScale: 1.10, capScale: 0.02 }, { label: 'Stressed', line: 2, loadScale: 1.25, capScale: 0.015 }, { label: 'Severe', line: 0, loadScale: 1.35, capScale: 0.012 }].map(({ label, ...preset }) => <button key={label} disabled={controlProps.isLoading} onClick={() => onSelectPreset(preset)}>{label}</button>)}</div><ControlBar {...controlProps} /><MetricsOverview simResult={simResult} /><div className="result-navigation"><div><span className="eyebrow">{simResult ? 'Incident complete' : 'Explore the workflow'}</span><h2>{simResult ? 'Your results are ready to inspect.' : 'One simulation. Every phase in focus.'}</h2><p>{simResult ? 'The same result is available across the feature pages below.' : 'Run a scenario, then follow its results through the platform.'}</p></div><div>{[['/topology','Inspect topology'],['/prediction','View forecasts'],['/timeline','Follow the trace']].map(([path,label]) => <Link key={path} to={path}>{label} →</Link>)}</div></div></div>;
}

