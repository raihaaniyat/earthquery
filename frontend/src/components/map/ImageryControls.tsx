import React from 'react';
import { SearchIcon, EyeIcon, SatelliteIcon, RadarIcon, GlobeIcon } from 'lucide-react';
import { StateNotice } from '../StateNotice';
import { SATELLITE_SOURCES } from '../../data/apiConfig';
import { todayIso, validateDate } from '../../utils/geo';
import type { LayerKey, LayerStatus } from '../../hooks/useSatelliteMap';
import type { Aoi, ImagerySettings, RequestState, StacScene } from '../../types/app';

interface ImageryControlsProps {
  imagery: ImagerySettings;
  updateImagery: (p: Partial<ImagerySettings>) => void;
  layerStatus: Record<LayerKey, LayerStatus>;
  aoi: Aoi | null;
  collection: 'optical' | 'sar';
  setCollection: (c: 'optical' | 'sar') => void;
  maxCloud: number;
  setMaxCloud: (n: number) => void;
  sceneState: RequestState<StacScene[]>;
  scenes: StacScene[];
  focusedScene: string | null;
  onFocus: (id: string) => void;
  onSearch: () => void;
}

function summarize(status: Record<LayerKey, LayerStatus>): {dot: string;text: string;} {
  const values = Object.values(status).filter((s) => s !== 'idle');
  if (!values.length) return { dot: 'idle', text: 'Basemap only — enable an imagery source' };
  if (values.includes('error')) return { dot: 'bad', text: 'Imagery unavailable for this view or date' };
  if (values.includes('loading')) return { dot: '', text: 'Loading imagery tiles…' };
  if (values.includes('partial')) return { dot: '', text: 'Some tiles are unavailable for this date' };
  return { dot: 'ok', text: `${values.length} imagery layer${values.length > 1 ? 's' : ''} live` };
}

export function ImageryControls(p: ImageryControlsProps) {
  const { imagery, updateImagery } = p;
  const hasInstance = Boolean(SATELLITE_SOURCES.sentinelHubInstanceId);
  const summary = summarize(p.layerStatus);
  const dateError = validateDate(imagery.date) ?? (imagery.compare ? validateDate(imagery.compareDate) : null);
  const today = todayIso(0);

  return (
    <div className="api-panel">
      <div className="api-head">
        <b>Live imagery sources</b>
        <span className={`api-dot ${summary.dot}`} aria-hidden="true" />
        <span>{summary.text}</span>
      </div>

      <div className="api-controls">
        <label>
          <input type="checkbox" checked={imagery.optical} onChange={(e) => updateImagery({ optical: e.target.checked })} />
          Sentinel-2 / Optical
        </label>
        <label>
          <input
            type="checkbox"
            checked={imagery.sar}
            onChange={(e) => {
              updateImagery({ sar: e.target.checked });
              if (e.target.checked) p.setCollection('sar');
            }} />
          
          Sentinel-1 / SAR
        </label>
        <label>
          <input type="checkbox" checked={imagery.gibs} onChange={(e) => updateImagery({ gibs: e.target.checked })} />
          NASA GIBS
        </label>
        <label>
          Date
          <input type="date" value={imagery.date} max={today} onChange={(e) => updateImagery({ date: e.target.value })} />
        </label>
        <label>
          <input type="checkbox" checked={imagery.compare} onChange={(e) => updateImagery({ compare: e.target.checked })} />
          Compare
        </label>
        {imagery.compare &&
        <label>
            Before
            <input type="date" value={imagery.compareDate} max={today} onChange={(e) => updateImagery({ compareDate: e.target.value })} />
          </label>
        }
      </div>

      <div className="source-notes">
        <span>
          <SatelliteIcon size={12} />
          Optical: {hasInstance ? 'Sentinel-2 L2A (dated, Sentinel Hub)' : 'Sentinel-2 cloudless mosaic (EOX)'}
        </span>
        <span>
          <RadarIcon size={12} />
          SAR: {hasInstance ? 'Sentinel-1 GRD (Sentinel Hub)' : 'scene footprints from Copernicus STAC — raster rendering needs a Sentinel Hub instance'}
        </span>
        <span>
          <GlobeIcon size={12} />
          GIBS: MODIS Terra true colour for the selected date{imagery.compare ? ' · split-screen compare active' : ''}
        </span>
      </div>

      {dateError && <StateNotice state={{ status: 'invalid', message: dateError }} />}

      <div className="api-controls" style={{ marginTop: 12 }}>
        <label>
          Scenes
          <select value={p.collection} onChange={(e) => p.setCollection(e.target.value as 'optical' | 'sar')}>
            <option value="optical">Sentinel-2 L2A</option>
            <option value="sar">Sentinel-1 GRD</option>
          </select>
        </label>
        <label>
          From
          <input type="date" value={imagery.startDate} max={today} onChange={(e) => updateImagery({ startDate: e.target.value })} />
        </label>
        <label>
          To
          <input type="date" value={imagery.endDate} max={today} onChange={(e) => updateImagery({ endDate: e.target.value })} />
        </label>
        {p.collection === 'optical' &&
        <label>
            Max cloud
            <input
            type="number"
            min={0}
            max={100}
            value={p.maxCloud}
            onChange={(e) => p.setMaxCloud(Math.min(100, Math.max(0, Number(e.target.value))))} />
          
            %
          </label>
        }
        <button className="btn small green" onClick={p.onSearch} disabled={p.sceneState.status === 'loading'}>
          <SearchIcon size={12} /> Search {p.aoi ? 'AOI' : 'visible area'}
        </button>
      </div>

      <div className="stac-results">
        <StateNotice
          state={p.sceneState}
          idleText="Search the AOI or visible map area for real Sentinel scene metadata from Copernicus Data Space."
          loadingText="Searching Copernicus STAC…"
          successText={`${p.scenes.length} scene${p.scenes.length === 1 ? '' : 's'} found · footprints drawn on the map`}
          onRetry={p.onSearch} />
        
        {p.scenes.map((s) =>
        <div key={s.id} className={`stac-item${p.focusedScene === s.id ? ' focused' : ''}`}>
            <span>
              <b>{s.id}</b>
              <br />
              <small>
                {s.datetime.slice(0, 16).replace('T', ' ')} UTC
                {s.platform ? ` · ${s.platform}` : ''}
                {s.cloudCover != null ? ` · cloud ${s.cloudCover.toFixed(1)}%` : ''}
              </small>
            </span>
            <button className="btn small" onClick={() => p.onFocus(s.id)} aria-label={`View footprint of ${s.id}`}>
              <EyeIcon size={12} /> View
            </button>
          </div>
        )}
      </div>
    </div>);

}