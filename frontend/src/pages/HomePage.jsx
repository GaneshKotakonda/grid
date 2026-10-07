import React from 'react';
import { Link } from 'react-router-dom';
import { BrainCircuit, ShieldCheck, RefreshCw, ArrowUpRight } from 'lucide-react';
import LandingHero from '../components/site/LandingHero';
const capabilities = [
  { step: '01 / FORECAST', title: 'See downstream failures early.', text: 'Topology-aware GCN forecasting ranks the risk across every transmission line before the cascade develops.', path: '/prediction', link: 'Explore prediction', icon: BrainCircuit },
  { step: '02 / MITIGATE', title: 'Act before instability spreads.', text: 'Predictive PPO coordinates targeted load shedding and generator redispatch to reduce downstream propagation.', path: '/mitigation', link: 'Explore mitigation', icon: ShieldCheck },
  { step: '03 / RECOVER', title: 'Restore with safety built in.', text: 'Sequential reclosure and customer load restoration remain bounded by AC feasibility and survivor integrity.', path: '/recovery', link: 'Explore recovery', icon: RefreshCw },
];
const workflow = [['/operations','Operations','Configure and run'],['/topology','Topology','Inspect network state'],['/prediction','Prediction','Review line risks'],['/mitigation','Mitigation','Trace PPO actions'],['/recovery','Recovery','Restore service'],['/timeline','Timeline','Follow every decision']];
export default function HomePage({ benchmarkData }) {
  const findings = benchmarkData?.key_findings;
  return <div className="home-page"><LandingHero />
    <section className="landing-impact" aria-label="Validated benchmark findings"><div><span className="eyebrow">Measured, not assumed</span><h2>Validated operational impact</h2><p>300 held-out scenarios · Phase 5.5 evaluation</p></div><div><strong>{findings?.load_served_gain_pp != null ? `+${findings.load_served_gain_pp} pp` : '—'}</strong><span>customer load served</span></div><div><strong>{findings?.load_shedding_reduction_percent != null ? `${findings.load_shedding_reduction_percent}%` : '—'}</strong><span>less load shedding</span></div><div><strong>{findings?.blackout_rate_reduction_pp != null ? `−${findings.blackout_rate_reduction_pp} pp` : '—'}</strong><span>total blackout rate</span></div></section>
    <section className="landing-section"><div className="landing-section__heading"><div><span className="eyebrow">Built around the incident</span><h2>One platform.<br />A complete resilience lifecycle.</h2></div><p>Move from a controlled scenario to an explainable response. Every capability has its own focused workspace, backed by the same scientific workflow.</p></div><div className="capability-grid">{capabilities.map(({ step, title, text, path, link, icon: Icon }) => <article className="capability-card" key={path}><span className="capability-step">{step}</span><Icon size={30} strokeWidth={1.5} /><h3>{title}</h3><p>{text}</p><Link to={path}>{link}<ArrowUpRight size={16} /></Link></article>)}</div></section>
    <section className="landing-section"><div className="landing-section__heading"><div><span className="eyebrow">Clarity through every phase</span><h2>Follow the whole story.</h2></div><Link className="text-link" to="/benchmarks">Review research evidence <ArrowUpRight size={17} /></Link></div><div className="workflow-grid">{workflow.map(([path,label,detail],i) => <Link key={path} to={path}><span className="workflow-number">0{i+1}</span><strong>{label}</strong><p>{detail}</p><ArrowUpRight size={17} /></Link>)}</div></section>
    <section className="landing-cta"><div><span className="eyebrow">From insight to action</span><h2>Explore how the grid responds.</h2><p>Choose an outage. Apply operating stress. Inspect every phase.</p></div><Link className="site-button site-button--primary" to="/operations">Launch Operations <ArrowUpRight size={18} /></Link></section>
  </div>;
}

