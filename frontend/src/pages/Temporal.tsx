import React, { useEffect, useMemo, useState } from 'react';
import { PlusIcon, SatelliteIcon, ArrowLeftRightIcon, XIcon, ArrowRightIcon, ChartLineIcon } from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import { useWorkspace } from '../contexts/WorkspaceContext';
import { CurtainViewer, type ViewerMode } from '../components/CurtainViewer';
import { StateNotice } from '../components/StateNotice';
import { AnalysisResult } from '../components/AnalysisResult';
import { SafeThumb } from '../components/SafeThumb';
import { GreennessChart } from '../components/GreennessChart';
import { STAC_COLLECTIONS } from '../data/apiConfig';
import { api, searchStac } from '../utils/api';
import { computeGreenness } from '../utils/imageDiff';
import type { AnalysisResponse, RequestState, StacScene } from '../types/app';

interface TemporalItem {
  id: string;
  label: string;
  sub: string;
  url: string | null;
  source: 'local' | 'stac';
  localIndex: number | null;
  date: string | null;
}

const FUNCTIONS = [
{ id: 'timeline', label: 'Change timeline' },
{ id: 'trend', label: 'Trend' },
{ id: 'seasonal', label: 'Seasonal' },
{ id: 'events', label: 'Event detection' }];


const MODES: {id: ViewerMode;label: string;}[] = [
{ id: 'curtain', label: 'Curtain' },
{ id: 'fade', label: 'Swipe' },
{ id: 'side', label: 'Grid' }];


