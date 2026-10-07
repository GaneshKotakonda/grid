import React from 'react';
import PageIntro from '../components/site/PageIntro';
import MitigationPanel from '../components/MitigationPanel';
export default function MitigationPage(props) {
  return <div className="feature-page feature-page--mitigation"><PageIntro path="/mitigation" /><MitigationPanel {...props} /></div>;
}

