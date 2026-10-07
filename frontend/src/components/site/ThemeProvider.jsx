import React, { useState, useEffect } from 'react';
import { ThemeContext, getSavedTheme } from './theme';
export default function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(getSavedTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('gridresilience-theme', theme); } catch { /* Storage may be disabled. */ }
  }, [theme]);
  return <ThemeContext.Provider value={{ theme, toggleTheme: () => setTheme((value) => value === 'dark' ? 'light' : 'dark') }}>{children}</ThemeContext.Provider>;
}
