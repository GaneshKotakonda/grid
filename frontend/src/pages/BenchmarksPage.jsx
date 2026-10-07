import React from 'react';
import PageIntro from '../components/site/PageIntro';
import ComparisonPanel from '../components/ComparisonPanel';
export default function BenchmarksPage(props) {
  return <div className="feature-page feature-page--benchmarks"><PageIntro path="/benchmarks" /><ComparisonPanel {...props} /></div>;
}

