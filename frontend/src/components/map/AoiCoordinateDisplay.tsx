import React from 'react';
import { XIcon } from 'lucide-react';
import type { Aoi } from '../../types/app';

interface AoiCoordinateDisplayProps {
  aoi: Aoi | null;
  onClear?: () => void;
}

export function AoiCoordinateDisplay({ aoi, onClear }: AoiCoordinateDisplayProps) {
  if (!aoi) return null;

  const isPoint = aoi.type === 'point';
  const [lat, lng] = aoi.centroid;
  // BBox is [west, south, east, north]
  const [west, south, east, north] = aoi.bbox;

  return (
    <div
      className="aoi-coordinate-overlay"
      style={{
        position: 'absolute',
        bottom: 24,
        right: 12,
        zIndex: 500,
        background: 'rgba(15, 23, 42, 0.88)',
        backdropFilter: 'blur(8px)',
        border: '1px solid rgba(255, 255, 255, 0.15)',
        borderRadius: '8px',
        padding: '8px 12px',
        fontSize: '11px',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
        color: '#e2e8f0',
        boxShadow: '0 4px 16px rgba(0, 0, 0, 0.45)',
        pointerEvents: 'auto',
        minWidth: '150px'
      }}
      aria-label="Selected AOI Coordinates"
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '3px' }}>
        <b style={{ color: 'var(--accent, #a56cff)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          {isPoint ? 'AOI' : 'AOI Bounds'}
        </b>
        {onClear && (
          <button
            onClick={onClear}
            className="btn small danger-text"
            style={{ padding: '1px 5px', fontSize: '10px', height: 'auto', lineHeight: '1.2' }}
            title="Clear AOI"
          >
            <XIcon size={10} style={{ marginRight: '2px' }} /> Clear
          </button>
        )}
      </div>

      {isPoint ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#94a3b8' }}>Lat:</span>
            <b>{lat.toFixed(4)}</b>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#94a3b8' }}>Lng:</span>
            <b>{lng.toFixed(4)}</b>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#94a3b8' }}>North:</span>
            <b>{north.toFixed(4)}°</b>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#94a3b8' }}>South:</span>
            <b>{south.toFixed(4)}°</b>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#94a3b8' }}>East:</span>
            <b>{east.toFixed(4)}°</b>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#94a3b8' }}>West:</span>
            <b>{west.toFixed(4)}°</b>
          </div>
        </div>
      )}
    </div>
  );
}
