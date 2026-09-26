import React from 'react';

interface Point {
  label: string;
  value: number;
}

export function GreennessChart({ points }: {points: Point[];}) {
  const W = 800;
  const H = 240;
  const pad = { l: 48, r: 20, t: 16, b: 34 };
  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 0.01;
  const lo = min - span * 0.15;
  const hi = max + span * 0.15;
  const x = (i: number) => pad.l + (points.length === 1 ? 0 : i / (points.length - 1) * (W - pad.l - pad.r));
  const y = (v: number) => pad.t + (1 - (v - lo) / (hi - lo)) * (H - pad.t - pad.b);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => lo + t * (hi - lo));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Greenness index per image">
      {ticks.map((t) =>
      <g key={t}>
          <line className="chart-grid" x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} />
          <text className="chart-text" x={pad.l - 8} y={y(t) + 4} textAnchor="end">
            {t.toFixed(3)}
          </text>
        </g>
      )}
      <line className="chart-axis" x1={pad.l} x2={W - pad.r} y1={H - pad.b} y2={H - pad.b} />
      <polyline
        points={points.map((p, i) => `${x(i)},${y(p.value)}`).join(' ')}
        fill="none"
        stroke="var(--accent)"
        strokeWidth={3}
        strokeLinejoin="round" />
      
      {points.map((p, i) =>
      <g key={p.label + i}>
          <circle cx={x(i)} cy={y(p.value)} r={5} fill="var(--accent)" stroke="var(--panel-solid)" strokeWidth={2} />
          <text className="chart-text" x={x(i)} y={H - pad.b + 20} textAnchor="middle">
            {p.label}
          </text>
        </g>
      )}
    </svg>);

}