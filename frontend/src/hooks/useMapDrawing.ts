import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { buildAoi, formatDistance, wrapLng } from '../utils/geo';
import type { Aoi, LatLngTuple, MapTool } from '../types/app';

interface Handlers {
  onAoi: (aoi: Aoi) => void;
  onInspect: (p: LatLngTuple) => void;
}

export interface DrawState {
  points: number;
  distanceKm: number | null;
}

const ACCENT = '#a56cff';

export function useMapDrawing(map: L.Map | null, tool: MapTool, handlers: Handlers) {
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;
  const [draw, setDraw] = useState<DrawState>({ points: 0, distanceKm: null });
  const finishRef = useRef<() => void>(() => undefined);
  const cancelRef = useRef<() => void>(() => undefined);

  useEffect(() => {
    if (!map) return;
    const pts: L.LatLng[] = [];
    let draft: L.Polyline | L.Polygon | L.Rectangle | null = null;
    let finalMeasure: L.Polyline | null = null;
    const container = map.getContainer();
    container.style.cursor = tool === 'select' ? '' : 'crosshair';
    const dblWasEnabled = map.doubleClickZoom.enabled();
    if (tool === 'polygon' || tool === 'measure') map.doubleClickZoom.disable();
    setDraw({ points: 0, distanceKm: null });

    const toTuple = (p: L.LatLng): LatLngTuple => [p.lat, wrapLng(p.lng)];
    const clearDraft = () => {
      if (draft) map.removeLayer(draft);
      draft = null;
    };
    const lengthKm = (list: L.LatLng[]) => {
      let d = 0;
      for (let i = 0; i < list.length - 1; i++) d += map.distance(list[i], list[i + 1]);
      return d / 1000;
    };
    const drawLine = (list: L.LatLng[], closed: boolean) => {
      clearDraft();
      const style = { color: ACCENT, weight: 2.5, dashArray: '6 5', interactive: false };
      draft = (closed && list.length > 2 ? L.polygon(list, { ...style, fillOpacity: 0.1 }) : L.polyline(list, style)) as any;
      draft?.addTo(map);
    };

    const reset = () => {
      pts.length = 0;
      clearDraft();
      setDraw({ points: 0, distanceKm: null });
    };

    const finish = () => {
      if (tool === 'polygon') {
        if (pts.length < 3) return;
        handlersRef.current.onAoi(buildAoi('polygon', pts.map(toTuple)));
        reset();
      } else if (tool === 'measure') {
        if (pts.length < 2) return;
        const km = lengthKm(pts);
        if (finalMeasure) map.removeLayer(finalMeasure);
        finalMeasure = L.polyline([...pts], { color: ACCENT, weight: 3, interactive: false }).addTo(map);
        finalMeasure.bindTooltip(formatDistance(km), { permanent: true, className: 'sq-tooltip', direction: 'top' }).openTooltip(pts[pts.length - 1]);
        pts.length = 0;
        clearDraft();
        setDraw({ points: 0, distanceKm: km });
      }
    };

    const isDuplicate = (p: L.LatLng) => {
      if (!pts.length) return false;
      const a = map.latLngToContainerPoint(pts[pts.length - 1]);
      const b = map.latLngToContainerPoint(p);
      return a.distanceTo(b) < 5;
    };

    const onClick = (e: L.LeafletMouseEvent) => {
      switch (tool) {
        case 'select':
          handlersRef.current.onInspect(toTuple(e.latlng));
          break;
        case 'point':
          handlersRef.current.onAoi(buildAoi('point', [toTuple(e.latlng)]));
          break;
        case 'rectangle':
          if (!pts.length) {
            pts.push(e.latlng);
            setDraw({ points: 1, distanceKm: null });
          } else {
            const b = L.latLngBounds(pts[0], e.latlng);
            const coords = [b.getNorthWest(), b.getNorthEast(), b.getSouthEast(), b.getSouthWest()].map(toTuple);
            handlersRef.current.onAoi(buildAoi('rectangle', coords));
            reset();
          }
          break;
        case 'polygon':
        case 'measure':
          if (isDuplicate(e.latlng)) return;
          if (tool === 'measure' && finalMeasure && !pts.length) {
            map.removeLayer(finalMeasure);
            finalMeasure = null;
          }
          pts.push(e.latlng);
          drawLine(pts, tool === 'polygon');
          setDraw({ points: pts.length, distanceKm: tool === 'measure' ? lengthKm(pts) : null });
          break;
      }
    };

    const onMove = (e: L.LeafletMouseEvent) => {
      if (!pts.length) return;
      if (tool === 'rectangle') {
        clearDraft();
        draft = L.rectangle(L.latLngBounds(pts[0], e.latlng), { color: ACCENT, weight: 2, dashArray: '6 5', fillOpacity: 0.1, interactive: false }).addTo(map);
      } else if (tool === 'polygon' || tool === 'measure') {
        const live = [...pts, e.latlng];
        drawLine(live, tool === 'polygon');
        if (tool === 'measure') setDraw({ points: pts.length, distanceKm: lengthKm(live) });
      }
    };

    const onDbl = (e: L.LeafletMouseEvent) => {
      if (tool !== 'polygon' && tool !== 'measure') return;
      L.DomEvent.stop(e);
      finish();
    };

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && pts.length) reset();
      if (e.key === 'Enter' && pts.length) finish();
    };

    map.on('click', onClick);
    map.on('mousemove', onMove);
    map.on('dblclick', onDbl);
    window.addEventListener('keydown', onKey);
    finishRef.current = finish;
    cancelRef.current = () => {
      reset();
      if (finalMeasure) {
        map.removeLayer(finalMeasure);
        finalMeasure = null;
      }
    };

    return () => {
      map.off('click', onClick);
      map.off('mousemove', onMove);
      map.off('dblclick', onDbl);
      window.removeEventListener('keydown', onKey);
      clearDraft();
      if (finalMeasure) map.removeLayer(finalMeasure);
      container.style.cursor = '';
      if (dblWasEnabled) map.doubleClickZoom.enable();
    };
  }, [map, tool]);

  return { draw, finish: () => finishRef.current(), cancel: () => cancelRef.current() };
}