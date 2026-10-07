import React from 'react';
import PageIntro from '../components/site/PageIntro';
import FailurePredictionPanel from '../components/FailurePredictionPanel';
export default function PredictionPage(props) {
  return <div className="feature-page feature-page--prediction"><PageIntro path="/prediction" /><FailurePredictionPanel {...props} /></div>;
}

