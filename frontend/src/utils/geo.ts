import { MAX_AOI_KM2 } from '../data/apiConfig';
import type { Aoi, BBox, LatLngTuple, TaskType } from '../types/app';

const EARTH_RADIUS = 6378137;
const toRad = (d: number) => d * Math.PI / 180;

export function wrapLng(lng: number): number {
  return ((lng + 180) % 360 + 360) % 360 - 180;
}

export function haversineKm(a: LatLngTuple, b: LatLngTuple): number {
  const dLat = toRad(b[0] - a[0]);
  const dLng = toRad(b[1] - a[1]);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a[0])) * Math.cos(toRad(b[0])) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS * Math.asin(Math.sqrt(h)) / 1000;
}

export function polygonAreaKm2(c: LatLngTuple[]): number {
  if (c.length < 3) return 0;
  let area = 0;
  for (let i = 0; i < c.length; i++) {
    const [lat1, lng1] = c[i];
    const [lat2, lng2] = c[(i + 1) % c.length];
    area += toRad(lng2 - lng1) * (2 + Math.sin(toRad(lat1)) + Math.sin(toRad(lat2)));
  }
  return Math.abs(area * EARTH_RADIUS * EARTH_RADIUS / 2) / 1e6;
}

export function pathLengthKm(c: LatLngTuple[], closed = false): number {
  let total = 0;
  for (let i = 0; i < c.length - 1; i++) total += haversineKm(c[i], c[i + 1]);
  if (closed && c.length > 2) total += haversineKm(c[c.length - 1], c[0]);
  return total;
}

export function bboxOf(c: LatLngTuple[]): BBox {
  const lats = c.map((p) => p[0]);
  const lngs = c.map((p) => p[1]);
  return [Math.min(...lngs), Math.min(...lats), Math.max(...lngs), Math.max(...lats)];
}

export function clampBbox(b: BBox): BBox {
  return [Math.max(-180, b[0]), Math.max(-90, b[1]), Math.min(180, b[2]), Math.min(90, b[3])];
}

export function buildAoi(type: Aoi['type'], coordinates: LatLngTuple[]): Aoi {
  const centroid: LatLngTuple = [
  coordinates.reduce((s, p) => s + p[0], 0) / coordinates.length,
  coordinates.reduce((s, p) => s + p[1], 0) / coordinates.length];

  return {
    type,
    coordinates,
    bbox: bboxOf(coordinates),
    areaKm2: type === 'point' ? 0 : polygonAreaKm2(coordinates),
    perimeterKm: type === 'point' ? 0 : pathLengthKm(coordinates, true),
    centroid
  };
}

export function aoiToGeoJson(aoi: Aoi): Record<string, unknown> {
  if (aoi.type === 'point') {
    return { type: 'Point', coordinates: [aoi.coordinates[0][1], aoi.coordinates[0][0]] };
  }
  const ring = aoi.coordinates.map(([lat, lng]) => [lng, lat]);
  ring.push(ring[0]);
  return { type: 'Polygon', coordinates: [ring] };
}

export function formatLatLng([lat, lng]: LatLngTuple): string {
  return `${Math.abs(lat).toFixed(4)}°${lat >= 0 ? 'N' : 'S'}, ${Math.abs(lng).toFixed(4)}°${lng >= 0 ? 'E' : 'W'}`;
}

export function formatBbox(b: BBox): string {
  return `${b[0].toFixed(4)}, ${b[1].toFixed(4)}, ${b[2].toFixed(4)}, ${b[3].toFixed(4)}`;
}

export function formatArea(km2: number): string {
  if (km2 === 0) return '—';
  if (km2 < 1) return `${(km2 * 100).toFixed(2)} ha`;
  return `${km2.toLocaleString(undefined, { maximumFractionDigits: km2 < 100 ? 2 : 0 })} km²`;
}

export function formatDistance(km: number): string {
  if (km < 1) return `${(km * 1000).toFixed(0)} m`;
  return `${km.toLocaleString(undefined, { maximumFractionDigits: 2 })} km`;
}

export function describeAoi(aoi: Aoi): string {
  if (aoi.type === 'point') return `Point ${formatLatLng(aoi.coordinates[0])}`;
  return `${aoi.type === 'rectangle' ? 'Rectangle' : 'Polygon'} · ${formatArea(aoi.areaKm2)}`;
}

export function validateAoi(aoi: Aoi | null): string | null {
  if (!aoi) return null;
  if (aoi.type === 'polygon' && aoi.coordinates.length < 3) return 'A polygon AOI needs at least three vertices.';
  if (aoi.areaKm2 > MAX_AOI_KM2)
  return `The AOI covers ${formatArea(aoi.areaKm2)}, above the ${MAX_AOI_KM2.toLocaleString()} km² limit. Draw a smaller area.`;
  return null;
}

export function todayIso(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

export function validateDate(date: string): string | null {
  if (!date) return 'Choose a date.';
  if (date > todayIso(0)) return 'The date cannot be in the future.';
  return null;
}

export function validateDateRange(start: string, end: string): string | null {
  if (!start || !end) return 'Choose both a start and end date.';
  if (start > end) return 'The start date must be before the end date.';
  if (end > todayIso(0)) return 'The end date cannot be in the future.';
  return null;
}

export function inferTask(query: string, imageCount: number): TaskType {
  const q = query.toLowerCase();
  if (/(optical.*sar|sar.*optical|\bfusion\b|\bcroma\b|\bsar\b|\bradar\b)/.test(q)) return 'optical-sar';
  if (/(over time|temporal|trend|season|time series|timeline)/.test(q)) return 'temporal';
  if (/(chang|before|after|differ|compare)/.test(q)) return 'change-detection';
  if (/(what is|image type|what does it have|what.*contain|describe|explain|tell me about|analyze scene)/.test(q)) return 'scene-description';
  if (/(building|vehicle|ship|detect|count|locate|where are|bounding box)/.test(q)) return 'object-detection';
  if (/(segment|land cover|classif)/.test(q)) return 'segmentation';
  if (/(fire|burn|hotspot|smoke)/.test(q)) return 'fire';
  if (/(water|flood|ocean|shore|river|lake)/.test(q)) return 'water';
  if (/(ndvi|spectral|band|index|vegetation)/.test(q)) return 'spectral';
  if (imageCount >= 2) return 'change-detection';
  if (imageCount === 1) return 'scene-description';
  return 'general';
}

export const TASK_LABELS: Record<TaskType, string> = {
  'change-detection': 'Change detection',
  temporal: 'Temporal analysis',
  'object-detection': 'Object detection',
  segmentation: 'Segmentation',
  'scene-description': 'Scene description',
  spectral: 'Spectral analysis',
  fire: 'Fire / hotspots',
  water: 'Water / ocean',
  general: 'General analysis',
  'optical-sar': 'Optical-SAR fusion analysis'
};