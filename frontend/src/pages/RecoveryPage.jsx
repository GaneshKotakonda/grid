import React from 'react';
import PageIntro from '../components/site/PageIntro';
import RecoveryPanel from '../components/RecoveryPanel';
export default function RecoveryPage(props) {
  return <div className="feature-page feature-page--recovery"><PageIntro path="/recovery" /><RecoveryPanel {...props} /></div>;
}

