import React, { useEffect, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { Moon, Sun, Menu, X, ChevronDown } from 'lucide-react';
import { SITE_ROUTES } from '../../routes/siteRoutes';
import { useTheme } from './theme';
import GridLogo from '../GridLogo';
export default function SiteHeader({ isBackendHealthy }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const { theme, toggleTheme } = useTheme();
  const { pathname } = useLocation();
  useEffect(() => {
    document.title = `${SITE_ROUTES.find((page) => page.path === pathname)?.label || 'Home'} · GridResilience`;
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  }, [pathname]);
  const navLink = ({ path, label }) => <NavLink key={path} to={path} end onClick={() => setMenuOpen(false)} className={({ isActive }) => isActive ? 'is-active' : ''}>{label}</NavLink>;
  return <header className="site-header">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <Link className="site-brand" to="/" aria-label="GridResilience home"><GridLogo size={35} />GridResilience</Link>
    <nav className="site-nav" aria-label="Main navigation">{SITE_ROUTES.filter((page) => page.group === 'primary').map(navLink)}
      <details className="research-menu" key={pathname}><summary className={['/timeline','/benchmarks'].includes(pathname) ? 'is-active' : ''}>Research <ChevronDown size={13} /></summary><div>{SITE_ROUTES.filter((page) => page.group === 'research').map(navLink)}</div></details>
    </nav>
    <div className="site-header__actions">
      <span className={`connection-status ${isBackendHealthy ? 'is-connected' : ''}`} title={isBackendHealthy ? 'FastAPI connected' : 'Connecting to API'}><i />{isBackendHealthy ? 'API online' : 'Connecting'}</span>
      <button className="theme-toggle" aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`} onClick={toggleTheme}>{theme === 'light' ? <Moon size={17} /> : <Sun size={17} />}</button>
      <Link className="site-button site-button--dark header-launch" to="/operations">Launch Operations <span>↗</span></Link>
      <button className="mobile-menu-toggle" aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={menuOpen} aria-controls="mobile-navigation" onClick={() => setMenuOpen((value) => !value)}>{menuOpen ? <X size={21} /> : <Menu size={21} />}</button>
    </div>
    {menuOpen && <nav id="mobile-navigation" className="mobile-navigation" aria-label="Mobile navigation" onKeyDown={(event) => { if (event.key === 'Escape') setMenuOpen(false); }}>{SITE_ROUTES.map(navLink)}</nav>}
  </header>;
}
