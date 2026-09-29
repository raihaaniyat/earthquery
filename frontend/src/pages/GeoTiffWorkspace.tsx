import React, { useRef, useState, useEffect } from 'react';
import {
  UploadCloudIcon,
  GlobeIcon,
  LayersIcon,
  MaximizeIcon,
  MinimizeIcon,
  LocateFixedIcon,
  PlusIcon,
  MinusIcon,
  TagIcon
} from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import { useWorkspace } from '../contexts/WorkspaceContext';
import { useGeoTiffMap } from '../hooks/useGeoTiffMap';
import { GeoTiffUploader } from '../components/geotiff/GeoTiffUploader';
import { GeoTiffMetadataPanel } from '../components/geotiff/GeoTiffMetadataPanel';
import { GeoTiffLayersPanel } from '../components/geotiff/GeoTiffLayersPanel';
import { AoiCoordinateDisplay } from '../components/map/AoiCoordinateDisplay';
import { BASEMAPS } from '../data/apiConfig';
import { formatLatLng } from '../utils/geo';
import { createId } from '../utils/files';
import type { BasemapId, LatLngTuple, Aoi, BBox, AttachedImage } from '../types/app';
import type { GeoTiffLayer } from '../types/geotiff';

export function GeoTiffWorkspace() {
  const { toast, navigate } = useApp();
  const { aoi, setAoi, addFiles, geoTiffLayers, addGeoTiffLayer, removeGeoTiffLayer } = useWorkspace();
  const containerRef = useRef<HTMLDivElement>(null);

  const [layers, setLayers] = useState<GeoTiffLayer[]>(geoTiffLayers);
  const [selectedLayerId, setSelectedLayerId] = useState<string | null>(geoTiffLayers[0]?.id || null);
  const [basemap, setBasemap] = useState<BasemapId>('satellite');
  const [showLabels, setShowLabels] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [activeTab, setActiveTab] = useState<'upload' | 'metadata'>('upload');

  // Synchronize with global shared GeoTIFF layers
  useEffect(() => {
    if (geoTiffLayers.length > 0) {
      setLayers((prev) => {
        const next = [...prev];
        for (const gl of geoTiffLayers) {
          if (!next.some((l) => l.id === gl.id || l.name === gl.name)) {
            next.unshift(gl);
          }
        }
        return next;
      });
      if (!selectedLayerId) {
        setSelectedLayerId(geoTiffLayers[0].id);
      }
    }
  }, [geoTiffLayers, selectedLayerId]);

  const { map, cursor, fitLayer, zoomIn, zoomOut } = useGeoTiffMap(containerRef, {
    layers,
    basemap,
    showLabels
  });

  const selectedLayer = layers.find((l) => l.id === selectedLayerId) ?? (layers[0] || null);

  // When a layer is loaded
  const handleLayerLoaded = (newLayer: GeoTiffLayer) => {
    addGeoTiffLayer(newLayer);
    setLayers((prev) => [newLayer, ...prev.filter((l) => l.id !== newLayer.id)]);
    setSelectedLayerId(newLayer.id);
    setActiveTab('metadata');

    toast(`GeoTIFF loaded · ${newLayer.name} (${newLayer.metadata.crsName})`, 'success');

    // Automatically zoom/fly to the newly added raster
    setTimeout(() => {
      fitLayer(newLayer);
    }, 150);
  };

  const handleToggleVisibility = (id: string) => {
    setLayers((prev) =>
      prev.map((l) => (l.id === id ? { ...l, visible: !l.visible } : l))
    );
  };

  const handleChangeOpacity = (id: string, opacity: number) => {
    setLayers((prev) =>
      prev.map((l) => (l.id === id ? { ...l, opacity } : l))
    );
  };

  const handleZoomToLayer = (id: string) => {
    const layer = layers.find((l) => l.id === id);
    if (layer) {
      fitLayer(layer);
      setSelectedLayerId(id);
      toast(`Fitted view to ${layer.name}`);
    }
  };

  const handleRemoveLayer = (id: string) => {
    removeGeoTiffLayer(id);
    setLayers((prev) => prev.filter((l) => l.id !== id));
    if (selectedLayerId === id) {
      const remaining = layers.filter((l) => l.id !== id);
      setSelectedLayerId(remaining.length > 0 ? remaining[0].id : null);
    }
    toast('GeoTIFF layer removed');
  };

  const handleSetAoi = (layer: GeoTiffLayer) => {
    const { minLat, maxLat, minLon, maxLon } = layer.metadata.wgs84Bounds;
    const coordinates: LatLngTuple[] = [
      [minLat, minLon],
      [maxLat, minLon],
      [maxLat, maxLon],
      [minLat, maxLon]
    ];
    const bbox: BBox = [minLon, minLat, maxLon, maxLat];

    const aoiObj: Aoi = {
      type: 'rectangle',
      coordinates,
      bbox,
      areaKm2: 0,
      perimeterKm: 0,
      centroid: [(minLat + maxLat) / 2, (minLon + maxLon) / 2]
    };

    setAoi(aoiObj);
    toast(`Area of Interest set from ${layer.name} bounds`, 'success');
  };

  const handleSendToAi = async (layer: GeoTiffLayer) => {
    try {
      handleSetAoi(layer);
      addGeoTiffLayer(layer);
      await addFiles([layer.file]);
      toast(`Sent ${layer.name} to AI Analyst workspace`, 'success');
      navigate('home');
    } catch {
      toast('Sent GeoTIFF to AI Analyst');
      navigate('home');
    }
  };

  const locate = () => {
    if (!navigator.geolocation) return toast('Geolocation is not supported in this browser', 'error');
    navigator.geolocation.getCurrentPosition(
      (p) => {
        map?.setView([p.coords.latitude, p.coords.longitude], 12);
        toast('Map centered on your location');
      },
      () => toast('Location permission unavailable', 'error'),
      { timeout: 10000 }
    );
  };

  // Handle escape key for fullscreen
  useEffect(() => {
    if (!fullscreen) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setFullscreen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [fullscreen]);

  return (
    <section className="page geotiff-workspace-page">
      <div className="section-head">
        <div>
          <h2>GeoTIFF Workspace</h2>
          <p>
            Upload geospatial GeoTIFFs (<code>.tif</code> / <code>.tiff</code>), read embedded metadata &amp; CRS, and accurately project rasters onto the interactive map.
          </p>
        </div>
      </div>

      <div className="panel">
        {/* Quick Toolbar */}
        <div className="quick-toolbar">
          <div className="tool-group" role="group" aria-label="Basemap">
            {BASEMAPS.map((b) => (
              <button
                key={b.id}
                className={`btn${basemap === b.id ? ' is-active' : ''}`}
                onClick={() => setBasemap(b.id)}
                aria-pressed={basemap === b.id}
              >
                {b.label}
              </button>
            ))}
          </div>

          <button
            className={`btn${showLabels ? ' is-active' : ''}`}
            onClick={() => setShowLabels((prev) => !prev)}
            title="Toggle place labels and boundaries"
          >
            <TagIcon size={14} /> Labels
          </button>

          {aoi && (
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
              <span className="badge ok" style={{ fontSize: '11px', padding: '3px 8px' }}>
                AOI selected
              </span>
              <button
                className="btn small danger-text"
                onClick={() => {
                  setAoi(null);
                  toast('AOI cleared');
                }}
                title="Clear selected AOI"
              >
                Clear AOI
              </button>
            </div>
          )}

          <span className="spacer" />

          {selectedLayer && (
            <div className="active-layer-indicator">
              <span className="active-dot" />
              <span className="active-name" title={selectedLayer.name}>
                {selectedLayer.name}
              </span>
              <span className="badge crs-badge">
                {selectedLayer.metadata.epsg ? `EPSG:${selectedLayer.metadata.epsg}` : 'Geographic'}
              </span>
            </div>
          )}

          <button className="btn" onClick={locate}>
            <LocateFixedIcon size={14} /> Locate
          </button>
        </div>

        <div style={{ padding: 12 }}>
          {/* Map canvas */}
          <div className={`map${fullscreen ? ' is-fullscreen' : ''}`}>
            <div ref={containerRef} className="map-canvas" aria-label="Interactive satellite map" />

            <div className="map-label status">
              <GlobeIcon size={14} style={{ color: 'var(--accent)' }} />
              <span>
                {layers.length === 0
                  ? 'No GeoTIFF uploaded · Use the panel below to upload or load a sample'
                  : `${layers.filter((l) => l.visible).length} of ${layers.length} GeoTIFF layers visible`}
              </span>
            </div>

            <div className="map-tools">
              <button onClick={zoomIn} aria-label="Zoom in">
                <PlusIcon size={16} />
              </button>
              <button onClick={zoomOut} aria-label="Zoom out">
                <MinusIcon size={16} />
              </button>
              <button onClick={locate} aria-label="Locate me">
                <LocateFixedIcon size={16} />
              </button>
              <button
                onClick={() => setFullscreen((f) => !f)}
                aria-label={fullscreen ? 'Exit fullscreen' : 'Fullscreen'}
              >
                {fullscreen ? <MinimizeIcon size={16} /> : <MaximizeIcon size={16} />}
              </button>
            </div>

            {cursor && <div className="map-label coords">{formatLatLng(cursor)}</div>}
            <AoiCoordinateDisplay aoi={aoi} onClear={() => { setAoi(null); toast('AOI cleared'); }} />

            {fullscreen && (
              <button className="btn map-exit" onClick={() => setFullscreen(false)}>
                Exit fullscreen · Esc
              </button>
            )}
          </div>

          {/* Bottom Grid */}
          <div className="geotiff-bottom-grid">
            {/* Left Column: Upload & Metadata tabs */}
            <div className="geotiff-left-card">
              <div className="card-tab-bar">
                <button
                  className={`tab-btn ${activeTab === 'upload' ? 'active' : ''}`}
                  onClick={() => setActiveTab('upload')}
                >
                  <UploadCloudIcon size={14} /> Upload GeoTIFF
                </button>
                <button
                  className={`tab-btn ${activeTab === 'metadata' ? 'active' : ''}`}
                  onClick={() => setActiveTab('metadata')}
                >
                  <GlobeIcon size={14} /> Metadata Inspector
                  {selectedLayer && <span className="tab-pill">{selectedLayer.metadata.epsg ? `EPSG:${selectedLayer.metadata.epsg}` : 'CRS'}</span>}
                </button>
              </div>

              <div className="card-tab-content">
                {activeTab === 'upload' ? (
                  <GeoTiffUploader onLayerLoaded={handleLayerLoaded} onError={(err) => toast(err, 'error')} />
                ) : (
                  <GeoTiffMetadataPanel
                    metadata={selectedLayer?.metadata || null}
                    onCopyCoordinates={(coords) => toast(`Copied bounds: ${coords}`, 'success')}
                  />
                )}
              </div>
            </div>

            {/* Right Column: Layer Management */}
            <div className="geotiff-right-card">
              <div className="card-header">
                <div className="header-title">
                  <LayersIcon size={15} style={{ color: 'var(--accent)' }} />
                  <h3>GeoTIFF Layers</h3>
                </div>
                <span className="layers-count">{layers.length}</span>
              </div>

              <GeoTiffLayersPanel
                layers={layers}
                selectedLayerId={selectedLayerId}
                onSelectLayer={(id) => {
                  setSelectedLayerId(id);
                  setActiveTab('metadata');
                }}
                onToggleVisibility={handleToggleVisibility}
                onChangeOpacity={handleChangeOpacity}
                onZoomToLayer={handleZoomToLayer}
                onRemoveLayer={handleRemoveLayer}
                onSetAoi={handleSetAoi}
                onSendToAi={handleSendToAi}
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
