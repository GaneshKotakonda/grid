// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from './App';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function setup(path = '/') {
  const result = {
    final_system_status: 'STABLE', final_load_served: 120, final_load_served_percent: 90,
    load_served_before_mitigation: 140, failed_lines: [1], audit_log: [],
    initial_grid_state: { gcn_risk_mean: 0.12, initial_outages: [1] },
    line_predictions: Array.from({ length: 15 }, (_, i) => ({ line_index: i, from_bus: 0, to_bus: 1, probability: i / 100 })),
  };
  const fetchMock = vi.fn(async (url) => ({ ok: true, json: async () => url === '/simulate' ? result : url === '/benchmarks' ? { key_findings: { load_served_gain_pp: 4.17, load_shedding_reduction_percent: 69.5, blackout_rate_reduction_pp: 3 } } : null }));
  vi.stubGlobal('fetch', fetchMock);
  render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
  return fetchMock;
}

test('home explains the project without operational controls', async () => {
  setup();
  expect(screen.getByRole('heading', { name: /Predict instability/ })).toBeTruthy();
  expect(screen.queryByText('Scenario Command Deck')).toBeNull();
  await screen.findByText('+4.17 pp');
});

test('navigation retains inputs and simulation data without refetching the controller', async () => {
  const fetchMock = setup('/operations');
  fireEvent.change(screen.getByLabelText('Seed'), { target: { value: '7' } });
  fireEvent.click(screen.getByRole('button', { name: 'Run GridResilience' }));
  await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => url === '/simulate')).toBe(true));
  await screen.findByText('STABLE GRID');
  const request = fetchMock.mock.calls.find(([url]) => url === '/simulate')[1];
  expect(JSON.parse(request.body)).toEqual({ initial_outage: 1, load_scale: 1.1, capacity_scale: 0.02, seed: 7 });
  fireEvent.click(screen.getAllByRole('link', { name: 'Prediction' })[0]);
  expect(screen.getByText('Line 14')).toBeTruthy();
  expect(document.querySelectorAll('.forecast-row')).toHaveLength(15);
  fireEvent.click(screen.getAllByRole('link', { name: 'Operations' })[0]);
  expect(screen.getByLabelText('Seed').value).toBe('7');
  expect(screen.getByText('STABLE GRID')).toBeTruthy();
  expect(fetchMock.mock.calls.filter(([url]) => url === '/grid')).toHaveLength(1);
});

test.each([
  ['/topology', /Inspect the grid/],
  ['/prediction', /Understand where/],
  ['/mitigation', /Trace every/],
  ['/recovery', /Restore service/],
  ['/timeline', /Follow the incident/],
  ['/benchmarks', /Evidence behind/],
])('direct entry to %s renders its focused feature page', (path, heading) => {
  setup(path);
  expect(screen.getByRole('heading', { name: heading })).toBeTruthy();
  expect(screen.queryByText('Scenario Command Deck')).toBeNull();
});

test('unknown client path returns to the homepage', async () => {
  setup('/unknown-feature');
  await screen.findByRole('heading', { name: /Predict instability/ });
});

test('route navigation starts at the document top', () => {
  setup('/operations');
  document.documentElement.scrollTop = 480;
  fireEvent.click(screen.getAllByRole('link', { name: 'Prediction' })[0]);
  expect(document.documentElement.scrollTop).toBe(0);
});
