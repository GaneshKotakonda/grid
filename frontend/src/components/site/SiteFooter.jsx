import React from 'react';
import { Link } from 'react-router-dom';
export default function SiteFooter() {
  return <footer className="site-footer"><div><strong>GridResilience</strong><p>Predictive intelligence. Physics-constrained action.</p></div><div className="site-footer__links"><Link to="/operations">Operations</Link><Link to="/timeline">Incident trace</Link><Link to="/benchmarks">Research evidence</Link></div><span>IEEE-14 Research Platform · 2026</span></footer>;
}

