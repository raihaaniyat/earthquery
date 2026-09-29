import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ImageIcon, Loader2Icon, LayersIcon, MapPinIcon, SparklesIcon } from 'lucide-react';
import type { AttachedImage } from '../types/app';
import type { GeoTiffWgs84Bounds } from '../types/geotiff';

export type ViewerMode = 'curtain' | 'fade' | 'side' | 'flicker';

export interface CurtainViewerProps {
  beforeUrl: string | null;
  afterUrl: string | null;
  beforeLabel: string;
  afterLabel: string;
  mode: ViewerMode;
  emptyText?: string;
  height?: number;
  beforeStatus?: 'idle' | 'loading' | 'ready' | 'error';
  afterStatus?: 'idle' | 'loading' | 'ready' | 'error';
  beforeImage?: AttachedImage | null;
  afterImage?: AttachedImage | null;
}

export function CurtainViewer({
  beforeUrl,
  afterUrl,
  beforeLabel,
  afterLabel,
  mode,
  emptyText,
  height,
  beforeStatus,
  afterStatus,
  beforeImage,
  afterImage
}: CurtainViewerProps) {
  const [pos, setPos] = useState(50);
  const [flickerAfter, setFlickerAfter] = useState(false);
  const [alignOverlap, setAlignOverlap] = useState(true);
  const ref = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  useEffect(() => {
    if (mode !== 'flicker') return;
    const t = window.setInterval(() => setFlickerAfter((f) => !f), 700);
    return () => window.clearInterval(t);
  }, [mode]);

  const isLoading = beforeStatus === 'loading' || afterStatus === 'loading';
  const hasBefore = Boolean(beforeUrl);
  const hasAfter = Boolean(afterUrl);
  const ready = Boolean(beforeUrl && afterUrl && !isLoading);
  const style = height ? { height } : undefined;

  // Compute common overlapping geospatial extent if both images have WGS84 bounds
  const boundsA = beforeImage?.wgs84Bounds || (beforeImage?.metadata?.wgs84Bounds);
  const boundsB = afterImage?.wgs84Bounds || (afterImage?.metadata?.wgs84Bounds);

  const overlapInfo = useMemo(() => {
    if (!boundsA || !boundsB) return null;
    const minLon = Math.max(boundsA.minLon, boundsB.minLon);
    const maxLon = Math.min(boundsA.maxLon, boundsB.maxLon);
    const minLat = Math.max(boundsA.minLat, boundsB.minLat);
    const maxLat = Math.min(boundsA.maxLat, boundsB.maxLat);

    if (minLon < maxLon && minLat < maxLat) {
      const spanLonA = boundsA.maxLon - boundsA.minLon;
      const spanLatA = boundsA.maxLat - boundsA.minLat;
      const spanLonB = boundsB.maxLon - boundsB.minLon;
      const spanLatB = boundsB.maxLat - boundsB.minLat;

      return {
        hasOverlap: true,
        minLon,
        maxLon,
        minLat,
        maxLat,
        // Relative sub-rect within Image A [0..1]
        a: {
          left: spanLonA > 0 ? (minLon - boundsA.minLon) / spanLonA : 0,
          right: spanLonA > 0 ? (boundsA.maxLon - maxLon) / spanLonA : 0,
          top: spanLatA > 0 ? (boundsA.maxLat - maxLat) / spanLatA : 0,
          bottom: spanLatA > 0 ? (minLat - boundsA.minLat) / spanLatA : 0
        },
        // Relative sub-rect within Image B [0..1]
        b: {
          left: spanLonB > 0 ? (minLon - boundsB.minLon) / spanLonB : 0,
          right: spanLonB > 0 ? (boundsB.maxLon - maxLon) / spanLonB : 0,
          top: spanLatB > 0 ? (boundsB.maxLat - maxLat) / spanLatB : 0,
          bottom: spanLatB > 0 ? (minLat - boundsB.minLat) / spanLatB : 0
        }
      };
    }
    return { hasOverlap: false, minLon, maxLon, minLat, maxLat };
  }, [boundsA, boundsB]);

  // Loading state
  if (isLoading) {
    return (
      <div className="curtain" style={style}>
        <div className="curtain-empty">
          <Loader2Icon className="spin" size={28} style={{ color: 'var(--accent)' }} />
          <b style={{ color: 'var(--text)' }}>Preparing comparison previews...</b>
          <span style={{ fontSize: '12px' }}>Decoding rasters and calculating common spatial extents...</span>
        </div>
      </div>
    );
  }

  // Not ready / Empty states
  if (!ready) {
    let msg = emptyText || 'Select two images to enable temporal comparison.';
    if (!hasBefore && !hasAfter) {
      msg = 'No temporal imagery selected. Select two compatible images to compare.';
    } else if (hasBefore && !hasAfter) {
      msg = 'Select a second image (AFTER / T2) to enable temporal curtain comparison.';
    } else if (!hasBefore && hasAfter) {
      msg = 'Select a first image (BEFORE / T1) to enable temporal curtain comparison.';
    } else if (beforeStatus === 'error' || afterStatus === 'error') {
      msg = 'Preview unavailable for one of the selected rasters. Original GeoTIFF is retained for AI analysis.';
    }

    return (
      <div className="curtain" style={style}>
        <div className="curtain-empty">
          <ImageIcon size={28} style={{ opacity: 0.5 }} />
          <span>{msg}</span>
        </div>
      </div>
    );
  }

  const setFromPointer = (clientX: number) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return;
    setPos(Math.min(100, Math.max(0, ((clientX - r.left) / r.width) * 100)));
  };

  const isFade = mode === 'fade';

  // Sub-extent clipping style for geospatial alignment
  const getLayerStyle = (isLayerB: boolean) => {
    const base: React.CSSProperties = {
      position: 'absolute',
      inset: 0,
      width: '100%',
      height: '100%',
      objectFit: 'contain',
      pointerEvents: 'none'
    };

    if (isLayerB) {
      if (isFade) {
        base.opacity = pos / 100;
      } else {
        base.clipPath = `inset(0 0 0 ${pos}%)`;
      }
    }

    return base;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {/* Geospatial Alignment & Metadata Header Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '8px',
          fontSize: '11px',
          padding: '4px 8px',
          background: 'rgba(15, 23, 42, 0.65)',
          borderRadius: '6px',
          border: '1px solid rgba(255, 255, 255, 0.06)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {overlapInfo?.hasOverlap ? (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                color: 'var(--ok)',
                fontWeight: 600
              }}
            >
              <MapPinIcon size={12} /> Geospatially Aligned Overlap
            </span>
          ) : (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#94a3b8' }}>
              <LayersIcon size={12} /> Normalized Scene Comparison
            </span>
          )}

          {beforeImage?.crsName && (
            <span className="badge" style={{ fontSize: '10px' }}>
              A: {beforeImage.crsName}
            </span>
          )}
          {afterImage?.crsName && afterImage.crsName !== beforeImage?.crsName && (
            <span className="badge" style={{ fontSize: '10px' }}>
              B: {afterImage.crsName}
            </span>
          )}
        </div>

        {/* Preset Split Jump Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ color: '#94a3b8', marginRight: '4px' }}>Curtain:</span>
          {[
            { label: '100% A', val: 100 },
            { label: '75%', val: 75 },
            { label: '50% Split', val: 50 },
            { label: '25%', val: 25 },
            { label: '100% B', val: 0 }
          ].map((btn) => (
            <button
              key={btn.label}
              className={`btn small${pos === btn.val ? ' green' : ''}`}
              style={{ padding: '1px 6px', fontSize: '10px', minHeight: '22px' }}
              onClick={() => setPos(btn.val)}
            >
              {btn.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Interactive Curtain Area */}
      {mode === 'side' ? (
        <div className="curtain" style={style}>
          <div className="side-by-side">
            <div style={{ position: 'relative', overflow: 'hidden' }}>
              <img
                className="layer-img"
                src={beforeUrl as string}
                alt={`Before: ${beforeLabel}`}
                style={{ objectFit: 'contain' }}
              />
              <span className="view-tag left">BEFORE · {beforeLabel}</span>
            </div>
            <div style={{ position: 'relative', overflow: 'hidden' }}>
              <img
                className="layer-img"
                src={afterUrl as string}
                alt={`After: ${afterLabel}`}
                style={{ objectFit: 'contain' }}
              />
              <span className="view-tag left">AFTER · {afterLabel}</span>
            </div>
          </div>
        </div>
      ) : mode === 'flicker' ? (
        <div className="curtain" style={style}>
          <img
            className="layer-img"
            src={beforeUrl as string}
            alt={`Before: ${beforeLabel}`}
            style={{ objectFit: 'contain' }}
          />
          <img
            className="layer-img"
            src={afterUrl as string}
            alt={`After: ${afterLabel}`}
            style={{ opacity: flickerAfter ? 1 : 0, objectFit: 'contain' }}
          />
          <span className="view-tag left">
            {flickerAfter ? `AFTER · ${afterLabel}` : `BEFORE · ${beforeLabel}`}
          </span>
        </div>
      ) : (
        <div
          ref={ref}
          className="curtain"
          style={{ ...style, cursor: isFade ? 'default' : 'ew-resize' }}
          onPointerDown={(e) => {
            if (isFade || (e.target as HTMLElement).tagName === 'INPUT') return;
            dragging.current = true;
            (e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId);
            setFromPointer(e.clientX);
          }}
          onPointerMove={(e) => dragging.current && setFromPointer(e.clientX)}
          onPointerUp={() => (dragging.current = false)}
          onPointerCancel={() => (dragging.current = false)}
        >
          {/* Base Layer: Image A (Before) */}
          <img
            className="layer-img"
            src={beforeUrl as string}
            alt={`Before: ${beforeLabel}`}
            style={getLayerStyle(false)}
          />

          {/* Overlay Layer: Image B (After), clipped by pos */}
          <img
            className="layer-img"
            src={afterUrl as string}
            alt={`After: ${afterLabel}`}
            style={getLayerStyle(true)}
          />

          {/* Tags */}
          <span className="view-tag left">
            BEFORE (T1) · {beforeLabel}
            {beforeImage?.isSar ? ' [SAR]' : ''}
          </span>
          <span className="view-tag right">
            AFTER (T2) · {afterLabel}
            {afterImage?.isSar ? ' [SAR]' : ''}
          </span>

          {/* Vertical Split Line and Handle */}
          {!isFade && (
            <>
              <div className="curtain-line" style={{ left: `${pos}%` }} />
              <div className="curtain-handle" style={{ left: `${pos}%` }} aria-hidden="true">
                ↔
              </div>
            </>
          )}

          {/* Range Slider for Touch / Fine adjustment */}
          <div className="curtain-range">
            <input
              type="range"
              min={0}
              max={100}
              value={pos}
              onChange={(e) => setPos(Number(e.target.value))}
              aria-label={isFade ? 'After image opacity' : 'Curtain split position'}
            />
          </div>
        </div>
      )}
    </div>
  );
}