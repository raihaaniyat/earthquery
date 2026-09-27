import React from 'react';
import { TargetIcon, CrosshairIcon } from 'lucide-react';
import type { NormalizedAnalysis } from '../../utils/normalizeAnalysis';

export function OWLv2Card({ owlv2 }: { owlv2?: NormalizedAnalysis['models']['owlv2'] }) {
  if (!owlv2 || !owlv2.available) {
    return (
      <div className="model-card panel" style={{ opacity: 0.65, padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <TargetIcon size={18} color="var(--faint, #746c78)" />
          <b style={{ color: 'var(--text-soft)' }}>OWLv2 GeoGround</b>
          <span className="badge" style={{ fontSize: 10, marginLeft: 'auto' }}>Inactive</span>
        </div>
        <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--muted)' }}>
          Open-vocabulary visual grounding was not engaged for this query pipeline.
        </p>
      </div>
    );
  }

  const objects = owlv2.detectedObjects || [];
  const candidateCount = owlv2.candidateDetectionsCount ?? 0;

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
              background: 'rgba(234, 179, 8, 0.15)',
              display: 'grid',
              placeItems: 'center',
              color: '#facc15'
            }}
          >
            <TargetIcon size={20} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <h4 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: 'var(--text-strong, #f7f2fa)' }}>
                OWLv2 GeoGround
              </h4>
              <span className="badge ok" style={{ fontSize: 10, padding: '2px 6px' }}>
                Object Localization
              </span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted, #a9a0ad)', marginTop: 2 }}>
              {owlv2.role}
            </div>
          </div>
        </div>

        <span
          className="badge"
          style={{
            fontSize: 11,
            padding: '3px 8px',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4
          }}
        >
          <CrosshairIcon size={12} color="var(--accent)" />
          {candidateCount} Spatial Targets
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* Detection Summary Stat */}
        <div style={{ background: 'var(--surface-2)', borderRadius: 8, padding: '10px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)' }}>
              Candidate Spatial Targets Identified
            </span>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-strong)', marginTop: 2 }}>
              {candidateCount > 0 ? `${candidateCount} candidate spatial object locations` : '0 candidate spatial targets'}
            </div>
          </div>
          <span style={{ fontSize: 11, color: 'var(--accent-ink)', fontWeight: 600 }}>
            {candidateCount > 0 ? 'Localized' : 'Negative match'}
          </span>
        </div>

        {/* Specific Object Detections if available */}
        {objects.length > 0 ? (
          <div>
            <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)' }}>
              Detected Visual Entities
            </span>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 8, marginTop: 6 }}>
              {objects.map((obj, i) => (
                <div
                  key={i}
                  style={{
                    background: 'var(--surface-2)',
                    border: '1px solid var(--line)',
                    borderRadius: 8,
                    padding: '8px 12px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                  }}
                >
                  <b style={{ fontSize: 12, color: 'var(--text-strong)' }}>{obj.label}</b>
                  {obj.confidence != null && (
                    <span className="badge ok" style={{ fontSize: 10 }}>
                      {Math.round(obj.confidence * 100)}%
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {/* Grounding Overlay Visualization if present */}
        {owlv2.overlayUrl && (
          <div>
            <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--muted)' }}>
              Bounding Box Spatial Overlay
            </span>
            <div style={{ marginTop: 6, borderRadius: 8, overflow: 'hidden', border: '1px solid var(--line)' }}>
              <img src={owlv2.overlayUrl} alt="OWLv2 Object Grounding" style={{ width: '100%', maxHeight: 240, objectFit: 'contain' }} />
            </div>
          </div>
        )}

        {owlv2.evidenceNote && (
          <div style={{ fontSize: 11, color: 'var(--faint)', fontStyle: 'italic' }}>
            Model Observation: {owlv2.evidenceNote}
          </div>
        )}
      </div>
    </div>
  );
}
