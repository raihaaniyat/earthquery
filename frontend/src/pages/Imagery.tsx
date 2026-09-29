import React, { useRef, useState } from 'react';
import { ScanSearchIcon, ArrowLeftRightIcon, CheckIcon, CircleIcon, LoaderCircleIcon, XIcon, ArrowRightIcon, FileImageIcon, PlusIcon } from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import { useWorkspace } from '../contexts/WorkspaceContext';
import { ImageDropZone } from '../components/ImageDropZone';
import { StateNotice } from '../components/StateNotice';
import { AnalysisResult } from '../components/AnalysisResult';
import { api } from '../utils/api';
import { loadAttachedImage } from '../utils/files';
import { computeDifference, type DiffResult } from '../utils/imageDiff';
import { TASK_LABELS, inferTask } from '../utils/geo';
import type { AnalysisResponse, ModelSettings, RequestState, TaskType } from '../types/app';

export function Imagery() {
  const { modelSettings, updateModelSettings, openDrawer, toast } = useApp();
  const {
    comparisonPair,
    setComparisonPair,
    uploadedImages,
    addUploadedImage,
    addFiles,
    selectImageForComparison,
    buildRequest,
    logResult,
    logHistory
  } = useWorkspace();
  const [query, setQuery] = useState('What changed between these two images?');
  const [threshold, setThreshold] = useState(48);
  const [diff, setDiff] = useState<RequestState<DiffResult>>({ status: 'idle' });
  const [backend, setBackend] = useState<RequestState<AnalysisResponse>>({ status: 'idle' });
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { before, after } = comparisonPair;
  const images = [before, after].filter((x): x is NonNullable<typeof x> => Boolean(x));

  const setSide = async (side: 'before' | 'after', file: File) => {
    const img = await loadAttachedImage(file);
    setComparisonPair({ ...comparisonPair, [side]: img });
    addUploadedImage(img);
    setDiff({ status: 'idle' });
  };

  const runDiff = () => {
    if (!before || !after) return setDiff({ status: 'invalid', message: 'Upload both BEFORE and AFTER images first.' });
    if (!before.image || !after.image)
    return setDiff({ status: 'invalid', message: 'The browser cannot decode one of these files (e.g. GeoTIFF). Use PNG/JPG/WebP, or run Analyze imagery on the backend.' });
    const canvas = canvasRef.current;
    if (!canvas) return;
    try {
      const res = computeDifference(before.image, after.image, canvas, threshold);
      setDiff({ status: 'success', data: res });
      logHistory({
        task: 'change-detection',
        title: 'Pixel difference',
        query: 'Browser-side pixel difference',
        inputs: [before.name, after.name],
        model: 'Client-side pixel difference',
        status: 'local',
        summary: `${res.changedPct.toFixed(2)}% of pixels exceeded the difference threshold (${threshold}).`,
        aoi: null,
        findings: []
      });
      toast('Change mask generated', 'success');
    } catch {
      setDiff({ status: 'error', message: 'Could not read pixel data. Cross-origin images cannot be compared in the browser.' });
    }
  };

  const runBackend = async (kind: 'describe' | 'buildings' | 'analyze') => {
    if (!images.length) return setBackend({ status: 'invalid', message: 'Upload at least one image first.' });
    const inferred = inferTask(query, images.length);
    const isOpticalSarMode =
      modelSettings.comparisonMode === 'optical-sar' ||
      inferred === 'optical-sar' ||
      modelSettings.model === 'CROMA' ||
      modelSettings.model === 'OpticalSAR';

    let task: TaskType =
      kind === 'describe'
        ? 'scene-description'
        : kind === 'buildings'
        ? 'object-detection'
        : isOpticalSarMode
        ? 'optical-sar'
        : modelSettings.comparisonMode === 'single'
        ? inferTask(query, 1)
        : inferred;
    if (task === 'change-detection' && images.length < 2) {
      return setBackend({ status: 'invalid', message: 'Before/after comparison needs both images. Switch Comparison to “Single image” to analyze one.' });
    }
    if (task === 'optical-sar' && images.length < 2) {
      return setBackend({ status: 'invalid', message: 'Optical-SAR fusion requires both an Optical and a SAR image.' });
    }
    if (kind === 'analyze' && task === 'general') task = 'scene-description';
    setBackend({ status: 'loading', message: `Running ${TASK_LABELS[task].toLowerCase()}…` });
    const req = buildRequest(task, query || TASK_LABELS[task], { aoi: null });
    const files = images.map((i) => i.file);
    const res =
      task === 'optical-sar' ?
      await api.analysis(req, files) :
      task === 'change-detection' ?
      await api.changeDetection(req, files) :
      task === 'object-detection' || task === 'segmentation' ?
      await api.prediction(req, files) :
      await api.analysis(req, files);
    setBackend(res);
    logResult(task, query, images.map((i) => i.name), res);
  };

  const identifiedTask =
    modelSettings.comparisonMode === 'optical-sar' ||
    inferTask(query, images.length) === 'optical-sar' ||
    modelSettings.model === 'CROMA' ||
    modelSettings.model === 'OpticalSAR'
      ? 'optical-sar'
      : modelSettings.comparisonMode === 'single'
      ? inferTask(query, 1)
      : inferTask(query, images.length);

  const trace: {label: string;state: 'ok' | 'pending' | 'loading' | 'bad';note: string;}[] = [
  { label: 'Input received', state: images.length ? 'ok' : 'pending', note: `${images.length}/2 images` },
  { label: 'Query understood', state: query.trim() ? 'ok' : 'pending', note: query.trim() ? 'Yes' : 'Empty' },
  { label: 'Task identified', state: query.trim() || modelSettings.comparisonMode === 'optical-sar' ? 'ok' : 'pending', note: TASK_LABELS[identifiedTask] },
  { label: 'Model selected', state: 'ok', note: modelSettings.model },
  {
    label: 'Validation',
    state: backend.status === 'loading' ? 'loading' : backend.status === 'success' ? 'ok' : backend.status === 'idle' ? 'pending' : 'bad',
    note: !modelSettings.validation ? 'Disabled' : backend.status === 'success' ? 'Completed' : backend.status === 'idle' ? 'Waiting' : backend.status === 'loading' ? 'Running' : 'Not completed'
  }];


  return (
    <section className="page">
      <div className="section-head">
        <div>
          <h2>Analysis workspace</h2>
          <p>Manual controls for imagery, routing and specialist models.</p>
        </div>
        <button className="btn" onClick={openDrawer}>Model selector</button>
      </div>

      <div className="page-grid">
        <div className="leftcol">
          {/* Shared Uploaded Imagery Pool */}
          {uploadedImages.length > 0 && (
            <div className="panel panel-pad" style={{ marginBottom: 14 }}>
              <div className="toolbar" style={{ marginBottom: 10 }}>
                <b style={{ fontSize: '13px' }}>Shared Uploaded Imagery</b>
                <span className="badge">{uploadedImages.length} available</span>
                <span className="spacer" />
                <label className="btn small file-btn">
                  <PlusIcon size={12} /> Upload More
                  <input
                    type="file"
                    multiple
                    accept="image/*,.tif,.tiff"
                    onChange={(e) => {
                      if (e.target.files) void addFiles(e.target.files);
                      e.target.value = '';
                    }}
                  />
                </label>
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                  gap: '10px'
                }}
              >
                {uploadedImages.map((img) => {
                  const isA = before?.id === img.id;
                  const isB = after?.id === img.id;
                  const dims = img.width && img.height ? `${img.width} × ${img.height}` : 'Dimensions pending';
                  const bandsText = img.bands ? `${img.bands} band${img.bands === 1 ? '' : 's'}` : (img.type.includes('tiff') ? 'Multispectral GeoTIFF' : 'RGB 3-Band');
                  const crsText = img.crsName || img.crs || (img.isGeoTiff ? 'CRS: Referenced' : null);
                  return (
                    <div
                      key={img.id}
                      style={{
                        background: 'rgba(15, 23, 42, 0.7)',
                        border: isA || isB ? '1px solid var(--accent)' : '1px solid rgba(255, 255, 255, 0.08)',
                        borderRadius: '8px',
                        padding: '10px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '6px',
                        fontSize: '11px',
                        position: 'relative'
                      }}
                    >
                      <div
                        style={{
                          height: '100px',
                          background: 'rgba(0, 0, 0, 0.35)',
                          borderRadius: '6px',
                          overflow: 'hidden',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          position: 'relative'
                        }}
                      >
                        {img.previewable ? (
                          <img
                            src={img.url}
                            alt={img.name}
                            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                            onError={(e) => {
                              (e.target as HTMLElement).style.display = 'none';
                            }}
                          />
                        ) : img.previewStatus === 'loading' ? (
                          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px', color: 'var(--accent)' }}>
                            <LoaderCircleIcon className="spin" size={20} />
                            <span style={{ fontSize: '10px' }}>Generating preview...</span>
                          </div>
                        ) : (
                          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px', opacity: 0.5, textAlign: 'center', padding: '6px' }}>
                            <FileImageIcon size={24} />
                            <span style={{ fontSize: '9px' }}>Preview unavailable</span>
                          </div>
                        )}
                        {img.isGeoTiff && (
                          <span
                            style={{
                              position: 'absolute',
                              top: '4px',
                              left: '4px',
                              background: img.isSar ? 'rgba(168, 85, 247, 0.85)' : 'rgba(14, 165, 233, 0.85)',
                              color: '#fff',
                              fontSize: '9px',
                              fontWeight: 600,
                              padding: '2px 6px',
                              borderRadius: '4px',
                              letterSpacing: '0.3px'
                            }}
                          >
                            {img.isSar ? 'SAR' : 'GeoTIFF'}
                          </span>
                        )}
                      </div>
                      <b style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: 'var(--text)' }} title={img.name}>
                        {img.name}
                      </b>
                      <div style={{ color: '#94a3b8', fontSize: '10px', lineHeight: 1.4 }}>
                        <div>{dims} · {bandsText}</div>
                        {crsText && <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={crsText}>{crsText}</div>}
                      </div>
                      <div style={{ marginTop: 'auto', display: 'flex', gap: '4px', paddingTop: '4px' }}>
                        <button
                          className={`btn small${isA ? ' green' : ''}`}
                          style={{ flex: 1, padding: '3px 4px', fontSize: '10px' }}
                          onClick={() => selectImageForComparison(img, 'before')}
                        >
                          {isA ? '✓ Image A' : 'Set as A'}
                        </button>
                        <button
                          className={`btn small${isB ? ' green' : ''}`}
                          style={{ flex: 1, padding: '3px 4px', fontSize: '10px' }}
                          onClick={() => selectImageForComparison(img, 'after')}
                        >
                          {isB ? '✓ Image B' : 'Set as B'}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div className="panel panel-pad">
            <div className="panel-title">
              Input imagery <span className="badge">Optical / SAR</span>
            </div>
            <div className="upload-grid">
              <ImageDropZone
                label="Image 1 / BEFORE"
                hint="PNG, JPG, WebP or GeoTIFF"
                image={before}
                onFile={(f) => void setSide('before', f)}
                onClear={() => setComparisonPair({ ...comparisonPair, before: null })} />
              
              <ImageDropZone
                label="Image 2 / AFTER"
                hint="Required for change analysis"
                image={after}
                onFile={(f) => void setSide('after', f)}
                onClear={() => setComparisonPair({ ...comparisonPair, after: null })} />
              
            </div>
          </div>

          <div className="panel panel-pad">
            <label className="panel-title" htmlFor="imagery-query">Natural-language query</label>
            <textarea
              id="imagery-query"
              className="field"
              style={{ marginTop: 10 }}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="What would you like to know?" />
            
            <div className="toolbar" style={{ marginTop: 10 }}>
              <button className="btn green small" onClick={runDiff}>
                <ArrowLeftRightIcon size={12} /> Detect changes
              </button>
              <button className="btn small" onClick={() => void runBackend('describe')} disabled={backend.status === 'loading'}>
                <ScanSearchIcon size={12} /> Describe scene
              </button>
              <span className="spacer" />
              <div className="range-row" style={{ minWidth: 200 }}>
                <label htmlFor="threshold">Threshold {threshold}</label>
                <input id="threshold" type="range" min={10} max={120} value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} />
              </div>
            </div>
            <StateNotice state={backend} onRetry={() => void runBackend('analyze')} />
            {backend.status === 'success' &&
            <div style={{ marginTop: 12 }}>
                <AnalysisResult result={backend.data} />
              </div>
            }
          </div>

          <div className="panel panel-pad">
            <div className="panel-title">Result preview</div>
            <canvas ref={canvasRef} className="change-canvas" style={{ display: diff.status === 'success' ? 'block' : 'none' }} aria-label="Change mask" />
            {backend.status === 'success' && backend.data?.maskUrl && (
              <div style={{ marginTop: diff.status === 'success' ? 12 : 0, marginBottom: 12 }}>
                <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--accent)', marginBottom: 6 }}>
                  Spatial Mask (Optical-SAR Consensus / Change Mask)
                </div>
                <div style={{ borderRadius: 6, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.1)', background: '#000', display: 'flex', justifyContent: 'center' }}>
                  <img
                    src={backend.data.maskUrl}
                    alt="Spatial Mask Preview"
                    style={{ maxWidth: '100%', maxHeight: '280px', objectFit: 'contain' }}
                  />
                </div>
              </div>
            )}
            <StateNotice
              state={diff}
              idleText={backend.status === 'success' && backend.data?.maskUrl ? undefined : "No comparison run yet. Upload BEFORE and AFTER images, then run Detect changes for a browser-side pixel difference, or click Analyze imagery."}
              successText={
              diff.status === 'success' ?
              `${diff.data.changedPct.toFixed(2)}% of pixels exceeded the difference threshold (${diff.data.threshold}). This is a visual comparison, not a trained change-detection model.` :
              undefined
              } />
            
          </div>
        </div>

        <aside className="rightcol">
          <div className="panel config">
            <div className="config-row">
              <label className="field-label" htmlFor="routing">Routing</label>
              <select
                id="routing"
                value={modelSettings.routing}
                onChange={(e) => {
                  const routing = e.target.value as ModelSettings['routing'];
                  updateModelSettings(routing === 'auto' ? { routing, model: 'Auto' } : { routing });
                  if (routing === 'manual') openDrawer();
                }}>
                
                <option value="auto">Automatic</option>
                <option value="manual">Manual model</option>
              </select>
            </div>
            <div className="config-row">
              <span className="field-label">Model</span>
              <button className="btn block" style={{ justifyContent: 'space-between' }} onClick={openDrawer}>
                {modelSettings.model === 'Auto' ? 'Auto — choose specialist model' : modelSettings.model}
                <ArrowRightIcon size={13} />
              </button>
            </div>
            <div className="config-row">
              <label className="field-label" htmlFor="validation">Validation</label>
              <select id="validation" value={modelSettings.validation ? 'on' : 'off'} onChange={(e) => updateModelSettings({ validation: e.target.value === 'on' })}>
                <option value="on">Enabled</option>
                <option value="off">Disabled</option>
              </select>
            </div>
            <div className="config-row">
              <label className="field-label" htmlFor="comparison">Comparison</label>
              <select
                id="comparison"
                value={modelSettings.comparisonMode}
                onChange={(e) => updateModelSettings({ comparisonMode: e.target.value as ModelSettings['comparisonMode'] })}>
                
                <option value="before-after">Before / After</option>
                <option value="optical-sar">Optical-SAR Fusion</option>
                <option value="single">Single image</option>
              </select>
            </div>
            <button className="btn primary block" onClick={() => void runBackend('analyze')} disabled={backend.status === 'loading'}>
              Analyze imagery <ArrowRightIcon size={14} />
            </button>
          </div>

          <div className="panel tracebox">
            <h3>Analysis trace</h3>
            {trace.map((s) =>
            <div className="trace-row" key={s.label}>
                {s.state === 'ok' && <CheckIcon size={14} className="ok" />}
                {s.state === 'pending' && <CircleIcon size={14} className="pending" />}
                {s.state === 'loading' && <LoaderCircleIcon size={14} className="spin" />}
                {s.state === 'bad' && <XIcon size={14} className="bad" />}
                {s.label}
                <em>{s.note}</em>
              </div>
            )}
          </div>
        </aside>
      </div>
    </section>);

}