import React from 'react';

export default function PanelHeader({
  icon: Icon,
  title,
  subtitle,
  badge,
  actions,
  as: Heading = 'h3',
}) {
  return (
    <div className="panel-header">
      <div className="panel-header__copy">
        <div className="panel-header__title-row">
          {Icon && <Icon className="panel-header__icon" size={17} />}
          <Heading>{title}</Heading>
          {badge}
        </div>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {actions && <div className="panel-header__actions">{actions}</div>}
    </div>
  );
}
