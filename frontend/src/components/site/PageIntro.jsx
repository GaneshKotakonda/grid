import React from 'react';
import { Link } from 'react-router-dom';
import { SITE_ROUTES } from '../../routes/siteRoutes';
export default function PageIntro({ path }) {
  const page = SITE_ROUTES.find((item) => item.path === path);
  return <div className="page-intro"><div><span className="eyebrow">{page.phase}</span><h1>{page.title}</h1><p>{page.description}</p></div>{path !== '/operations' && <Link className="site-button site-button--outline" to="/operations">Configure scenario →</Link>}</div>;
}

