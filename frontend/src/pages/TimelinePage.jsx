import React from 'react';
import PageIntro from '../components/site/PageIntro';
import CascadeTimeline from '../components/CascadeTimeline';
export default function TimelinePage(props) {
  return <div className="feature-page feature-page--timeline"><PageIntro path="/timeline" /><CascadeTimeline {...props} /></div>;
}

