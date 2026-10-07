import { createContext, useContext } from 'react';
export const ThemeContext = createContext({ theme: 'light', toggleTheme: () => {} });
export function getSavedTheme() {
  try { return localStorage.getItem('gridresilience-theme') === 'dark' ? 'dark' : 'light'; } catch { return 'light'; }
}
export function useTheme() { return useContext(ThemeContext); }
