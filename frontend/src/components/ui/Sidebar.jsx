import React, { useEffect, useState } from 'react';
import {
  Activity,
  BarChart3,
  BrainCircuit,
  RefreshCw,
  ShieldCheck,
  Zap,
} from 'lucide-react';

const NAV_ITEMS = [
  { id: 'operations', label: 'Grid Operations', icon: Activity },
  { id: 'prediction', label: 'Prediction', icon: BrainCircuit },
  { id: 'mitigation', label: 'Mitigation', icon: ShieldCheck },
  { id: 'recovery', label: 'Recovery', icon: RefreshCw },
  { id: 'benchmarks', label: 'Experiments & Benchmarks', icon: BarChart3 },
];

export default function Sidebar() {
  const [activeSection, setActiveSection] = useState('operations');

  useEffect(() => {
    const sections = NAV_ITEMS
      .map(({ id }) => document.getElementById(id))
      .filter(Boolean);

    if (!sections.length || typeof IntersectionObserver === 'undefined') return undefined;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible?.target?.id) setActiveSection(visible.target.id);
      },
      { rootMargin: '-18% 0px -62% 0px', threshold: [0.05, 0.25, 0.5] },
    );

    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, []);

  return (
    <aside className="sidebar" aria-label="Dashboard sections">
      <a className="sidebar__brand" href="#operations" aria-label="GridResilience home">
        <Zap size={25} strokeWidth={2.4} />
      </a>

      <nav className="sidebar__nav">
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
          <a
            key={id}
            href={`#${id}`}
            className={`sidebar__link ${activeSection === id ? 'is-active' : ''}`}
            aria-label={label}
            title={label}
            onClick={() => setActiveSection(id)}
          >
            <Icon size={19} />
            <span>{label}</span>
          </a>
        ))}
      </nav>

      <div className="sidebar__status" title="Safety-constrained operations">
        <span className="sidebar__status-dot" />
        <span>AC</span>
      </div>
    </aside>
  );
}
