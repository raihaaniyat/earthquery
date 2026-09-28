import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  MousePointer2Icon,
  SquareIcon,
  PentagonIcon,
  CircleDotIcon,
  RulerIcon,
  PlusIcon,
  MinusIcon,
  LocateFixedIcon,
  MaximizeIcon,
  MinimizeIcon,
  SearchIcon,
  CheckIcon,
  XIcon,
  LayersIcon
} from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import { useWorkspace } from '../contexts/WorkspaceContext';
import { useSatelliteMap } from '../hooks/useSatelliteMap';
import { useMapDrawing } from '../hooks/useMapDrawing';
import { ImageryControls } from '../components/map/ImageryControls';
import { MapLayersPanel } from '../components/map/MapLayersPanel';
import { AoiPanel } from '../components/map/AoiPanel';
import { BASEMAPS, STAC_COLLECTIONS } from '../data/apiConfig';
import { searchStac } from '../utils/api';
import { describeAoi, formatDistance, formatLatLng } from '../utils/geo';
import type { LatLngTuple, MapTool, RequestState, StacScene } from '../types/app';

const TOOLS: {id: MapTool;label: string;icon: typeof SquareIcon;}[] = [
{ id: 'select', label: 'Select', icon: MousePointer2Icon },
{ id: 'rectangle', label: 'Rectangle', icon: SquareIcon },
{ id: 'polygon', label: 'Polygon', icon: PentagonIcon },
{ id: 'point', label: 'Point', icon: CircleDotIcon },
{ id: 'measure', label: 'Measure', icon: RulerIcon }];


