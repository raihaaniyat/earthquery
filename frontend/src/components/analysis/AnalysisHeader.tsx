import React from 'react';
import { CheckCircle2Icon, ShieldCheckIcon, CpuIcon, LayersIcon } from 'lucide-react';
import type { NormalizedAnalysis } from '../../utils/normalizeAnalysis';

export function AnalysisHeader({ header }: { header: NormalizedAnalysis['header'] }) {
  return (
    <div
      className="analysis-header"
      style={{
        background: 'var(--panel-solid, #131017)',
        border: '1px solid var(--line, rgba(255, 255, 255, 0.085))',
        borderRadius: 12,
        padding: '14px 18px',
        marginBottom: 16,
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12
      }}
    >
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              color: 'var(--accent, #a56cff)',
              background: 'var(--accent-soft, rgba(165, 108, 255, 0.15))',
              padding: '2px 7px',
              borderRadius: 4
            }}
          >
            AI Platform
          </span>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: 'var(--text-strong, #f7f2fa)' }}>
            {header.title}
          </h3>
        </div>
        {header.query && (
          <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--muted, #a9a0ad)' }}>
            Query: <span style={{ color: 'var(--text, #f4eef7)', fontStyle: 'italic' }}>"{header.query}"</span>
          </p>
        )}
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
        <span
          className="badge ok"
          style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '4px 9px', fontSize: 11 }}
        >
          <CheckCircle2Icon size={12} />
          {header.status}
        </span>

        <span
          className="badge"
          style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '4px 9px', fontSize: 11 }}
        >
          <ShieldCheckIcon size={12} />
          Validation: {header.validation}
        </span>

        <span
          className="badge"
          style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '4px 9px', fontSize: 11 }}
        >
          <CpuIcon size={12} />
          {header.modelCount} AI Models
        </span>

        <span
          className="badge"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            padding: '4px 9px',
            fontSize: 11,
            background: 'var(--surface-3, #1c1721)'
          }}
        >
          <LayersIcon size={12} />
          {header.processingType}
        </span>
      </div>
    </div>
  );
}
