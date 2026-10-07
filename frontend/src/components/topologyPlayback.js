// Presentation snapshots from the recorded incident trace, in its original order.
// A trip wave remains one frame; no ordering within that wave is inferred.
export function buildTopologyPlayback(result) {
  if (!result) return [];
  const frames = [];
  let failed = new Set();
  let restored = new Set();
  const add = (frame) => frames.push({
    failedLines: [...failed], reconnectedLines: [...restored],
    activeTrips: [], activeReconnections: [], tone: 'info', ...frame,
  });
  add({ title: 'Base graph', detail: 'Transmission connections before the initiating outage.', tone: 'safe' });

  for (const event of result.audit_log || []) {
    if (event.stage === '1_CONTINGENCY') {
      const trips = event.initial_outages || [];
      trips.forEach((id) => failed.add(id));
      add({ title: 'Initial outage', detail: `Disconnected: ${trips.map((id) => `Line ${id}`).join(', ')}.`, activeTrips: trips, tone: 'danger' });
    } else if (event.stage?.includes('MITIGATION_STEP')) {
      const trips = event.newly_failed || [];
      trips.forEach((id) => { failed.add(id); restored.delete(id); });
      add({
        title: 'PPO mitigation & cascade', tone: trips.length ? 'danger' : 'info',
        detail: `${event.action || 'Mitigation step'}${trips.length ? ` · New trips: ${trips.map((id) => `Line ${id}`).join(', ')}` : ' · No new trips recorded'}${event.final_status ? ` · ${event.final_status}` : ''}`,
        activeTrips: trips,
      });
    } else if (event.stage === '3_CASCADE_RESULT') {
      const previous = failed;
      failed = new Set(event.tripped_lines || [...failed]);
      add({ title: 'Post-cascade state', detail: `${event.status || 'Recorded state'} · ${failed.size} disconnected lines`, activeTrips: [...failed].filter((id) => !previous.has(id)), tone: event.status === 'STABLE' ? 'safe' : 'warning' });
    } else if (event.stage?.includes('RECOVERY_STEP')) {
      const match = /^reconnect_line_(\d+)$/.exec(event.action || '');
      const reconnected = match && event.committed === true ? [Number(match[1])] : [];
      reconnected.forEach((id) => restored.add(id));
      add({
        title: event.committed ? 'Recovery committed' : 'Recovery not committed',
        detail: `${event.action || 'Recovery step'} · ${event.reason || (event.committed ? 'Committed' : 'Not committed')}`,
        activeReconnections: reconnected, tone: event.committed ? 'safe' : 'warning',
      });
    }
  }

  failed = new Set([...(result.failed_lines || []), ...(result.initial_grid_state?.initial_outages || [])]);
  restored = new Set(result.reconnected_lines || []);
  add({ title: 'Simulation output', detail: `${result.final_system_status || 'Recorded output'}${frames.length === 1 ? ' · Intermediate events unavailable for this run' : ' · Playback complete'}`, isOutput: true, tone: result.final_system_status === 'STABLE' ? 'safe' : 'warning' });
  return frames;
}
