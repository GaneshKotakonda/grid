import React from 'react';
import Sidebar from './Sidebar';

export default function AppShell({ header, children }) {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-shell__body">
        {header}
        <main className="app-shell__content">{children}</main>
        <footer className="app-footer">
          <span>GridResilience</span>
          <span>Predictive GCN · PPO Mitigation · Safety-Constrained Recovery</span>
          <span>IEEE-14 Research Operations</span>
        </footer>
      </div>
    </div>
  );
}
