import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, Network, ShieldCheck } from 'lucide-react';
export default function LandingHero() {
  return <section className="landing-hero" aria-labelledby="home-heading">
    <div className="landing-hero__copy"><span className="eyebrow"><i className="live-dot" /> Intelligence for resilient energy</span><h1 id="home-heading">Predict instability.<br /><em>Protect the grid.</em></h1><p>A research-grade platform that forecasts cascading failures, applies preventive control, and restores service under AC safety constraints.</p><div className="hero-actions"><Link className="site-button site-button--primary" to="/operations">Run a scenario <ArrowUpRight size={17} /></Link><Link className="site-button site-button--outline" to="/benchmarks">Explore the evidence</Link></div><div className="hero-footnote"><Network size={15} /> IEEE-14 test system <span /> Predictive GCN + PPO</div></div>
    <div className="landing-hero__visual"><img src="/gridresilience-hero.png" alt="Transmission towers and substation under a warm evening sky" fetchPriority="high" /><span className="visual-caption">THE FUTURE OF GRID RESILIENCE</span><div className="hero-visual-card"><span><ShieldCheck size={18} /> Physics as the guardrail</span><strong>Forecast. Act. Restore.</strong><p>One coordinated incident workflow.</p></div></div>
  </section>;
}

