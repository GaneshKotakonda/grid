import React from 'react';
import PageIntro from '../components/site/PageIntro';
import TopologyGraph from '../components/TopologyGraph';
export default function TopologyPage(props) {
  return <div className="feature-page feature-page--topology"><PageIntro path="/topology" /><TopologyGraph key={props.simResult?.run_id || 'base'} {...props} /></div>;
}
