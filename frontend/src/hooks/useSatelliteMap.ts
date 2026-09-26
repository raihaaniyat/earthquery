import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';
import L from 'leaflet';
import { ANALYSIS_OVERLAYS, BASEMAPS, LABELS_LAYER, SATELLITE_SOURCES } from '../data/apiConfig';
import { clampBbox, wrapLng } from '../utils/geo';
import type { Aoi, BBox, ImagerySettings, LatLngTuple, StacScene } from '../types/app';

export type LayerKey = 'optical' | 'sar' | 'gibs' | 'overlay' | 'compare';
export type LayerStatus = 'idle' | 'loading' | 'ready' | 'partial' | 'error';

interface Options {
  imagery: ImagerySettings;
  aoi: Aoi | null;
  scenes: StacScene[];
  focusedSceneId: string | null;
  comparePos: number;
}

const ACCENT = '#a56cff';
const PANES: [string, number][] = [
['opticalPane', 210],
['sarPane', 220],
['gibsPane', 230],
['comparePane', 240],
['productPane', 260],
['labelsPane', 270]];


const IDLE: Record<LayerKey, LayerStatus> = { optical: 'idle', sar: 'idle', gibs: 'idle', overlay: 'idle', compare: 'idle' };

function wms(url: string, params: Record<string, string | number | boolean>, options: L.TileLayerOptions): L.TileLayer.WMS {
  return L.tileLayer.wms(url, { ...options, ...params } as unknown as L.WMSOptions);
}