export function MapAoi() {
  const { toast } = useApp();
  const {
    imagery,
    updateImagery,
    aoi,
    setAoi,
    mapTool,
    setMapTool,
    startAnalysis,
    setQuery,
    latestMapAction,
    setLatestMapAction
  } = useWorkspace();
  const containerRef = useRef<HTMLDivElement>(null);
  const [scenes, setScenes] = useState<StacScene[]>([]);
  const [sceneState, setSceneState] = useState<RequestState<StacScene[]>>({ status: 'idle' });
  const [collection, setCollection] = useState<'optical' | 'sar'>('optical');
  const [maxCloud, setMaxCloud] = useState(40);
  const [focusedScene, setFocusedScene] = useState<string | null>(null);
  const [comparePos, setComparePos] = useState(50);
  const [fullscreen, setFullscreen] = useState(false);
  const [inspect, setInspect] = useState<LatLngTuple | null>(null);
  const [question, setQuestion] = useState('What changed inside this selected area?');

  const sat = useSatelliteMap(containerRef, { imagery, aoi, scenes, focusedSceneId: focusedScene, comparePos });
  const { draw, finish, cancel } = useMapDrawing(sat.map, mapTool, {
    onAoi: (a) => {
      setAoi(a);
      toast(`AOI selected · ${describeAoi(a)}`, 'success');
    },
    onInspect: setInspect
  });

  const searchScenes = useCallback(
    async (kind: 'optical' | 'sar' = collection) => {
      const bbox = aoi ? aoi.bbox : sat.getViewBbox();
      if (!bbox) return;
      setSceneState({ status: 'loading' });
      setFocusedScene(null);
      const res = await searchStac({
        collection: STAC_COLLECTIONS[kind],
        bbox,
        start: imagery.startDate,
        end: imagery.endDate,
        maxCloud: kind === 'optical' ? maxCloud : null
      });
      setSceneState(res);
      setScenes(res.status === 'success' ? res.data : []);
    },
    [collection, aoi, sat, imagery.startDate, imagery.endDate, maxCloud]
  );

  // When SAR is switched on, surface real Sentinel-1 scene coverage for the view.
  const prevSar = useRef(imagery.sar);
  useEffect(() => {
    if (imagery.sar && !prevSar.current && sat.map) void searchScenes('sar');
    prevSar.current = imagery.sar;
  }, [imagery.sar, sat.map, searchScenes]);

  useEffect(() => {
    if (!fullscreen) return;
    document.body.style.overflow = 'hidden';
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && draw.points === 0 && setFullscreen(false);
    window.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = '';
      window.removeEventListener('keydown', onKey);
    };
  }, [fullscreen, draw.points]);

  const locate = () => {
    if (!navigator.geolocation) return toast('Geolocation is not supported in this browser', 'error');
    navigator.geolocation.getCurrentPosition(
      (p) => {
        sat.setView([p.coords.latitude, p.coords.longitude], 12);
        toast('Map centred on your location');
      },
      () => toast('Location permission unavailable', 'error'),
      { timeout: 10000 }
    );
  };

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast('Copied to clipboard', 'success');
    } catch {
      toast('Clipboard access blocked by the browser', 'error');
    }
  };

  const ask = () => {
    if (!aoi) return toast('Select an AOI first', 'error');
    const q = question.trim() || 'Analyze this selected area';
    setQuery(q);
    startAnalysis(q);
  };

  const statusText = (() => {
    switch (mapTool) {
      case 'select':
        return inspect ? `Inspected ${formatLatLng(inspect)}` : 'Select · click to inspect coordinates';
      case 'point':
        return 'Point · click to set a point AOI';
      case 'rectangle':
        return draw.points ? 'Rectangle · click the opposite corner' : 'Rectangle · click the first corner';
      case 'polygon':
        return draw.points ? `Polygon · ${draw.points} vertices · double-click or Finish` : 'Polygon · click to add vertices';
      case 'measure':
        return draw.distanceKm != null ? `Distance: ${formatDistance(draw.distanceKm)}` : 'Measure · click points along a path';
    }
  })();

  const drawing = (mapTool === 'polygon' || mapTool === 'measure' || mapTool === 'rectangle') && draw.points > 0;

  return (
    <section className="page">
      <div className="section-head">
        <div>
          <h2>Map & AOI workspace</h2>
          <p>Select a specific region, draw an AOI, inspect layers, and send the selected region directly to the AI.</p>
        </div>
      </div>

      <div className="panel">
        <div className="quick-toolbar">
          <div className="tool-group" role="toolbar" aria-label="Drawing tools">
            {TOOLS.map((t) => {
              const Icon = t.icon;
              return (
                <button
                  key={t.id}
                  className={`btn${mapTool === t.id ? ' green' : ''}`}
                  onClick={() => setMapTool(t.id)}
                  aria-pressed={mapTool === t.id}>
                  
                  <Icon size={14} /> {t.label}
                </button>);

            })}
          </div>
          <span className="spacer" />
          <div className="tool-group" role="group" aria-label="Basemap">
            {BASEMAPS.map((b) =>
            <button
              key={b.id}
              className={`btn${imagery.basemap === b.id ? ' is-active' : ''}`}
              onClick={() => updateImagery({ basemap: b.id })}
              aria-pressed={imagery.basemap === b.id}>
              
                {b.label}
              </button>
            )}
          </div>
          <button className="btn" onClick={() => void searchScenes()} disabled={sceneState.status === 'loading'}>
            <SearchIcon size={14} /> Search Sentinel
          </button>
          <button className="btn" onClick={locate}>
            <LocateFixedIcon size={14} /> Locate
          </button>
        </div>

        <div style={{ padding: 12 }}>
          <div className={`map${fullscreen ? ' is-fullscreen' : ''}`}>
            <div ref={containerRef} className="map-canvas" aria-label="Interactive satellite map" />
            {latestMapAction && (
              <div
                className="map-analytical-overlay"
                style={{
                  position: 'absolute',
                  top: 14,
                  left: '50%',
                  transform: 'translateX(-50%)',
                  zIndex: 600,
                  background: 'rgba(15, 23, 42, 0.92)',
                  backdropFilter: 'blur(10px)',
                  border: '1px solid var(--accent)',
                  borderRadius: '10px',
                  padding: '8px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  boxShadow: '0 6px 24px rgba(0, 0, 0, 0.4)',
                  fontSize: '12px',
                  color: 'var(--text)'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <LayersIcon size={14} color="var(--accent)" />
                  <b>Analytical Layer:</b> {latestMapAction.operation || 'Result overlay'}
                  {latestMapAction.findings_count !== undefined && (
                    <span className="badge ok" style={{ marginLeft: '4px', fontSize: '11px', padding: '2px 6px' }}>
                      {latestMapAction.findings_count} features
                    </span>
                  )}
                </div>
                {latestMapAction.mask_url && (
                  <a
                    href={latestMapAction.mask_url}
                    target="_blank"
                    rel="noreferrer"
                    className="btn small"
                    style={{ padding: '2px 8px', fontSize: '11px' }}
                  >
                    View Mask Asset
                  </a>
                )}
                <button
                  className="btn small"
                  style={{ padding: '2px 6px', fontSize: '11px' }}
                  onClick={() => setLatestMapAction(null)}
                  title="Dismiss analytical overlay"
                >
                  <XIcon size={11} />
                </button>
              </div>
            )}
            <div className="map-label status">
              <span>{statusText}</span>
              {drawing &&
              <span className="map-draw-actions">
                  {mapTool !== 'rectangle' &&
                <button className="btn small green" onClick={finish} disabled={mapTool === 'polygon' ? draw.points < 3 : draw.points < 2}>
                      <CheckIcon size={12} /> Finish
                    </button>
                }
                  <button className="btn small" onClick={cancel}>
                    <XIcon size={12} /> Cancel
                  </button>
                </span>
              }
            </div>
            <div className="map-tools">
              <button onClick={sat.zoomIn} aria-label="Zoom in"><PlusIcon size={16} /></button>
              <button onClick={sat.zoomOut} aria-label="Zoom out"><MinusIcon size={16} /></button>
              <button onClick={locate} aria-label="Locate me"><LocateFixedIcon size={16} /></button>
              <button onClick={() => setFullscreen((f) => !f)} aria-label={fullscreen ? 'Exit fullscreen' : 'Fullscreen'}>
                {fullscreen ? <MinimizeIcon size={16} /> : <MaximizeIcon size={16} />}
              </button>
            </div>
            {sat.cursor && <div className="map-label coords">{formatLatLng(sat.cursor)}</div>}
            {imagery.compare &&
            <>
                <span className="view-tag left" style={{ top: 52, zIndex: 500 }}>BEFORE · {imagery.compareDate}</span>
                <span className="view-tag right" style={{ top: 52, right: 58, zIndex: 500 }}>AFTER · {imagery.date}</span>
                <div className="map-compare-line" style={{ left: `${comparePos}%` }} />
                <div className="map-compare-range">
                  <input
                  type="range"
                  min={0}
                  max={100}
                  value={comparePos}
                  onChange={(e) => setComparePos(Number(e.target.value))}
                  aria-label="Split-screen compare position" />
                
                </div>
              </>
            }
            {fullscreen &&
            <button className="btn map-exit" onClick={() => setFullscreen(false)}>
                Exit fullscreen · Esc
              </button>
            }
          </div>

          <ImageryControls
            imagery={imagery}
            updateImagery={updateImagery}
            layerStatus={sat.layerStatus}
            aoi={aoi}
            collection={collection}
            setCollection={setCollection}
            maxCloud={maxCloud}
            setMaxCloud={setMaxCloud}
            sceneState={sceneState}
            scenes={scenes}
            focusedScene={focusedScene}
            onFocus={setFocusedScene}
            onSearch={() => void searchScenes()} />
          

          <div className="map-bottom-grid">
            <AoiPanel
              aoi={aoi}
              question={question}
              setQuestion={setQuestion}
              onAsk={ask}
              onZoom={sat.fitAoi}
              onClear={() => {
                setAoi(null);
                toast('AOI cleared');
              }}
              onCopy={(t) => void copy(t)}
              onDraw={() => setMapTool('rectangle')} />
            
            <MapLayersPanel imagery={imagery} updateImagery={updateImagery} layerStatus={sat.layerStatus} />
          </div>
        </div>
      </div>
    </section>);

}