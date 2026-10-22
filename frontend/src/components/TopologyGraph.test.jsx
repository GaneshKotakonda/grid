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

test('automatically constructs the output from the base graph and can pause and replay', () => {
  vi.useFakeTimers();
  render(view());
  expect(screen.getByRole('button', { name: 'Pause' })).toBeTruthy();
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

test('a new simulation restarts construction and playback waits for a simulation', () => {
  const { rerender } = render(view());
  fireEvent.change(screen.getByRole('slider', { name: 'Playback step' }), { target: { value: '0' } });
  rerender(view({ ...result, run_id: 'second', reconnected_lines: [1] }));
  expect(screen.getByRole('button', { name: 'Line 1: IN_SERVICE' })).toBeTruthy();
  rerender(view(null));
  expect(screen.getByRole('button', { name: 'Play' }).disabled).toBe(true);
});

test('playback honors speed and stops on the exact final output', () => {
  vi.useFakeTimers();
  render(view());
  fireEvent.change(screen.getByRole('combobox', { name: 'Speed' }), { target: { value: '2' } });
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
  fireEvent.click(screen.getByRole('button', { name: 'Show output' }));
  expect(screen.getByText(/Intermediate events unavailable/)).toBeTruthy();
  expect(screen.getByRole('slider', { name: 'Playback step' }).max).toBe('1');
});


test('load recovery updates the affected bus and MW on every frame, including backwards seeking', () => {
  const snapshot = (mw) => ({ buses: [{ id: 2, load_mw: mw, voltage_pu: 1.02, supplied: true }], lines: [] });
  render(view({ ...result, audit_log: [
    { stage: '1_CONTINGENCY', initial_outages: [0], served_load_mw: 80, grid_state: snapshot(20) },
    { stage: '4_RECOVERY_STEP_1', action: 'restore_load_bus_2', committed: true, served_load_mw: 90, grid_state: snapshot(30) },
    { stage: '4_RECOVERY_STEP_2', action: 'restore_load_bus_2', committed: true, served_load_mw: 95, grid_state: snapshot(35) },
  ] }));
  const slider = screen.getByRole('slider', { name: 'Playback step' });
  fireEvent.change(slider, { target: { value: '2' } });
  expect(screen.getByText('30.0 MW')).toBeTruthy();
  expect(screen.getByText('90.00 MW served')).toBeTruthy();
  expect(screen.getByRole('button', { name: /Bus 3/ }).getAttribute('data-active')).toBe('true');
  fireEvent.change(slider, { target: { value: '3' } });
  expect(screen.getByText('35.0 MW')).toBeTruthy();
  expect(screen.getByText('95.00 MW served')).toBeTruthy();
  fireEvent.change(slider, { target: { value: '1' } });
  expect(screen.getByText('20.0 MW')).toBeTruthy();
});

test('recorded risk appears at its own step rather than suddenly at the output', () => {
  render(view({ ...result, audit_log: [
    { stage: '1_CONTINGENCY', initial_outages: [], gcn_probabilities: [0.1, 0.7, 0.1] },
    { stage: '2_MITIGATION_STEP_1', action: 'do_nothing', gcn_probabilities: [0.1, 0.25, 0.1] },
  ] }));
  const slider = screen.getByRole('slider', { name: 'Playback step' });
  fireEvent.change(slider, { target: { value: '1' } });
  expect(screen.getByRole('button', { name: 'Line 1: PREDICTED_FAILURE' })).toBeTruthy();
  fireEvent.change(slider, { target: { value: '2' } });
  expect(screen.getByRole('button', { name: 'Line 1: HIGH_RISK' })).toBeTruthy();
});
