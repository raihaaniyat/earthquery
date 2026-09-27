import React from 'react';
import { RulerIcon, CheckCircle2Icon, CompassIcon, BarChart2Icon, ActivityIcon } from 'lucide-react';
import type { NormalizedAnalysis } from '../../utils/normalizeAnalysis';

export function RasterAnalysisCard({ raster }: { raster: NormalizedAnalysis['raster'] }) {
  if (!raster.available) {
    return (
      <div className="model-card panel" style={{ opacity: 0.65, padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <RulerIcon size={18} color="var(--faint, #746c78)" />
          <b style={{ color: 'var(--text-soft)' }}>Deterministic Raster Analysis</b>
          <span className="badge" style={{ fontSize: 10, marginLeft: 'auto' }}>Standard RGB Mode</span>
        </div>
        <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--muted)' }}>
          Non-georeferenced benchmark image operated strictly in pixel coordinate space.
        </p>
      </div>
    );
  }

  const radio = raster.radiometry;

  return (
    <div
      className="model-card"
      style={{
        background: 'var(--panel-solid, #131017)',
        border: '1px solid rgba(69, 212, 131, 0.25)',
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
              background: 'rgba(69, 212, 131, 0.15)',
              display: 'grid',
              placeItems: 'center',
              color: '#45d483'
            }}
          >
            <RulerIcon size={20} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <h4 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: 'var(--text-strong, #f7f2fa)' }}>
                Deterministic Raster Analysis
              </h4>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 800,
                  letterSpacing: '0.06em',
                  textTransform: 'uppercase',
                  padding: '2px 7px',
                  borderRadius: 4,
                  background: 'rgba(69, 212, 131, 0.2)',
                  color: '#45d483',
                  border: '1px solid rgba(69, 212, 131, 0.4)'
                }}
              >
                Deterministic
              </span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted, #a9a0ad)', marginTop: 2 }}>
              Direct scientific measurements computed from raster data without neural inference
            </div>
          </div>
        </div>

        <span
          className="badge ok"
          style={{
            fontSize: 11,
            padding: '3px 8px',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4
          }}
        >
          <CheckCircle2Icon size={12} />
          {raster.status}
        </span>
      </div>

      {/* Grid of Geodetic & Radiometric metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
        {raster.crs && (
          <div style={{ background: 'var(--surface-2)', borderRadius: 8, padding: '10px 12px' }}>
            <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <CompassIcon size={11} /> Coordinate Reference System
            </span>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-strong)', marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>
              {raster.crs}
            </div>
          </div>
        )}

        {raster.resolutionM != null && (
          <div style={{ background: 'var(--surface-2)', borderRadius: 8, padding: '10px 12px' }}>
            <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <RulerIcon size={11} /> Ground Resolution
            </span>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-strong)', marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>
              {raster.resolutionM} m / pixel
            </div>
          </div>
        )}

        {raster.footprintKm2 != null && (
          <div style={{ background: 'var(--surface-2)', borderRadius: 8, padding: '10px 12px' }}>
            <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <CompassIcon size={11} /> Scene Footprint
            </span>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-strong)', marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>
              {raster.footprintKm2} km²
            </div>
          </div>
        )}

        {radio && (
          <div style={{ background: 'var(--surface-2)', borderRadius: 8, padding: '10px 12px' }}>
            <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <BarChart2Icon size={11} /> Radiometric DN Mean
            </span>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-strong)', marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>
              {radio.mean} <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--muted)' }}>[{radio.min} - {radio.max}]</span>
            </div>
          </div>
        )}

        {radio?.validPixelPct != null && (
          <div style={{ background: 'var(--surface-2)', borderRadius: 8, padding: '10px 12px' }}>
            <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)' }}>
              Valid Pixel Ratio
            </span>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#45d483', marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>
              {radio.validPixelPct}%
            </div>
          </div>
        )}

        {raster.ndvi != null && (
          <div style={{ background: 'var(--surface-2)', borderRadius: 8, padding: '10px 12px' }}>
            <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <ActivityIcon size={11} /> NDVI Mean
            </span>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-strong)', marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>
              {raster.ndvi} {raster.ndviThresholdPct != null && <span style={{ fontSize: 11, color: 'var(--muted)' }}>({raster.ndviThresholdPct}% exceed)</span>}
            </div>
          </div>
        )}
      </div>

      {raster.rawItems.length > 0 && (
        <div style={{ marginTop: 10, fontSize: 11, color: 'var(--muted)' }}>
          {raster.rawItems.map((item, i) => (
            <div key={i} style={{ marginTop: 2 }}>• {item}</div>
          ))}
        </div>
      )}
    </div>
  );
}
