import React from 'react';
import { FileTextIcon, ImageIcon, HelpCircleIcon, CompassIcon } from 'lucide-react';
import type { NormalizedAnalysis } from '../../utils/normalizeAnalysis';

export function AnalysisInputCard({ input }: { input?: NormalizedAnalysis['input'] }) {
  if (!input) return null;

  return (
    <div
      className="analysis-input-card"
      style={{
        background: 'var(--surface-2, #17131b)',
        border: '1px solid var(--line, rgba(255, 255, 255, 0.085))',
        borderRadius: 12,
        padding: '14px 18px',
        marginBottom: 16
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
        <HelpCircleIcon size={14} color="var(--accent, #a56cff)" />
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            color: 'var(--muted, #a9a0ad)'
          }}
        >
          Analysis Input & Objective
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: input.imagePreviewUrl ? 'minmax(0, 1fr) 140px' : '1fr', gap: 16 }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-strong, #f7f2fa)', marginBottom: 8 }}>
            "{input.query || 'Describe the satellite imagery'}"
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, fontSize: 12, color: 'var(--muted, #a9a0ad)' }}>
            {input.filename && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                <FileTextIcon size={13} color="var(--accent, #a56cff)" />
                <b style={{ color: 'var(--text, #f4eef7)' }}>{input.filename}</b>
                {input.fileSize && <span>({input.fileSize})</span>}
              </span>
            )}

            {input.fileType && (
              <span className="badge" style={{ fontSize: 10, padding: '2px 7px' }}>
                {input.fileType}
              </span>
            )}

            <span className="badge" style={{ fontSize: 10, padding: '2px 7px' }}>
              <CompassIcon size={11} style={{ marginRight: 3 }} />
              {input.analysisType}
            </span>

            <span className="badge" style={{ fontSize: 10, padding: '2px 7px', background: 'var(--surface-3)' }}>
              {input.inputCategory}
            </span>
          </div>
        </div>

        {input.imagePreviewUrl && (
          <div
            style={{
              width: 140,
              height: 90,
              borderRadius: 8,
              overflow: 'hidden',
              border: '1px solid var(--line, rgba(255, 255, 255, 0.1))',
              background: 'var(--viewer-bg, #17121d)',
              position: 'relative'
            }}
          >
            <img
              src={input.imagePreviewUrl}
              alt="Input preview"
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            />
            <span
              style={{
                position: 'absolute',
                bottom: 4,
                right: 4,
                background: 'rgba(0, 0, 0, 0.75)',
                color: '#fff',
                fontSize: 9,
                fontWeight: 600,
                padding: '1px 5px',
                borderRadius: 4,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 3
              }}
            >
              <ImageIcon size={9} /> Input
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
