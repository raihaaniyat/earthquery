import React, { useState } from 'react';
import { BrainIcon, ChevronDownIcon, ChevronUpIcon, CompassIcon, ShieldCheckIcon, AlertTriangleIcon } from 'lucide-react';
import type { NormalizedAnalysis } from '../../utils/normalizeAnalysis';

export function InternVLCard({ internvl }: { internvl?: NormalizedAnalysis['models']['internvl'] }) {
  const [expanded, setExpanded] = useState(false);

  if (!internvl || !internvl.available) {
    return (
      <div className="model-card panel" style={{ opacity: 0.65, padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <BrainIcon size={18} color="var(--faint, #746c78)" />
          <b style={{ color: 'var(--text-soft)' }}>InternVL3-2B</b>
          <span className="badge" style={{ fontSize: 10, marginLeft: 'auto' }}>Inactive</span>
        </div>
        <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--muted)' }}>
          Model-specific visual reasoning was not invoked for this task pipeline.
        </p>
      </div>
    );
  }

  const hasExtra =
    internvl.spatialInterpretation.length > 0 ||
    Boolean(internvl.limitations) ||
    Boolean(internvl.evidenceNote);

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
              background: 'rgba(165, 108, 255, 0.15)',
              display: 'grid',
              placeItems: 'center',
              color: 'var(--accent, #a56cff)'
            }}
          >
            <BrainIcon size={20} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <h4 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: 'var(--text-strong, #f7f2fa)' }}>
                InternVL3-2B
              </h4>
              <span className="badge ok" style={{ fontSize: 10, padding: '2px 6px' }}>
                Active VLM
              </span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted, #a9a0ad)', marginTop: 2 }}>
              {internvl.role} • {internvl.task}
            </div>
          </div>
        </div>

        {internvl.confidence && (
          <span
            className="badge"
            style={{
              fontSize: 11,
              padding: '3px 8px',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              background: 'rgba(34, 197, 94, 0.12)',
              color: '#45d483',
              border: '1px solid rgba(34, 197, 94, 0.25)'
            }}
          >
            <ShieldCheckIcon size={12} />
            {internvl.confidence.length < 25 ? `Confidence: ${internvl.confidence}` : 'Confidence: High'}
          </span>
        )}
      </div>

      {/* Content */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* Scene Type */}
        {internvl.sceneType && (
          <div style={{ background: 'var(--surface-2, #17131b)', borderRadius: 8, padding: '10px 14px' }}>
            <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--accent-ink, #d7b7ff)' }}>
              Scene Classification
            </span>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-strong)', marginTop: 2 }}>
              {internvl.sceneType}
            </div>
          </div>
        )}

        {/* Direct Observation */}
        {internvl.directObservation && (
          <div>
            <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)' }}>
              Direct Visual Observation
            </span>
            <p style={{ margin: '4px 0 0', fontSize: 13, lineHeight: 1.6, color: 'var(--text)' }}>
              {internvl.directObservation}
            </p>
          </div>
        )}

        {/* Visual Features */}
        {internvl.visualFeatures.length > 0 && (
          <div>
            <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)' }}>
              Identified Visual Features
            </span>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 8, marginTop: 6 }}>
              {internvl.visualFeatures.map((f, i) => (
                <div
                  key={i}
                  style={{
                    background: 'var(--surface-2)',
                    border: '1px solid var(--line)',
                    borderRadius: 8,
                    padding: '8px 12px'
                  }}
                >
                  <b style={{ fontSize: 12, color: 'var(--text-strong)', display: 'block' }}>{f.name}</b>
                  {f.description && (
                    <span style={{ fontSize: 12, color: 'var(--muted)', display: 'block', marginTop: 2 }}>
                      {f.description}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Collapsible Details: Spatial regions, limitations, notes */}
        {hasExtra && (
          <>
            {expanded && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 6, paddingTop: 12, borderTop: '1px solid var(--line)' }}>
                {internvl.spatialInterpretation.length > 0 && (
                  <div>
                    <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)' }}>
                      <CompassIcon size={12} style={{ display: 'inline', marginRight: 4 }} />
                      Spatial & Geographic Distribution
                    </span>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 6 }}>
                      {internvl.spatialInterpretation.map((sp, i) => (
                        <div key={i} style={{ fontSize: 12, display: 'flex', gap: 8 }}>
                          <span style={{ color: 'var(--accent-ink)', fontWeight: 600, minWidth: 130 }}>{sp.region}:</span>
                          <span style={{ color: 'var(--text-soft)' }}>{sp.description}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {internvl.limitations && (
                  <div style={{ background: 'rgba(234, 179, 8, 0.06)', border: '1px solid rgba(234, 179, 8, 0.2)', borderRadius: 8, padding: '8px 12px', fontSize: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#eab308', fontWeight: 600, marginBottom: 2 }}>
                      <AlertTriangleIcon size={13} />
                      <span>Resolution & Model Limitations</span>
                    </div>
                    <span style={{ color: 'var(--text-soft)' }}>{internvl.limitations}</span>
                  </div>
                )}

                {internvl.evidenceNote && (
                  <div style={{ fontSize: 11, color: 'var(--faint)', fontStyle: 'italic' }}>
                    Model Evidence Note: {internvl.evidenceNote}
                  </div>
                )}
              </div>
            )}

            <button
              className="btn"
              onClick={() => setExpanded(!expanded)}
              style={{
                alignSelf: 'flex-start',
                padding: '4px 10px',
                fontSize: 11,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                marginTop: 4
              }}
            >
              {expanded ? <ChevronUpIcon size={13} /> : <ChevronDownIcon size={13} />}
              {expanded ? 'Hide Spatial & Diagnostic Details' : 'Show Spatial & Diagnostic Details'}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