export function Temporal() {
  const { navigate, toast } = useApp();
  const { temporalImages, addTemporalFiles, removeTemporalImage, aoi, imagery, buildRequest, logResult, setComparisonPair } = useWorkspace();
  const [scenes, setScenes] = useState<StacScene[]>([]);
  const [sceneState, setSceneState] = useState<RequestState<StacScene[]>>({ status: 'idle' });
  const [beforeId, setBeforeId] = useState<string | null>(null);
  const [afterId, setAfterId] = useState<string | null>(null);
  const [mode, setMode] = useState<ViewerMode>('curtain');
  const [run, setRun] = useState<RequestState<AnalysisResponse>>({ status: 'idle' });
  const [activeFn, setActiveFn] = useState('timeline');

  const items: TemporalItem[] = useMemo(
    () => [
    ...temporalImages.map((img, i) => ({
      id: img.id,
      label: `Image ${String.fromCharCode(65 + i % 26)}`,
      sub: img.name,
      url: img.previewable ? img.url : null,
      source: 'local' as const,
      localIndex: i,
      date: null
    })),
    ...scenes.map((s) => ({
      id: s.id,
      label: s.datetime.slice(0, 10),
      sub: `Sentinel-2${s.cloudCover != null ? ` · cloud ${s.cloudCover.toFixed(0)}%` : ''}`,
      url: s.thumbnail,
      source: 'stac' as const,
      localIndex: null,
      date: s.datetime.slice(0, 10)
    }))],

    [temporalImages, scenes]
  );

  useEffect(() => {
    if (!items.length) {
      setBeforeId(null);
      setAfterId(null);
      return;
    }
    if (!beforeId || !items.some((i) => i.id === beforeId)) setBeforeId(items[0].id);
    if (!afterId || !items.some((i) => i.id === afterId)) setAfterId(items[items.length - 1].id);
  }, [items, beforeId, afterId]);

  const greenness = useMemo(
    () =>
    temporalImages.
    map((img, i) => ({ label: `Image ${String.fromCharCode(65 + i % 26)}`, value: img.image ? computeGreenness(img.image) : null })).
    filter((p): p is {label: string;value: number;} => p.value !== null),
    [temporalImages]
  );

  const before = items.find((i) => i.id === beforeId) ?? null;
  const after = items.find((i) => i.id === afterId) ?? null;
  const pairs = items.length * (items.length - 1) / 2;
  const dated = items.filter((i) => i.date).map((i) => i.date as string).sort();

  const loadScenes = async () => {
    if (!aoi) return setSceneState({ status: 'invalid', message: 'Select an AOI on the Map & AOI page to load Sentinel-2 scenes for that area.' });
    setSceneState({ status: 'loading' });
    const res = await searchStac({
      collection: STAC_COLLECTIONS.optical,
      bbox: aoi.bbox,
      start: imagery.startDate,
      end: imagery.endDate,
      maxCloud: 40,
      limit: 12
    });
    setSceneState(res);
    setScenes(res.status === 'success' ? [...res.data].sort((a, b) => a.datetime.localeCompare(b.datetime)) : []);
  };

  const runTemporal = async (fn: string) => {
    setActiveFn(fn);
    if (items.length < 2 && !aoi) return setRun({ status: 'invalid', message: 'Add at least two images or select an AOI to run temporal analysis.' });
    const label = FUNCTIONS.find((f) => f.id === fn)?.label ?? fn;
    setRun({ status: 'loading', message: `Running ${label.toLowerCase()}…` });
    const req = buildRequest('temporal', `Temporal ${label.toLowerCase()}`, { mode: fn, comparisonMode: 'multi-date' });
    const res = await api.analysis(req, temporalImages.map((i) => i.file));
    setRun(res);
    logResult('temporal', `Temporal ${label.toLowerCase()}`, items.map((i) => i.sub), res);
  };

  const swap = () => {
    setBeforeId(afterId);
    setAfterId(beforeId);
    toast('Temporal pair swapped');
  };

  const sendToDifference = () => {
    const b = before?.localIndex != null ? temporalImages[before.localIndex] : null;
    const a = after?.localIndex != null ? temporalImages[after.localIndex] : null;
    if (!b || !a || b.id === a.id) return toast('Choose two different uploaded images for a difference mask', 'error');
    setComparisonPair({ before: b, after: a }, true);
    navigate('comparison');
  };

  return (
    <section className="page">
      <div className="section-head">
        <div>
          <h2>Temporal analysis</h2>
          <p>Work with multiple dated images, compare any pair, scrub the timeline, and run time-series analysis.</p>
        </div>
        <button className="btn green" onClick={() => void runTemporal('timeline')} disabled={run.status === 'loading'}>
          Run temporal analysis <ArrowRightIcon size={14} />
        </button>
      </div>

      <div className="panel panel-pad" style={{ marginBottom: 14 }}>
        <div className="toolbar">
          <b>Image collection</b>
          <span className="badge">{items.length} image{items.length === 1 ? '' : 's'}</span>
          <span className="spacer" />
          <button className="btn small" onClick={() => void loadScenes()} disabled={sceneState.status === 'loading'}>
            <SatelliteIcon size={12} /> Load Sentinel-2 scenes for AOI
          </button>
          <label className="btn small file-btn">
            <PlusIcon size={12} /> Add images
            <input
              type="file"
              multiple
              accept="image/png,image/jpeg,image/webp,.tif,.tiff"
              onChange={(e) => {
                if (e.target.files?.length) void addTemporalFiles(e.target.files);
                e.target.value = '';
              }} />
            
          </label>
        </div>
        <StateNotice
          state={sceneState}
          loadingText="Searching Copernicus STAC for Sentinel-2 scenes…"
          successText={`${scenes.length} Sentinel-2 scenes added from ${imagery.startDate} to ${imagery.endDate}.`}
          onRetry={() => void loadScenes()} />
        
        <div className="image-strip">
          {items.map((it) =>
          <div key={it.id} className={`image-tile${it.id === beforeId || it.id === afterId ? ' selected' : ''}`}>
              <div className="mini">
                <SafeThumb src={it.url} alt={it.sub} />
              </div>
              <b>{it.label}</b>
              <small>{it.sub}</small>
              {it.source === 'local' &&
            <button className="tile-remove" onClick={() => removeTemporalImage(it.id)} aria-label={`Remove ${it.sub}`}>
                  <XIcon size={12} />
                </button>
            }
            </div>
          )}
          <label className="image-tile add-tile">
            <PlusIcon size={18} />
            <small>Add dated images</small>
            <input
              type="file"
              multiple
              hidden
              accept="image/png,image/jpeg,image/webp,.tif,.tiff"
              onChange={(e) => {
                if (e.target.files?.length) void addTemporalFiles(e.target.files);
                e.target.value = '';
              }} />
            
          </label>
        </div>
      </div>

      <div className="result-grid">
        <div className="panel panel-pad">
          <div className="toolbar">
            <b>Multi-date comparison</b>
            <span className="spacer" />
            <div className="mode-tabs" role="tablist">
              {MODES.map((m) =>
              <button key={m.id} role="tab" aria-selected={mode === m.id} className={mode === m.id ? 'active' : ''} onClick={() => setMode(m.id)}>
                  {m.label}
                </button>
              )}
            </div>
          </div>
          <div style={{ marginTop: 12 }}>
            <CurtainViewer
              beforeUrl={before?.url ?? null}
              afterUrl={after?.url ?? null}
              beforeLabel={before?.label ?? ''}
              afterLabel={after?.label ?? ''}
              mode={mode}
              emptyText={items.length < 2 ? 'Add at least two images or load Sentinel-2 scenes to compare dates.' : 'A preview is not available for one of the selected items.'} />
            
          </div>
          <div className="image-compare-toolbar">
            <label className="range-row">
              Before
              <select value={beforeId ?? ''} onChange={(e) => setBeforeId(e.target.value)} disabled={!items.length}>
                {items.map((i) => <option key={i.id} value={i.id}>{i.label} · {i.sub}</option>)}
              </select>
            </label>
            <label className="range-row">
              After
              <select value={afterId ?? ''} onChange={(e) => setAfterId(e.target.value)} disabled={!items.length}>
                {items.map((i) => <option key={i.id} value={i.id}>{i.label} · {i.sub}</option>)}
              </select>
            </label>
            <button className="btn small" onClick={swap} disabled={items.length < 2}>
              <ArrowLeftRightIcon size={12} /> Swap pair
            </button>
            <button className="btn small" onClick={sendToDifference} disabled={temporalImages.length < 2}>
              Generate difference mask
            </button>
          </div>
        </div>

        <div className="panel panel-pad">
          <b>Temporal functions</b>
          <div className="toolbar" style={{ marginTop: 10 }}>
            {FUNCTIONS.map((f) =>
            <button
              key={f.id}
              className={`btn${activeFn === f.id ? ' green' : ''}`}
              onClick={() => void runTemporal(f.id)}
              disabled={run.status === 'loading'}>
              
                {f.label}
              </button>
            )}
          </div>
          <StateNotice state={run} onRetry={() => void runTemporal(activeFn)} />
          {run.status === 'success' && <AnalysisResult result={run.data} title="Temporal result" />}
          <div className="finding">
            <b>Pairwise comparison</b>
            <br />
            <span className="muted">{items.length >= 2 ? `${pairs} possible image pairs from ${items.length} images` : 'Add two or more images to compare pairs'}</span>
          </div>
          <div className="finding">
            <b>Date coverage</b>
            <br />
            <span className="muted">
              {dated.length ? `${dated[0]} → ${dated[dated.length - 1]} · ${dated.length} dated scenes` : 'Acquisition dates are only known for Sentinel scenes loaded from STAC'}
            </span>
          </div>
          <div className="finding">
            <b>Time-series index</b>
            <br />
            <span className="muted">
              {greenness.length ? `RGB greenness computed for ${greenness.length} uploaded image${greenness.length > 1 ? 's' : ''}` : 'NDVI / NDWI / NDBI need multispectral bands via the backend'}
            </span>
          </div>
        </div>
      </div>

      <div className="panel panel-pad" style={{ marginTop: 14 }}>
        <div className="toolbar">
          <b>Temporal trend</b>
          <span className="badge">Excess Green (RGB proxy, not NDVI)</span>
        </div>
        <div className="chart">
          {greenness.length >= 2 ?
          <GreennessChart points={greenness} /> :

          <div className="empty-state" style={{ padding: 32 }}>
              <div className="empty-icon"><ChartLineIcon size={20} /></div>
              <p>Upload two or more browser-readable images to plot a greenness trend computed from their pixels.</p>
            </div>
          }
        </div>
      </div>
    </section>);

}