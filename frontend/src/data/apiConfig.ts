import type { BasemapId, OverlayId, AdvancedToolId } from '../types/app';

/**
 * Centralized backend configuration.
 *
 * `baseUrl` is empty because the Vite dev-server proxies `/api/*` to the
 * FastAPI backend on port 8000 — see vite.config.ts.  In production the
 * reverse-proxy does the same, so browser code never needs an absolute origin.
 *
 * The `endpoints` map is intentionally matched to the FastAPI route tree.
 * Legacy routes live under `/api/…`, structured v1 routes under `/api/v1/…`.
 */
export const API_CONFIG = {
  /** Leave empty: the Vite proxy (dev) or reverse-proxy (prod) handles routing. */
  baseUrl: '',
  timeoutMs: 300_000,  // 5 min — accommodates large raster uploads (e.g. 300MB S2 GeoTIFFs) + multi-model inference
  endpoints: {
    /* ── Backend-direct routes (FastAPI main.py legacy mounts) ── */
    health:          '/api/health',
    models:          '/api/models',
    dispatch:        '/api/dispatch',
    validateGeotiff: '/api/validate/geotiff',

    /* ── Frontend-facing bridge routes (added for new frontend) ── */
    search:          '/api/search',
    imagery:         '/api/imagery',
    optical:         '/api/optical',
    sar:             '/api/sar',
    analysis:        '/api/analysis',
    changeDetection: '/api/change-detection',
    prediction:      '/api/prediction',

    /* ── V1 structured API ── */
    v1Capabilities:  '/api/v1/capabilities',
    v1Projects:      '/api/v1/projects',
    v1AnalysisJobs:  '/api/v1/analysis-jobs',
  }
} as const;

/**
 * Public satellite data sources used directly by the map.
 * `sentinelHubInstanceId` enables dated Sentinel-2 and Sentinel-1 (SAR) rendering via
 * a Copernicus Data Space Sentinel Hub configuration instance. Layer ids must match that instance.
 */
export const SATELLITE_SOURCES = {
  copernicusStac: 'https://stac.dataspace.copernicus.eu/v1/search',
  sentinelHubWms: 'https://sh.dataspace.copernicus.eu/ogc/wms/',
  sentinelHubInstanceId: '',
  sentinelHubLayers: { optical: 'TRUE_COLOR', sar: 'VV' },
  s2Mosaic: 'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2021_3857/default/g/{z}/{y}/{x}.jpg',
  s2MosaicAttribution:
  'Sentinel-2 cloudless 2021 by EOX IT Services GmbH (contains modified Copernicus Sentinel data)',
  gibsWms: 'https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi',
  gibsTrueColor: 'MODIS_Terra_CorrectedReflectance_TrueColor'
} as const;

export const STAC_COLLECTIONS = {
  optical: 'sentinel-2-l2a',
  sar: 'sentinel-1-grd'
} as const;

export interface BasemapConfig {
  id: BasemapId;
  label: string;
  url: string;
  attribution: string;
  maxZoom: number;
  subdomains?: string;
}

export const BASEMAPS: BasemapConfig[] = [
{
  id: 'street',
  label: 'Street',
  url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  attribution: '© OpenStreetMap contributors',
  maxZoom: 19
},
{
  id: 'satellite',
  label: 'Satellite',
  url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  attribution: 'Tiles © Esri — Maxar, Earthstar Geographics',
  maxZoom: 19
},
{
  id: 'dark',
  label: 'Dark',
  url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
  attribution: '© OpenStreetMap contributors © CARTO',
  maxZoom: 20,
  subdomains: 'abcd'
}];


export const LABELS_LAYER = {
  url: 'https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png',
  attribution: '© CARTO',
  subdomains: 'abcd'
};

export interface OverlayConfig {
  id: OverlayId;
  label: string;
  layer: string;
  tool: AdvancedToolId;
  source: string;
}

/** NASA GIBS science products used by the specialist tools. */
export const ANALYSIS_OVERLAYS: OverlayConfig[] = [
{
  id: 'ndvi',
  label: 'Vegetation index (NDVI 8-day)',
  layer: 'MODIS_Terra_NDVI_8Day',
  tool: 'spectral',
  source: 'NASA GIBS · MODIS Terra'
},
{
  id: 'thermal',
  label: 'Thermal anomalies / fire',
  layer: 'MODIS_Terra_Thermal_Anomalies_All',
  tool: 'fire',
  source: 'NASA GIBS · MODIS Terra'
},
{
  id: 'sst',
  label: 'Sea surface temperature',
  layer: 'GHRSST_L4_MUR_Sea_Surface_Temperature',
  tool: 'water',
  source: 'NASA GIBS · GHRSST MUR'
}];


export const MAX_AOI_KM2 = 250000;