import React from 'react';

export default function GridLogo({ size = 42, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={{
        display: 'inline-block',
        verticalAlign: 'middle',
        filter: 'drop-shadow(0 0 12px rgba(6, 182, 212, 0.45))',
        flexShrink: 0,
      }}
    >
      <defs>
        {/* Dark Cyber-Physical Shield Background Gradient */}
        <linearGradient id="navShieldBg" x1="8" y1="4" x2="56" y2="60" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#0e1726" />
          <stop offset="45%" stopColor="#0a0f1d" />
          <stop offset="100%" stopColor="#030712" />
        </linearGradient>

        {/* Glowing Cyber Blue-Cyan Outer Border Gradient */}
        <linearGradient id="navShieldBorder" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="30%" stopColor="#06b6d4" />
          <stop offset="70%" stopColor="#3b82f6" />
          <stop offset="100%" stopColor="#8b5cf6" />
        </linearGradient>

        {/* Radiant High-Voltage Lightning Gradient */}
        <linearGradient id="navBoltGrad" x1="34" y1="10" x2="26" y2="52" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#67e8f9" />
          <stop offset="35%" stopColor="#22d3ee" />
          <stop offset="70%" stopColor="#0284c7" />
          <stop offset="100%" stopColor="#2563eb" />
        </linearGradient>

        {/* Core Lightning Highlight */}
        <linearGradient id="navCoreGrad" x1="33" y1="12" x2="28" y2="48" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="50%" stopColor="#e0f2fe" />
          <stop offset="100%" stopColor="#7dd3fc" />
        </linearGradient>

        {/* Transmission Grid Lines Gradient */}
        <linearGradient id="navLineGrad" x1="16" y1="14" x2="48" y2="50" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#0284c7" stopOpacity="0.75" />
          <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.9" />
        </linearGradient>
      </defs>

      {/* Outer Resilience Shield / Crest */}
      <path
        d="M32 4 C48 4 58 10 58 24 C58 44 43 56 32 60 C21 56 6 44 6 24 C6 10 16 4 32 4 Z"
        fill="url(#navShieldBg)"
        stroke="url(#navShieldBorder)"
        strokeWidth="2.75"
        strokeLinejoin="round"
      />

      {/* Inner Subtle Shield Ring */}
      <path
        d="M32 8 C44 8 52 13 52 24 C52 40 40 50 32 54 C24 50 12 40 12 24 C12 13 20 8 32 8 Z"
        fill="none"
        stroke="#1e293b"
        strokeWidth="1"
        strokeDasharray="2 2"
        opacity="0.6"
      />

      {/* Power Grid Interconnections (Transmission Lines Topology) */}
      <g stroke="url(#navLineGrad)" strokeWidth="1.8" strokeLinecap="round">
        <line x1="18" y1="23" x2="32" y2="15" />
        <line x1="32" y1="15" x2="46" y2="23" />
        <line x1="46" y1="23" x2="43" y2="41" />
        <line x1="43" y1="41" x2="32" y2="49" />
        <line x1="32" y1="49" x2="21" y2="41" />
        <line x1="21" y1="41" x2="18" y2="23" />

        <line x1="18" y1="23" x2="43" y2="41" strokeDasharray="2.5 2" opacity="0.5" />
        <line x1="46" y1="23" x2="21" y2="41" strokeDasharray="2.5 2" opacity="0.5" />
        <line x1="32" y1="15" x2="32" y2="49" strokeDasharray="2 2" opacity="0.35" />
      </g>

      {/* Substation Bus Nodes (IEEE Nodes with Status Rings) */}
      <circle cx="32" cy="15" r="5" fill="#0284c7" fillOpacity="0.25" />
      <circle cx="32" cy="15" r="2.8" fill="#38bdf8" />
      <circle cx="32" cy="15" r="1.2" fill="#ffffff" />

      <circle cx="46" cy="23" r="4.5" fill="#10b981" fillOpacity="0.25" />
      <circle cx="46" cy="23" r="2.6" fill="#10b981" />
      <circle cx="46" cy="23" r="1" fill="#ecfdf5" />

      <circle cx="43" cy="41" r="4.5" fill="#06b6d4" fillOpacity="0.25" />
      <circle cx="43" cy="41" r="2.6" fill="#38bdf8" />

      <circle cx="32" cy="49" r="5" fill="#10b981" fillOpacity="0.25" />
      <circle cx="32" cy="49" r="2.8" fill="#10b981" />
      <circle cx="32" cy="49" r="1.2" fill="#ffffff" />

      <circle cx="21" cy="41" r="4.5" fill="#06b6d4" fillOpacity="0.25" />
      <circle cx="21" cy="41" r="2.6" fill="#38bdf8" />

      <circle cx="18" cy="23" r="4.5" fill="#10b981" fillOpacity="0.25" />
      <circle cx="18" cy="23" r="2.6" fill="#10b981" />
      <circle cx="18" cy="23" r="1" fill="#ecfdf5" />

      {/* Central High-Voltage Resilience Energy Bolt */}
      <path
        d="M34 10 L19 31 L31 31 L26 52 L45 27 L33 27 Z"
        fill="url(#navBoltGrad)"
        stroke="#bae6fd"
        strokeWidth="1.2"
        strokeLinejoin="round"
      />

      {/* Core Electric Energy Glimmer (Inner 3D Ridge) */}
      <path
        d="M33 13 L22 30 L31 30 L28 47 L41 28 L32 28 Z"
        fill="url(#navCoreGrad)"
        opacity="0.85"
      />
    </svg>
  );
}
