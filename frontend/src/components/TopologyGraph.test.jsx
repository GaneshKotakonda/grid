// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, test, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import TopologyPage from '../pages/TopologyPage';
import { MemoryRouter } from 'react-router-dom';

const gridData = {
  buses: [0, 1, 2].map((id) => ({ id, x: id * 100 + 40, y: 100, name: `Bus ${id + 1}` })),
  lines: [0, 1, 2].map((id) => ({ id, from_bus: id % 2, to_bus: id % 2 + 1 })),
};
const result = {
  run_id: 'first', initial_grid_state: { initial_outages: [0] },
  failed_lines: [0, 1, 2], reconnected_lines: [0], final_system_status: 'PARTIAL_BLACKOUT',
  gcn_failure_probabilities: [0.8, 0.6, 0.1],
  audit_log: [
    { stage: '1_CONTINGENCY', initial_outages: [0] },
    { stage: '2_MITIGATION_STEP_1', action: 'do_nothing', newly_failed: [1, 2], final_status: 'PARTIAL_BLACKOUT' },
    { stage: '3_CASCADE_RESULT', tripped_lines: [0, 1, 2], status: 'PARTIAL_BLACKOUT' },
    { stage: '4_RECOVERY_STEP_1', action: 'reconnect_line_1', committed: false, reason: 'Rejected: voltage violation' },
    { stage: '4_RECOVERY_STEP_2', action: 'reconnect_line_0', committed: true, reason: 'Committed safely' },
  ],
};
function view(simResult = result) {
  return <MemoryRouter><TopologyPage gridData={gridData} simResult={simResult} setSelectedElement={() => {}} /></MemoryRouter>;
}
afterEach(() => { cleanup(); vi.useRealTimers(); });

test('shows output first, then plays from the base graph and can pause and replay', () => {
  vi.useFakeTimers();
  render(view());
  expect(screen.getByRole('button', { name: 'Line 0: RECONNECTED' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Play' }));
  expect(screen.getByRole('button', { name: 'Line 0: IN_SERVICE' })).toBeTruthy();
  act(() => { vi.advanceTimersByTime(1500); });
  expect(screen.getByRole('button', { name: 'Line 0: FAILED' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Pause' }));
  act(() => { vi.advanceTimersByTime(5000); });
  expect(screen.getByRole('slider', { name: 'Playback step' }).value).toBe('1');
  fireEvent.click(screen.getByRole('button', { name: 'Replay' }));
  expect(screen.getByRole('slider', { name: 'Playback step' }).value).toBe('0');
});

test('keeps simultaneous trips together and never reconnects a rejected recovery action', () => {
  render(view());
  const slider = screen.getByRole('slider', { name: 'Playback step' });
  fireEvent.change(slider, { target: { value: '2' } });
  expect(screen.getByRole('button', { name: 'Line 1: FAILED' })).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Line 2: FAILED' })).toBeTruthy();
  fireEvent.change(slider, { target: { value: '4' } });
  expect(screen.getByText(/Rejected: voltage violation/)).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Line 1: FAILED' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Next step' }));
  expect(screen.getByRole('button', { name: 'Line 0: RECONNECTED' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Show output' }));
  expect(slider.value).toBe(slider.max);
});

test('a new simulation returns to its output and playback waits for a simulation', () => {
  const { rerender } = render(view());
  fireEvent.change(screen.getByRole('slider', { name: 'Playback step' }), { target: { value: '0' } });
  rerender(view({ ...result, run_id: 'second', reconnected_lines: [1] }));
  expect(screen.getByRole('button', { name: 'Line 1: RECONNECTED' })).toBeTruthy();
  rerender(view(null));
  expect(screen.getByRole('button', { name: 'Play' }).disabled).toBe(true);
});

test('playback honors speed and stops on the exact final output', () => {
  vi.useFakeTimers();
  render(view());
  fireEvent.change(screen.getByRole('combobox', { name: 'Speed' }), { target: { value: '2' } });
  fireEvent.click(screen.getByRole('button', { name: 'Play' }));
  const slider = screen.getByRole('slider', { name: 'Playback step' });
  for (let step = 1; step <= Number(slider.max); step++) {
    act(() => { vi.advanceTimersByTime(750); });
    expect(slider.value).toBe(String(step));
  }
  expect(screen.getByRole('button', { name: 'Play' })).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Line 0: RECONNECTED' })).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Line 2: FAILED' })).toBeTruthy();
});

test('a snapshot without an audit log does not invent intermediate failures or recovery', () => {
  render(view({ ...result, audit_log: [] }));
  expect(screen.getByText(/Intermediate events unavailable/)).toBeTruthy();
  expect(screen.getByRole('slider', { name: 'Playback step' }).max).toBe('1');
});
