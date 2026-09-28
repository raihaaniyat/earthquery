import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';
import L from 'leaflet';
import { BASEMAPS, LABELS_LAYER } from '../data/apiConfig';
import { wrapLng } from '../utils/geo';
import type { BasemapId, LatLngTuple } from '../types/app';
import type { GeoTiffLayer } from '../types/geotiff';

interface UseGeoTiffMapOptions {
  layers: GeoTiffLayer[];
  basemap: BasemapId;
  showLabels: boolean;
}

export function useGeoTiffMap(
  containerRef: RefObject<HTMLDivElement>,
  { layers, basemap, showLabels }: UseGeoTiffMapOptions
) {
  const [map, setMap] = useState<L.Map | null>(null);
  const [cursor, setCursor] = useState<LatLngTuple | null>(null);
  const overlaysRef = useRef<Map<string, L.ImageOverlay>>(new Map());
  const basemapLayerRef = useRef<L.TileLayer | null>(null);
  const labelsLayerRef = useRef<L.TileLayer | null>(null);

  // Initialize map
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const m = L.map(el, {
      zoomControl: false,
      preferCanvas: true,
      worldCopyJump: true,
      minZoom: 2
    }).setView([22.9734, 78.6569], 4);

    // Panes
    const geotiffPane = m.createPane('geotiffPane');
    geotiffPane.style.zIndex = '350';

    const labelsPane = m.createPane('labelsPane');
    labelsPane.style.zIndex = '450';
    labelsPane.style.pointerEvents = 'none';

    // Scale
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
    };
  }, [containerRef]);

  // Basemap tile layer
  useEffect(() => {
    if (!map) return;
    if (basemapLayerRef.current) {
      map.removeLayer(basemapLayerRef.current);
    }
    const cfg = BASEMAPS.find((b) => b.id === basemap) ?? BASEMAPS[0];
    const layer = L.tileLayer(cfg.url, {
      maxZoom: cfg.maxZoom,
      attribution: cfg.attribution,
      subdomains: cfg.subdomains ?? 'abc'
    });
    layer.addTo(map);
    basemapLayerRef.current = layer;

    return () => {
      if (basemapLayerRef.current) {
        map.removeLayer(basemapLayerRef.current);
        basemapLayerRef.current = null;
      }
    };
  }, [map, basemap]);

  // Labels layer
  useEffect(() => {
    if (!map) return;
    if (labelsLayerRef.current) {
      map.removeLayer(labelsLayerRef.current);
      labelsLayerRef.current = null;
    }
    if (showLabels) {
      const layer = L.tileLayer(LABELS_LAYER.url, {
        pane: 'labelsPane',
        subdomains: LABELS_LAYER.subdomains,
        attribution: LABELS_LAYER.attribution
      });
      layer.addTo(map);
      labelsLayerRef.current = layer;
    }
  }, [map, showLabels]);

  // Sync GeoTIFF overlays
  useEffect(() => {
    if (!map) return;

    const currentMap = overlaysRef.current;
    const activeIds = new Set(layers.map((l) => l.id));

    // Remove obsolete overlays
    currentMap.forEach((overlay, id) => {
      if (!activeIds.has(id)) {
        map.removeLayer(overlay);
        currentMap.delete(id);
      }
    });

    // Add or update overlays
    layers.forEach((layer) => {
      let overlay = currentMap.get(layer.id);
      if (!overlay) {
        overlay = L.imageOverlay(layer.imageUrl, layer.bounds, {
          pane: 'geotiffPane',
          opacity: layer.opacity,
          interactive: true
        });
        if (layer.visible) {
          overlay.addTo(map);
        }
        currentMap.set(layer.id, overlay);
      } else {
        // Update opacity
        overlay.setOpacity(layer.opacity);
        // Update visibility
        const isAdded = map.hasLayer(overlay);
        if (layer.visible && !isAdded) {
          overlay.addTo(map);
        } else if (!layer.visible && isAdded) {
          map.removeLayer(overlay);
        }
      }
    });
  }, [map, layers]);

  // Zoom to a specific layer's bounds
  const fitLayer = useCallback(
    (layer: GeoTiffLayer) => {
      if (!map) return;
      map.fitBounds(layer.bounds, { padding: [40, 40], maxZoom: 16 });
    },
    [map]
  );

  return {
    map,
    cursor,
    fitLayer,
    zoomIn: () => map?.zoomIn(),
    zoomOut: () => map?.zoomOut(),
    setView: (c: LatLngTuple, z: number) => map?.setView(c, z)
  };
}
