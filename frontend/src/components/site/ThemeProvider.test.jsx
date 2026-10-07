// @vitest-environment jsdom
import React from 'react';
import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import ThemeProvider from './ThemeProvider';
import { getSavedTheme, useTheme } from './theme';
afterEach(() => { cleanup(); localStorage.clear(); vi.restoreAllMocks(); });
function Control() { const { theme, toggleTheme } = useTheme(); return <button onClick={toggleTheme}>{theme}</button>; }
test('theme defaults to light and persists a change across mounts', () => {
  localStorage.setItem('gridresilience-theme', 'invalid');
  const first = render(<ThemeProvider><Control /></ThemeProvider>);
  fireEvent.click(screen.getByRole('button', { name: 'light' }));
  expect(document.documentElement.dataset.theme).toBe('dark');
  expect(localStorage.getItem('gridresilience-theme')).toBe('dark');
  first.unmount();
  render(<ThemeProvider><Control /></ThemeProvider>);
  expect(screen.getByRole('button', { name: 'dark' })).toBeTruthy();
});
test('blocked browser storage falls back to light without throwing', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
  expect(getSavedTheme()).toBe('light');
  render(<ThemeProvider><Control /></ThemeProvider>);
  fireEvent.click(screen.getByRole('button', { name: 'light' }));
  expect(document.documentElement.dataset.theme).toBe('dark');
});
