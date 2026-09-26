import React, { useEffect, useRef, useState } from 'react';
import { ImageIcon } from 'lucide-react';

export type ViewerMode = 'curtain' | 'fade' | 'side' | 'flicker';

interface CurtainViewerProps {
  beforeUrl: string | null;
  afterUrl: string | null;
  beforeLabel: string;
  afterLabel: string;
  mode: ViewerMode;
  emptyText: string;
  height?: number;
}

export function CurtainViewer({ beforeUrl, afterUrl, beforeLabel, afterLabel, mode, emptyText, height }: CurtainViewerProps) {
  const [pos, setPos] = useState(50);
  const [flickerAfter, setFlickerAfter] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  useEffect(() => {
    if (mode !== 'flicker') return;
    const t = window.setInterval(() => setFlickerAfter((f) => !f), 700);
    return () => window.clearInterval(t);
  }, [mode]);

  const ready = Boolean(beforeUrl && afterUrl);
  const style = height ? { height } : undefined;

  if (!ready) {
    return (
      <div className="curtain" style={style}>
        <div className="curtain-empty">
          <ImageIcon size={22} />
          <span>{emptyText}</span>
        </div>
      </div>);

  }

  const setFromPointer = (clientX: number) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return;
    setPos(Math.min(100, Math.max(0, (clientX - r.left) / r.width * 100)));
  };

  if (mode === 'side') {
    return (
      <div className="curtain" style={style}>
        <div className="side-by-side">
          <div>
            <img className="layer-img" src={beforeUrl as string} alt={`Before: ${beforeLabel}`} />
            <span className="view-tag left">BEFORE · {beforeLabel}</span>
          </div>
          <div>
            <img className="layer-img" src={afterUrl as string} alt={`After: ${afterLabel}`} />
            <span className="view-tag left">AFTER · {afterLabel}</span>
          </div>
        </div>
      </div>);

  }

  if (mode === 'flicker') {
    return (
      <div className="curtain" style={style}>
        <img className="layer-img" src={beforeUrl as string} alt={`Before: ${beforeLabel}`} />
        <img
          className="layer-img"
          src={afterUrl as string}
          alt={`After: ${afterLabel}`}
          style={{ opacity: flickerAfter ? 1 : 0 }} />
        
        <span className="view-tag left">{flickerAfter ? `AFTER · ${afterLabel}` : `BEFORE · ${beforeLabel}`}</span>
      </div>);

  }

  const isFade = mode === 'fade';
  return (
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
      onPointerUp={() => dragging.current = false}
      onPointerCancel={() => dragging.current = false}>
      
      <img className="layer-img" src={beforeUrl as string} alt={`Before: ${beforeLabel}`} />
      <img
        className="layer-img"
        src={afterUrl as string}
        alt={`After: ${afterLabel}`}
        style={isFade ? { opacity: pos / 100 } : { clipPath: `inset(0 0 0 ${pos}%)` }} />
      
      <span className="view-tag left">BEFORE · {beforeLabel}</span>
      <span className="view-tag right">AFTER · {afterLabel}</span>
      {!isFade &&
      <>
          <div className="curtain-line" style={{ left: `${pos}%` }} />
          <div className="curtain-handle" style={{ left: `${pos}%` }} aria-hidden="true">↔</div>
        </>
      }
      <div className="curtain-range">
        <input
          type="range"
          min={0}
          max={100}
          value={pos}
          onChange={(e) => setPos(Number(e.target.value))}
          aria-label={isFade ? 'After image opacity' : 'Curtain position'} />
        
      </div>
    </div>);

}