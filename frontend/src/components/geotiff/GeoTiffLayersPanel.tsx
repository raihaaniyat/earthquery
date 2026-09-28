import React from 'react';
import {
  EyeIcon,
  EyeOffIcon,
  Maximize2Icon,
  Trash2Icon,
  InfoIcon,
  SparklesIcon,
  CrosshairIcon,
  LayersIcon
} from 'lucide-react';
import type { GeoTiffLayer } from '../../types/geotiff';

interface Props {
  layers: GeoTiffLayer[];
  selectedLayerId: string | null;
  onSelectLayer: (layerId: string) => void;
  onToggleVisibility: (layerId: string) => void;
  onChangeOpacity: (layerId: string, opacity: number) => void;
  onZoomToLayer: (layerId: string) => void;
  onRemoveLayer: (layerId: string) => void;
  onSetAoi?: (layer: GeoTiffLayer) => void;
  onSendToAi?: (layer: GeoTiffLayer) => void;
}

export function GeoTiffLayersPanel({
  layers,
  selectedLayerId,
  onSelectLayer,
  onToggleVisibility,
  onChangeOpacity,
  onZoomToLayer,
  onRemoveLayer,
  onSetAoi,
  onSendToAi
}: Props) {
  if (layers.length === 0) {
    return (
      <div className="geotiff-layers-empty">
        <LayersIcon size={24} style={{ color: 'var(--muted)', opacity: 0.6 }} />
        <p>No GeoTIFF layers added yet. Upload a GeoTIFF to see it listed here.</p>
      </div>
    );
  }

  return (
    <div className="geotiff-layers-list">
      {layers.map((layer) => {
        const isSelected = layer.id === selectedLayerId;
        const opacityPercent = Math.round(layer.opacity * 100);

        return (
          <div
            key={layer.id}
            className={`geotiff-layer-card ${isSelected ? 'selected' : ''}`}
            onClick={() => onSelectLayer(layer.id)}
          >
            {/* Header row */}
            <div className="layer-card-top">
              <label
                className="layer-check-label"
                onClick={(e) => e.stopPropagation()}
                title={layer.visible ? 'Hide layer' : 'Show layer'}
              >
                <input
                  type="checkbox"
                  checked={layer.visible}
                  onChange={() => onToggleVisibility(layer.id)}
                />
                <span className="layer-name" title={layer.name}>
                  {layer.name}
                </span>
              </label>

              <div className="layer-action-icons" onClick={(e) => e.stopPropagation()}>
                <button
                  className="icon-action-btn"
                  onClick={() => onToggleVisibility(layer.id)}
                  title={layer.visible ? 'Hide' : 'Show'}
                  aria-label="Toggle visibility"
                >
                  {layer.visible ? <EyeIcon size={14} /> : <EyeOffIcon size={14} className="muted" />}
                </button>
                <button
                  className="icon-action-btn"
                  onClick={() => onZoomToLayer(layer.id)}
                  title="Zoom to exact layer bounds"
                  aria-label="Zoom to layer"
                >
                  <Maximize2Icon size={14} />
                </button>
                <button
                  className={`icon-action-btn ${isSelected ? 'active' : ''}`}
                  onClick={() => onSelectLayer(layer.id)}
                  title="Inspect metadata"
                  aria-label="Inspect metadata"
                >
                  <InfoIcon size={14} />
                </button>
                <button
                  className="icon-action-btn danger"
                  onClick={() => onRemoveLayer(layer.id)}
                  title="Remove layer"
                  aria-label="Remove layer"
                >
                  <Trash2Icon size={14} />
                </button>
              </div>
            </div>

            {/* Sub-info */}
            <div className="layer-sub-info">
              <span className="badge crs-badge">
                {layer.metadata.epsg ? `EPSG:${layer.metadata.epsg}` : 'Geographic'}
              </span>
              <span className="layer-dims">
                {layer.metadata.width} × {layer.metadata.height} px
              </span>
              <span className="layer-bands">
                {layer.metadata.numBands} {layer.metadata.numBands >= 4 ? 'bands (RGBA)' : 'bands'}
              </span>
            </div>

            {/* Opacity slider */}
            <div className="layer-opacity-row" onClick={(e) => e.stopPropagation()}>
              <span className="opacity-label">Opacity</span>
              <input
                type="range"
                min={0}
                max={100}
                value={opacityPercent}
                onChange={(e) => onChangeOpacity(layer.id, Number(e.target.value) / 100)}
                aria-label={`${layer.name} opacity`}
              />
              <span className="opacity-value">{opacityPercent}%</span>
            </div>

            {/* Action buttons */}
            <div className="layer-card-actions" onClick={(e) => e.stopPropagation()}>
              <button
                className="btn small"
                onClick={() => onZoomToLayer(layer.id)}
                title="Fit map viewport to this raster"
              >
                <Maximize2Icon size={12} /> Fit view
              </button>
              {onSetAoi && (
                <button
                  className="btn small"
                  onClick={() => onSetAoi(layer)}
                  title="Set area of interest from this raster extent"
                >
                  <CrosshairIcon size={12} /> Set as AOI
                </button>
              )}
              {onSendToAi && (
                <button
                  className="btn small primary"
                  onClick={() => onSendToAi(layer)}
                  title="Attach this GeoTIFF raster to the AI Analyst workspace"
                >
                  <SparklesIcon size={12} /> AI Analyst
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
