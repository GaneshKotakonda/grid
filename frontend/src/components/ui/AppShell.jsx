import React from 'react';
import SiteHeader from '../site/SiteHeader';
import SiteFooter from '../site/SiteFooter';
export default function AppShell({ isBackendHealthy, children }) {
  return <div className="app-shell"><SiteHeader isBackendHealthy={isBackendHealthy} /><main id="main-content" className="site-content" tabIndex={-1}>{children}</main><SiteFooter /></div>;
}
