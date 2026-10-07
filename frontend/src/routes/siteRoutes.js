export const SITE_ROUTES = [
  { path: '/', label: 'Home', group: 'primary', title: 'GridResilience', description: 'Predict, mitigate, recover.' },
  { path: '/operations', label: 'Operations', group: 'primary', phase: 'Incident control', title: 'Your scenario. One coordinated response.', description: 'Configure the initiating outage and grid stress, then run the complete predictive incident workflow.' },
  { path: '/topology', label: 'Topology', group: 'primary', phase: 'Network intelligence', title: 'Inspect the grid, connection by connection.', description: 'Explore the IEEE-14 network and inspect the latest line status, predicted risks, and restored connections.' },
  { path: '/prediction', label: 'Prediction', group: 'primary', phase: 'Phase 4.5 · Predictive GCN', title: 'Understand where the cascade could spread.', description: 'Review downstream failure probability across all 15 transmission lines in the latest scenario.' },
  { path: '/mitigation', label: 'Mitigation', group: 'primary', phase: 'Phase 5 · PPO control', title: 'Trace every preventive decision.', description: 'Inspect the predictive policy’s action sequence, load shedding, and reward feedback.' },
  { path: '/recovery', label: 'Recovery', group: 'primary', phase: 'Phase 6 · Safety constraints', title: 'Restore service with physics as the guardrail.', description: 'Review committed restoration actions, reclosed lines, and the final served-load state.' },
  { path: '/timeline', label: 'Timeline', group: 'research', phase: 'Incident trace', title: 'Follow the incident from trigger to recovery.', description: 'A complete progression through contingency, forecasting, mitigation, cascade propagation, and restoration.' },
  { path: '/benchmarks', label: 'Benchmarks', group: 'research', phase: 'Validated research', title: 'Evidence behind the operational decisions.', description: 'Compare saved Phase 5.5 experiments and the Phase 6 recovery invariant audit.' },
];

