import React from 'react';

export default function MetricCard({
  label,
  value,
  unit,
  icon: Icon,
  tone = 'neutral',
  hint,
  footer,
  children,
  className = '',
}) {
  return (
    <article className={`metric-card metric-card--${tone} ${className}`.trim()}>
      <div className="metric-card__header">
        <span>{label}</span>
        {Icon && <Icon size={16} />}
      </div>
      <div className="metric-card__value-row">
        <strong className="metric-card__value mono">{value}</strong>
        {unit && <span className="metric-card__unit">{unit}</span>}
      </div>
      {hint && <p className="metric-card__hint">{hint}</p>}
      {children}
      {footer && <div className="metric-card__footer">{footer}</div>}
    </article>
  );
}
