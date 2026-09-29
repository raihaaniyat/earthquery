import React, { useCallback, useEffect, useRef, useState } from 'react';
import { PlusIcon, ArrowLeftRightIcon, FileImageIcon, XIcon } from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import { useWorkspace } from '../contexts/WorkspaceContext';
import { CurtainViewer } from '../components/CurtainViewer';
import { StateNotice } from '../components/StateNotice';
import { loadAttachedImage } from '../utils/files';
import { computeDifference, type DiffResult } from '../utils/imageDiff';
import type { AttachedImage, RequestState } from '../types/app';

type Mode = 'curtain' | 'side' | 'difference' | 'flicker';
const MODES: {id: Mode;label: string;}[] = [
{ id: 'curtain', label: 'Curtain' },
{ id: 'side', label: 'Side-by-side' },
{ id: 'difference', label: 'Difference' },
{ id: 'flicker', label: 'Flicker' }];


export function Comparison() {
  const { toast } = useApp();
  const { comparisonPair, setComparisonPair, pendingDiff, clearPendingDiff, logHistory, addUploadedImage } = useWorkspace();
  const [mode, setMode] = useState<Mode>('curtain');
  const [threshold, setThreshold] = useState(48);
  const [diff, setDiff] = useState<RequestState<DiffResult>>({ status: 'idle' });
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { before, after } = comparisonPair;
  const count = (before ? 1 : 0) + (after ? 1 : 0);

  const runDiff = useCallback(() => {
    setMode('difference');
    if (!before || !after) return setDiff({ status: 'invalid', message: 'Upload two images (A / BEFORE and B / AFTER) first.' });
    if (!before.image || !after.image)
    return setDiff({ status: 'invalid', message: 'The browser cannot decode one of these files (e.g. GeoTIFF). Use PNG, JPG or WebP for browser comparison.' });
    const canvas = canvasRef.current;
    if (!canvas) return;
    try {
      const res = computeDifference(before.image, after.image, canvas, threshold);
      setDiff({ status: 'success', data: res });
      logHistory({
        task: 'change-detection',
        title: 'Pixel difference',
        query: 'Multi-image comparison',
        inputs: [before.name, after.name],
        model: 'Client-side pixel difference',
        status: 'local',
        summary: `${res.changedPct.toFixed(2)}% of pixels exceeded the difference threshold (${threshold}).`,
        aoi: null,
        findings: []
      });
    } catch {
      setDiff({ status: 'error', message: 'Could not read pixel data from these images.' });
    }
  }, [before, after, threshold, logHistory]);

  useEffect(() => {
    if (pendingDiff) {
      clearPendingDiff();
      runDiff();
    }
  }, [pendingDiff, clearPendingDiff, runDiff]);

  const addMany = async (files: FileList) => {
    const list = Array.from(files).slice(0, 2);
    const loaded = await Promise.all(list.map(loadAttachedImage));
    loaded.forEach(addUploadedImage);
    if (loaded.length === 1) setComparisonPair(before ? { before, after: loaded[0] } : { before: loaded[0], after });else
    setComparisonPair({ before: loaded[0], after: loaded[1] });
    setDiff({ status: 'idle' });
    toast('Comparison images loaded', 'success');
  };

  const setSlot = async (side: 'before' | 'after', file: File) => {
    const img = await loadAttachedImage(file);
    addUploadedImage(img);
    setComparisonPair({ ...comparisonPair, [side]: img });
    setDiff({ status: 'idle' });
  };

  const renderSlot = (side: 'before' | 'after', img: AttachedImage | null, title: string) =>
  <div className={`image-tile${img ? ' selected' : ''}`} key={side}>
      <div className="mini">{img?.previewable ? <img src={img.url} alt={title} /> : <FileImageIcon size={18} />}</div>
      <b>{title}</b>
      <small>{img ? img.name : 'No image yet'}</small>
      <div className="toolbar" style={{ marginTop: 6 }}>
        <label className="btn small file-btn">
          {img ? 'Replace' : 'Upload'}
          <input
          type="file"
          accept="image/png,image/jpeg,image/webp,.tif,.tiff"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void setSlot(side, f);
            e.target.value = '';
          }} />
        
        </label>
        {img &&
      <button className="btn small" onClick={() => setComparisonPair({ ...comparisonPair, [side]: null })} aria-label={`Remove ${title}`}>
            <XIcon size={12} />
          </button>
      }
      </div>
    </div>;


  return (
    <section className="page">
      <div className="section-head">
        <div>
          <h2>Multi-image comparison</h2>
          <p>Upload two images and compare them in the browser. The pixel-difference preview runs locally without a backend.</p>
        </div>
        <label className="btn file-btn">
          <PlusIcon size={14} /> Add images
          <input
            type="file"
            multiple
            accept="image/png,image/jpeg,image/webp,.tif,.tiff"
            onChange={(e) => {
              if (e.target.files?.length) void addMany(e.target.files);
              e.target.value = '';
            }} />
          
        </label>
      </div>

      <div className="panel panel-pad">
        <div className="image-strip" style={{ marginTop: 0 }}>
          {renderSlot('before', before, 'Image A / BEFORE')}
          {renderSlot('after', after, 'Image B / AFTER')}
        </div>
      </div>

      <div className="panel panel-pad" style={{ marginTop: 14 }}>
        <div className="toolbar">
          <b>Comparison mode</b>
          <div className="mode-tabs" role="tablist">
            {MODES.map((m) =>
            <button
              key={m.id}
              role="tab"
              aria-selected={mode === m.id}
              className={mode === m.id ? 'active' : ''}
              onClick={() => m.id === 'difference' ? runDiff() : setMode(m.id)}>
              
                {m.label}
              </button>
            )}
          </div>
        </div>

        <div style={{ marginTop: 12, display: mode === 'difference' ? 'none' : 'block' }}>
          <CurtainViewer
            beforeUrl={before?.previewable ? before.url : null}
            afterUrl={after?.previewable ? after.url : null}
            beforeLabel={before?.name ?? 'Image A'}
            afterLabel={after?.name ?? 'Image B'}
            mode={mode === 'difference' ? 'curtain' : mode}
            beforeStatus={before?.previewStatus}
            afterStatus={after?.previewStatus}
            beforeImage={before}
            afterImage={after}
            emptyText="Upload two images to compare (PNG, JPG, WebP or GeoTIFF)."
          />
          
        </div>
        <canvas
          ref={canvasRef}
          className="change-canvas"
          style={{ display: mode === 'difference' && diff.status === 'success' ? 'block' : 'none' }}
          aria-label="Difference mask" />
        

        <div className="toolbar" style={{ marginTop: 12 }}>
          <button className="btn green" onClick={runDiff}>
            <ArrowLeftRightIcon size={14} /> Detect changes
          </button>
          <span className={`badge ${count === 2 ? 'ok' : ''}`}>{count === 2 ? '2 images loaded' : `Waiting for ${2 - count} image${count === 1 ? '' : 's'}`}</span>
          <span className="spacer" />
          <div className="range-row" style={{ minWidth: 220 }}>
            <label htmlFor="cmp-threshold">Threshold {threshold}</label>
            <input id="cmp-threshold" type="range" min={10} max={120} value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} />
          </div>
        </div>
        <StateNotice
          state={diff}
          successText={
          diff.status === 'success' ?
          `Difference mask generated: ${diff.data.changedPct.toFixed(2)}% of pixels exceeded threshold ${diff.data.threshold}. Visual comparison only — not a trained change-detection model.` :
          undefined
          } />
        
      </div>
    </section>);

}