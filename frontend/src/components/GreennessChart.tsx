import React, { useState } from 'react';

export interface TemporalPoint {
  label: string;
  value: number;
  date?: string | null;
}

interface GreennessChartProps {
  points: TemporalPoint[];
  metricName?: string;
  dateRange?: string;
  isLoading?: boolean;
}

export function GreennessChart({
  points,
  metricName = 'Excess Green Index (RGB proxy)',
  dateRange,
  isLoading = false
}: GreennessChartProps) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  if (isLoading) {
    return (
      <div style={{ padding: '36px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
        <div className="spin" style={{ display: 'inline-block', marginBottom: '8px' }}>⟳</div>
        <div>Loading temporal trend data…</div>
      </div>
    );
  }

  if (!points || points.length === 0) {
    return (
      <div style={{ padding: '36px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
        No temporal data points available. Add two or more dated scenes to generate temporal plots.
      </div>
    );
  }

  const W = 800;
  const H = 200;
  const pad = { l: 56, r: 24, t: 20, b: 38 };

  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 0.01;
  const lo = min - span * 0.15;
  const hi = max + span * 0.15;

  const getX = (i: number) => pad.l + (points.length === 1 ? (W - pad.l - pad.r) / 2 : (i / (points.length - 1)) * (W - pad.l - pad.r));
  const getY = (v: number) => pad.t + (1 - (v - lo) / (hi - lo)) * (H - pad.t - pad.b);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => lo + t * (hi - lo));

  return (
    <div className="temporal-trend-container" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header with Metric & Date Range */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px', paddingBottom: '10px', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text)' }}>Metric:</span>
          <span className="badge accent" style={{ fontSize: '11px' }}>{metricName}</span>
        </div>
        {dateRange && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#94a3b8' }}>
            <span>Date Range:</span>
            <b style={{ color: 'var(--text)' }}>{dateRange}</b>
          </div>
        )}
      </div>

      {/* 1. SCATTER PLOT */}
      <div className="chart-section">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <b style={{ fontSize: '13px', color: 'var(--text)' }}>1. Scatter Plot (Observations)</b>
          <span style={{ fontSize: '11px', color: '#94a3b8' }}>Date → X · Value → Y</span>
        </div>
        <div style={{ position: 'relative', background: 'rgba(0, 0, 0, 0.2)', borderRadius: '8px', padding: '8px' }}>
          <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', display: 'block' }} role="img" aria-label="Scatter plot">
            {/* Grid & Y Axis ticks */}
            {ticks.map((t, idx) => (
              <g key={`sp-tick-${idx}`}>
                <line className="chart-grid" x1={pad.l} x2={W - pad.r} y1={getY(t)} y2={getY(t)} stroke="rgba(255,255,255,0.08)" strokeDasharray="3 3" />
                <text className="chart-text" x={pad.l - 8} y={getY(t) + 4} textAnchor="end" fill="#94a3b8" fontSize="10">
                  {t.toFixed(3)}
                </text>
              </g>
            ))}
            <line className="chart-axis" x1={pad.l} x2={W - pad.r} y1={H - pad.b} y2={H - pad.b} stroke="rgba(255,255,255,0.2)" />
            <line className="chart-axis" x1={pad.l} x2={pad.l} y1={pad.t} y2={H - pad.b} stroke="rgba(255,255,255,0.2)" />

            {/* Scatter dots */}
            {points.map((p, i) => {
              const cx = getX(i);
              const cy = getY(p.value);
              const isHov = hoveredIdx === i;
              return (
                <g
                  key={`sp-pt-${i}`}
                  onMouseEnter={() => setHoveredIdx(i)}
                  onMouseLeave={() => setHoveredIdx(null)}
                  style={{ cursor: 'pointer' }}
                >
                  <circle
                    cx={cx}
                    cy={cy}
                    r={isHov ? 7 : 5}
                    fill="var(--accent, #a56cff)"
                    stroke="#ffffff"
                    strokeWidth={isHov ? 2.5 : 1.5}
                    style={{ transition: 'r 0.15s ease' }}
                  />
                  {/* X Axis Label */}
                  <text
                    x={cx}
                    y={H - pad.b + 18}
                    textAnchor="middle"
                    fill={isHov ? 'var(--text)' : '#94a3b8'}
                    fontSize="10"
                    fontWeight={isHov ? 600 : 400}
                  >
                    {p.date ? p.date.slice(5) : p.label}
                  </text>
                </g>
              );
            })}
          </svg>

          {/* Tooltip Overlay */}
          {hoveredIdx !== null && points[hoveredIdx] && (
            <div
              style={{
                position: 'absolute',
                top: 10,
                right: 14,
                background: 'rgba(15, 23, 42, 0.95)',
                border: '1px solid var(--accent)',
                borderRadius: '6px',
                padding: '6px 10px',
                fontSize: '11px',
                color: '#fff',
                boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
                pointerEvents: 'none'
              }}
            >
              <div><b>{points[hoveredIdx].label}</b> {points[hoveredIdx].date ? `(${points[hoveredIdx].date})` : ''}</div>
              <div style={{ color: 'var(--accent)' }}>Value: <b>{points[hoveredIdx].value.toFixed(4)}</b></div>
            </div>
          )}
        </div>
      </div>

      {/* 2. LINE CHART */}
      <div className="chart-section">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <b style={{ fontSize: '13px', color: 'var(--text)' }}>2. Line Chart (Temporal Trend)</b>
          <span style={{ fontSize: '11px', color: '#94a3b8' }}>Continuous time-series trajectory</span>
        </div>
        <div style={{ position: 'relative', background: 'rgba(0, 0, 0, 0.2)', borderRadius: '8px', padding: '8px' }}>
          <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', display: 'block' }} role="img" aria-label="Line chart">
            <defs>
              <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--accent, #a56cff)" stopOpacity="0.35" />
                <stop offset="100%" stopColor="var(--accent, #a56cff)" stopOpacity="0.0" />
              </linearGradient>
            </defs>

            {/* Grid & Y Axis ticks */}
            {ticks.map((t, idx) => (
              <g key={`lc-tick-${idx}`}>
                <line className="chart-grid" x1={pad.l} x2={W - pad.r} y1={getY(t)} y2={getY(t)} stroke="rgba(255,255,255,0.08)" strokeDasharray="3 3" />
                <text className="chart-text" x={pad.l - 8} y={getY(t) + 4} textAnchor="end" fill="#94a3b8" fontSize="10">
                  {t.toFixed(3)}
                </text>
              </g>
            ))}
            <line className="chart-axis" x1={pad.l} x2={W - pad.r} y1={H - pad.b} y2={H - pad.b} stroke="rgba(255,255,255,0.2)" />
            <line className="chart-axis" x1={pad.l} x2={pad.l} y1={pad.t} y2={H - pad.b} stroke="rgba(255,255,255,0.2)" />

            {/* Area under curve */}
            {points.length > 1 && (
              <polygon
                points={[
                  `${getX(0)},${H - pad.b}`,
                  ...points.map((p, i) => `${getX(i)},${getY(p.value)}`),
                  `${getX(points.length - 1)},${H - pad.b}`
                ].join(' ')}
                fill="url(#trendGradient)"
              />
            )}

            {/* Connected Trend Line */}
            {points.length > 1 && (
              <polyline
                points={points.map((p, i) => `${getX(i)},${getY(p.value)}`).join(' ')}
                fill="none"
                stroke="var(--accent, #a56cff)"
                strokeWidth={2.5}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            )}

            {/* Points along the line */}
            {points.map((p, i) => {
              const cx = getX(i);
              const cy = getY(p.value);
              const isHov = hoveredIdx === i;
              return (
                <g
                  key={`lc-pt-${i}`}
                  onMouseEnter={() => setHoveredIdx(i)}
                  onMouseLeave={() => setHoveredIdx(null)}
                  style={{ cursor: 'pointer' }}
                >
                  <circle
                    cx={cx}
                    cy={cy}
                    r={isHov ? 6 : 4}
                    fill={isHov ? '#ffffff' : 'var(--accent, #a56cff)'}
                    stroke="var(--accent, #a56cff)"
                    strokeWidth={2}
                  />
                  <text
                    x={cx}
                    y={H - pad.b + 18}
                    textAnchor="middle"
                    fill={isHov ? 'var(--text)' : '#94a3b8'}
                    fontSize="10"
                    fontWeight={isHov ? 600 : 400}
                  >
                    {p.date ? p.date.slice(5) : p.label}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>
    </div>
  );
}