import React, { useState } from 'react';
import { MapPinIcon, LayersIcon, EyeIcon } from 'lucide-react';
import type { NormalizedAnalysis } from '../../utils/normalizeAnalysis';

const CLASS_COLORS = [
  '#45d483', // green
  '#3b82f6', // blue
  '#a855f7', // purple
  '#f59e0b', // amber
  '#ec4899', // pink
  '#06b6d4', // cyan
  '#10b981', // emerald
  '#8b5cf6'  // violet
];

export function UPerNetCard({ upernet }: { upernet?: NormalizedAnalysis['models']['upernet'] }) {
  const [zoomMask, setZoomMask] = useState(false);

  if (!upernet || !upernet.available) {
    return (
      <div className="model-card panel" style={{ opacity: 0.65, padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <LayersIcon size={18} color="var(--faint, #746c78)" />
          <b style={{ color: 'var(--text-soft)' }}>UPerNet ConvNeXt</b>
          <span className="badge" style={{ fontSize: 10, marginLeft: 'auto' }}>Inactive</span>
        </div>
        <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--muted)' }}>
          Surface segmentation was not executed for this image mode.
        </p>
      </div>
    );
  }

  const classes = upernet.classes || [];

  return (
    <div
      className="model-card"
      style={{
        background: 'var(--panel-solid, #131017)',
        border: '1px solid var(--line, rgba(255, 255, 255, 0.085))',
        borderRadius: 12,
        padding: 18,
        position: 'relative'
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 8,
              background: 'rgba(59, 130, 246, 0.15)',
              display: 'grid',
              placeItems: 'center',
              color: '#60a5fa'
            }}
          >
            <LayersIcon size={20} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <h4 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: 'var(--text-strong, #f7f2fa)' }}>
                UPerNet ConvNeXt
              </h4>
              <span className="badge ok" style={{ fontSize: 10, padding: '2px 6px' }}>
                Surface Segmentation
              </span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted, #a9a0ad)', marginTop: 2 }}>
              {upernet.role} • {upernet.analysisType}
            </div>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: upernet.maskUrl ? 'minmax(0, 1.2fr) minmax(0, 0.8fr)' : '1fr', gap: 16 }}>
        {/* Classes Table */}
        <div>
          <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)' }}>
            Semantic Land-Cover Distribution
          </span>

          {classes.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
              {classes.map((cls, i) => {
                const color = CLASS_COLORS[i % CLASS_COLORS.length];
                return (
                  <div key={i} style={{ background: 'var(--surface-2)', borderRadius: 8, padding: '8px 12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
                        {cls.name}
                      </span>
                      <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-strong)', fontVariantNumeric: 'tabular-nums' }}>
                        {cls.coveragePct.toFixed(2)}%
                      </span>
                    </div>

                    <div style={{ width: '100%', height: 4, background: 'rgba(255, 255, 255, 0.08)', borderRadius: 2, overflow: 'hidden' }}>
                      <div
                        style={{
                          width: `${Math.min(100, cls.coveragePct)}%`,
                          height: '100%',
                          background: color,
                          borderRadius: 2
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--muted)' }}>
              Pixel-level surface classes extracted into segmentation mask.
            </p>
          )}

          {upernet.evidenceNote && (
            <div style={{ fontSize: 11, color: 'var(--faint)', fontStyle: 'italic', marginTop: 10 }}>
              Model Output: {upernet.evidenceNote}
            </div>
          )}
        </div>

        {/* Segmentation Mask Visualization */}
        {upernet.maskUrl && (
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)', marginBottom: 8 }}>
              Segmentation Mask Visualization
            </span>
            <div
              style={{
                position: 'relative',
                borderRadius: 8,
                overflow: 'hidden',
                border: '1px solid var(--line)',
                background: '#000',
                cursor: 'pointer'
              }}
              onClick={() => setZoomMask(!zoomMask)}
              title="Click to toggle expanded view"
            >
              <img
                src={upernet.maskUrl}
                alt="UPerNet segmentation mask"
                style={{
                  width: '100%',
                  height: zoomMask ? 'auto' : 180,
                  maxHeight: zoomMask ? 450 : 180,
                  objectFit: 'contain',
                  display: 'block'
                }}
              />
              <div
                style={{
                  position: 'absolute',
                  top: 6,
                  right: 6,
                  background: 'rgba(0, 0, 0, 0.7)',
                  color: '#fff',
                  borderRadius: 4,
                  padding: '2px 6px',
                  fontSize: 10,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 3
                }}
              >
                <EyeIcon size={10} />
                {zoomMask ? 'Collapse' : 'Expand'}
              </div>
            </div>
            <span style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4, textAlign: 'center' }}>
              Pixel coordinate mask rendering surface distribution
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