export function useSatelliteMap(containerRef: RefObject<HTMLDivElement>, opts: Options) {
  const { imagery, aoi, scenes, focusedSceneId, comparePos } = opts;
  const [map, setMap] = useState<L.Map | null>(null);
  const [cursor, setCursor] = useState<LatLngTuple | null>(null);
  const [layerStatus, setLayerStatus] = useState<Record<LayerKey, LayerStatus>>(IDLE);
  const layers = useRef<Partial<Record<LayerKey, L.TileLayer>>>({});
  const compareLayers = useRef<{before: L.TileLayer;after: L.TileLayer;} | null>(null);
  const comparePosRef = useRef(comparePos);
  const footprintRefs = useRef<Map<string, L.GeoJSON>>(new Map());

  const setStatus = useCallback((k: LayerKey, s: LayerStatus) => {
    setLayerStatus((p) => p[k] === s ? p : { ...p, [k]: s });
  }, []);

  const track = useCallback(
    (layer: L.TileLayer, key: LayerKey) => {
      let ok = 0;
      let err = 0;
      layer.on('loading', () => {
        ok = 0;
        err = 0;
        setStatus(key, 'loading');
      });
      layer.on('tileload', () => ok++);
      layer.on('tileerror', () => err++);
      layer.on('load', () => setStatus(key, err > 0 ? ok === 0 ? 'error' : 'partial' : 'ready'));
    },
    [setStatus]
  );

  // Init
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const m = L.map(el, { zoomControl: false, preferCanvas: true, worldCopyJump: true, minZoom: 2 }).setView([22.9734, 78.6569], 5);
    PANES.forEach(([name, z]) => {
      const pane = m.createPane(name);
      pane.style.zIndex = String(z);
      if (name === 'labelsPane') pane.style.pointerEvents = 'none';
    });
    L.control.scale({ position: 'bottomleft', imperial: false }).addTo(m);
    m.attributionControl.setPrefix(false);
    let raf = 0;
    m.on('mousemove', (e: L.LeafletMouseEvent) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => setCursor([e.latlng.lat, wrapLng(e.latlng.lng)]));
    });
    m.on('mouseout', () => setCursor(null));
    const ro = new ResizeObserver(() => m.invalidateSize({ pan: false }));
    ro.observe(el);
    setMap(m);
    return () => {
      ro.disconnect();
      cancelAnimationFrame(raf);
      m.remove();
      setMap(null);
      setLayerStatus(IDLE);
    };
  }, [containerRef]);

  // Basemap
  useEffect(() => {
    if (!map) return;
    const cfg = BASEMAPS.find((b) => b.id === imagery.basemap) ?? BASEMAPS[0];
    const layer = L.tileLayer(cfg.url, { maxZoom: cfg.maxZoom, attribution: cfg.attribution, subdomains: cfg.subdomains ?? 'abc' });
    layer.addTo(map);
    return () => {
      map.removeLayer(layer);
    };
  }, [map, imagery.basemap]);

  // Labels
  useEffect(() => {
    if (!map || !imagery.labels) return;
    const layer = L.tileLayer(LABELS_LAYER.url, { pane: 'labelsPane', subdomains: LABELS_LAYER.subdomains, attribution: LABELS_LAYER.attribution });
    layer.addTo(map);
    return () => {
      map.removeLayer(layer);
    };
  }, [map, imagery.labels]);

  // Sentinel-2 optical
  useEffect(() => {
    if (!map || !imagery.optical) {
      setStatus('optical', 'idle');
      return;
    }
    const inst = SATELLITE_SOURCES.sentinelHubInstanceId;
    const layer = inst ?
    wms(
      SATELLITE_SOURCES.sentinelHubWms + inst,
      { layers: SATELLITE_SOURCES.sentinelHubLayers.optical, format: 'image/jpeg', transparent: false, maxcc: 30, time: `${imagery.startDate}/${imagery.endDate}` },
      { pane: 'opticalPane', attribution: 'Copernicus Sentinel-2 · Sentinel Hub' }
    ) :
    L.tileLayer(SATELLITE_SOURCES.s2Mosaic, { pane: 'opticalPane', maxNativeZoom: 15, maxZoom: 19, attribution: SATELLITE_SOURCES.s2MosaicAttribution });
    track(layer, 'optical');
    layer.setOpacity(imagery.opacity.optical);
    layer.addTo(map);
    layers.current.optical = layer;
    return () => {
      map.removeLayer(layer);
      delete layers.current.optical;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, imagery.optical, imagery.startDate, imagery.endDate, track, setStatus]);

  // Sentinel-1 SAR (raster only when a Sentinel Hub instance is configured)
  useEffect(() => {
    const inst = SATELLITE_SOURCES.sentinelHubInstanceId;
    if (!map || !imagery.sar || !inst) {
      setStatus('sar', 'idle');
      return;
    }
    const layer = wms(
      SATELLITE_SOURCES.sentinelHubWms + inst,
      { layers: SATELLITE_SOURCES.sentinelHubLayers.sar, format: 'image/png', transparent: true, time: `${imagery.startDate}/${imagery.endDate}` },
      { pane: 'sarPane', attribution: 'Copernicus Sentinel-1 · Sentinel Hub' }
    );
    track(layer, 'sar');
    layer.setOpacity(imagery.opacity.sar);
    layer.addTo(map);
    layers.current.sar = layer;
    return () => {
      map.removeLayer(layer);
      delete layers.current.sar;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, imagery.sar, imagery.startDate, imagery.endDate, track, setStatus]);

  // NASA GIBS true colour
  useEffect(() => {
    if (!map || !imagery.gibs) {
      setStatus('gibs', 'idle');
      return;
    }
    const layer = wms(
      SATELLITE_SOURCES.gibsWms,
      { layers: SATELLITE_SOURCES.gibsTrueColor, format: 'image/jpeg', transparent: false, version: '1.1.1', time: imagery.date },
      { pane: 'gibsPane', attribution: 'NASA GIBS / EOSDIS' }
    );
    track(layer, 'gibs');
    layer.setOpacity(imagery.opacity.gibs);
    layer.addTo(map);
    layers.current.gibs = layer;
    return () => {
      map.removeLayer(layer);
      delete layers.current.gibs;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, imagery.gibs, imagery.date, track, setStatus]);

  // Analysis overlay (GIBS science product)
  useEffect(() => {
    const cfg = ANALYSIS_OVERLAYS.find((o) => o.id === imagery.overlay);
    if (!map || !cfg) {
      setStatus('overlay', 'idle');
      return;
    }
    const layer = wms(
      SATELLITE_SOURCES.gibsWms,
      { layers: cfg.layer, format: 'image/png', transparent: true, version: '1.1.1', time: imagery.date },
      { pane: 'productPane', attribution: cfg.source }
    );
    track(layer, 'overlay');
    layer.setOpacity(imagery.opacity.overlay);
    layer.addTo(map);
    layers.current.overlay = layer;
    return () => {
      map.removeLayer(layer);
      delete layers.current.overlay;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, imagery.overlay, imagery.date, track, setStatus]);

  // Opacity updates without rebuilding layers
  useEffect(() => {
    (['optical', 'sar', 'gibs', 'overlay'] as const).forEach((k) => layers.current[k]?.setOpacity(imagery.opacity[k]));
  }, [imagery.opacity]);

  const updateClip = useCallback(() => {
    const pair = compareLayers.current;
    if (!map || !pair) return;
    const size = map.getSize();
    const nw = map.containerPointToLayerPoint([0, 0]);
    const se = map.containerPointToLayerPoint(size);
    const x = map.containerPointToLayerPoint([size.x * comparePosRef.current / 100, 0]).x;
    const bc = pair.before.getContainer();
    const ac = pair.after.getContainer();
    if (bc) bc.style.clip = `rect(${nw.y}px, ${x}px, ${se.y}px, ${nw.x}px)`;
    if (ac) ac.style.clip = `rect(${nw.y}px, ${se.x}px, ${se.y}px, ${x}px)`;
  }, [map]);

  // Split-screen compare: GIBS on compareDate (left) vs date (right)
  useEffect(() => {
    if (!map || !imagery.compare) {
      setStatus('compare', 'idle');
      return;
    }
    const make = (time: string) =>
    wms(
      SATELLITE_SOURCES.gibsWms,
      { layers: SATELLITE_SOURCES.gibsTrueColor, format: 'image/jpeg', transparent: false, version: '1.1.1', time },
      { pane: 'comparePane', attribution: 'NASA GIBS / EOSDIS' }
    );
    const before = make(imagery.compareDate);
    const after = make(imagery.date);
    track(after, 'compare');
    before.addTo(map);
    after.addTo(map);
    compareLayers.current = { before, after };
    updateClip();
    map.on('move zoomend resize', updateClip);
    return () => {
      map.off('move zoomend resize', updateClip);
      map.removeLayer(before);
      map.removeLayer(after);
      compareLayers.current = null;
    };
  }, [map, imagery.compare, imagery.compareDate, imagery.date, track, setStatus, updateClip]);

  useEffect(() => {
    comparePosRef.current = comparePos;
    updateClip();
  }, [comparePos, updateClip]);

  // AOI geometry
  useEffect(() => {
    if (!map || !aoi || !imagery.showAoi) return;
    const style = { color: ACCENT, weight: 2, fillOpacity: 0.12 };
    const layer: L.Layer =
    aoi.type === 'point' ?
    L.circleMarker(aoi.coordinates[0], { radius: 7, color: '#fff', weight: 2, fillColor: ACCENT, fillOpacity: 0.95 }) :
    L.polygon(aoi.coordinates, style);
    layer.addTo(map);
    return () => {
      map.removeLayer(layer);
    };
  }, [map, aoi, imagery.showAoi]);

  // Scene footprints
  useEffect(() => {
    if (!map || !imagery.showFootprints) return;
    const group = L.layerGroup().addTo(map);
    const refs = new Map<string, L.GeoJSON>();
    scenes.forEach((s) => {
      if (!s.geometry) return;
      const gj = L.geoJSON(s.geometry as unknown as Parameters<typeof L.geoJSON>[0], {
        style: { color: '#8aa8ff', weight: 1.2, dashArray: '4 4', fillOpacity: 0.04 }
      });
      gj.bindTooltip(`${s.id}<br>${s.datetime.slice(0, 10)}`, { className: 'sq-tooltip', sticky: true });
      gj.addTo(group);
      refs.set(s.id, gj);
    });
    footprintRefs.current = refs;
    return () => {
      map.removeLayer(group);
      footprintRefs.current = new Map();
    };
  }, [map, scenes, imagery.showFootprints]);

  // Focused scene
  useEffect(() => {
    if (!map || !focusedSceneId) return;
    const gj = footprintRefs.current.get(focusedSceneId);
    const scene = scenes.find((s) => s.id === focusedSceneId);
    footprintRefs.current.forEach((layer, id) =>
    layer.setStyle(id === focusedSceneId ? { color: ACCENT, weight: 2.5, dashArray: '', fillOpacity: 0.12 } : { color: '#8aa8ff', weight: 1.2, dashArray: '4 4', fillOpacity: 0.04 })
    );
    if (gj && gj.getBounds().isValid()) map.fitBounds(gj.getBounds(), { padding: [30, 30], maxZoom: 10 });else
    if (scene?.bbox) map.fitBounds([[scene.bbox[1], scene.bbox[0]], [scene.bbox[3], scene.bbox[2]]], { padding: [30, 30] });
  }, [map, focusedSceneId, scenes]);

  const getViewBbox = useCallback((): BBox | null => {
    if (!map) return null;
    const b = map.getBounds();
    return clampBbox([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
  }, [map]);

  const fitAoi = useCallback(() => {
    if (!map || !aoi) return;
    if (aoi.type === 'point') map.setView(aoi.coordinates[0], Math.max(map.getZoom(), 12));else
    map.fitBounds(L.latLngBounds(aoi.coordinates), { padding: [40, 40] });
  }, [map, aoi]);

  return {
    map,
    cursor,
    layerStatus,
    getViewBbox,
    fitAoi,
    zoomIn: () => map?.zoomIn(),
    zoomOut: () => map?.zoomOut(),
    setView: (c: LatLngTuple, z: number) => map?.setView(c, z)
  };
}