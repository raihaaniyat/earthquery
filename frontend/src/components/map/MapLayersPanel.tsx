import React from 'react';
import { ANALYSIS_OVERLAYS, SATELLITE_SOURCES } from '../../data/apiConfig';
import type { LayerKey, LayerStatus } from '../../hooks/useSatelliteMap';
import type { ImageryLayerKey, ImagerySettings, OverlayId } from '../../types/app';

interface MapLayersPanelProps {
  imagery: ImagerySettings;
  updateImagery: (p: Partial<ImagerySettings>) => void;
  layerStatus: Record<LayerKey, LayerStatus>;
}

const STATUS_TEXT: Record<LayerStatus, string> = {
  idle: '',
  loading: 'Loading…',
  ready: 'Live',
  partial: 'Partial coverage',
  error: 'Unavailable'
};

export function MapLayersPanel({ imagery, updateImagery, layerStatus }: MapLayersPanelProps) {
  const setOpacity = (k: ImageryLayerKey, v: number) => updateImagery({ opacity: { ...imagery.opacity, [k]: v } });
  const sarRaster = Boolean(SATELLITE_SOURCES.sentinelHubInstanceId);

  const rows: {key: ImageryLayerKey;label: string;color: string;checked: boolean;toggle: (v: boolean) => void;note?: string;}[] = [
  { key: 'optical', label: 'Sentinel-2 optical', color: '#8aa88d', checked: imagery.optical, toggle: (v) => updateImagery({ optical: v }) },
  {
    key: 'sar',
    label: 'Sentinel-1 SAR',
    color: '#9aa3b5',
    checked: imagery.sar,
    toggle: (v) => updateImagery({ sar: v }),
    note: sarRaster ? undefined : 'Footprints only'
  },
  { key: 'gibs', label: 'NASA GIBS true colour', color: '#c7a86b', checked: imagery.gibs, toggle: (v) => updateImagery({ gibs: v }) }];


  return (
    <div className="panel panel-pad">
      <div className="panel-title">Map layers</div>
      <div className="layer-list">
        {rows.map((r) =>
        <div className="layer-row" key={r.key}>
            <label>
              <input type="checkbox" checked={r.checked} onChange={(e) => r.toggle(e.target.checked)} />
              <span className="layer-swatch" style={{ background: r.color }} />
              <span>
                {r.label}
                <br />
                <span className="layer-meta">{r.note ?? (r.checked ? STATUS_TEXT[layerStatus[r.key]] : 'Hidden')}</span>
              </span>
            </label>
            <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={imagery.opacity[r.key]}
            disabled={!r.checked || r.key === 'sar' && !sarRaster}
            onChange={(e) => setOpacity(r.key, Number(e.target.value))}
            aria-label={`${r.label} opacity`} />
          
          </div>
        )}

        <div className="layer-row">
          <label>
            <input type="checkbox" checked={imagery.overlay !== null} onChange={(e) => updateImagery({ overlay: e.target.checked ? 'ndvi' : null })} />
            <span className="layer-swatch" style={{ background: '#d47d72' }} />
            <span>
              Analysis overlay
              <br />
              <span className="layer-meta">{imagery.overlay ? STATUS_TEXT[layerStatus.overlay] : 'Hidden'}</span>
            </span>
          </label>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={imagery.opacity.overlay}
            disabled={!imagery.overlay}
            onChange={(e) => setOpacity('overlay', Number(e.target.value))}
            aria-label="Analysis overlay opacity" />
          
          <select
            value={imagery.overlay ?? ''}
            onChange={(e) => updateImagery({ overlay: (e.target.value || null) as OverlayId | null })}
            aria-label="Analysis overlay product">
            
            <option value="">None</option>
            {ANALYSIS_OVERLAYS.map((o) =>
            <option key={o.id} value={o.id}>
                {o.label}
              </option>
            )}
          </select>
        </div>

        <div className="layer-row">
          <label>
            <input type="checkbox" checked={imagery.labels} onChange={(e) => updateImagery({ labels: e.target.checked })} />
            <span className="layer-swatch" style={{ background: '#e8e4ec' }} />
            Place labels
          </label>
        </div>
        <div className="layer-row">
          <label>
            <input type="checkbox" checked={imagery.showFootprints} onChange={(e) => updateImagery({ showFootprints: e.target.checked })} />
            <span className="layer-swatch" style={{ background: '#8aa8ff' }} />
            Scene footprints
          </label>
        </div>
        <div className="layer-row">
          <label>
            <input type="checkbox" checked={imagery.showAoi} onChange={(e) => updateImagery({ showAoi: e.target.checked })} />
            <span className="layer-swatch" style={{ background: '#a56cff' }} />
            AOI geometry
          </label>
        </div>
      </div>
    </div>);

}