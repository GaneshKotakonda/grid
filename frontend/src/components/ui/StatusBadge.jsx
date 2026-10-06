import React from 'react';

export default function StatusBadge({ children, tone = 'neutral', dot = false, className = '' }) {
  return (
    <span className={`status-badge status-badge--${tone} ${className}`.trim()}>
      {dot && <span className="status-badge__dot" aria-hidden="true" />}
      {children}
    </span>
  );
}
