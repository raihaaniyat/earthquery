export type PageId =
  | 'home'
  | 'chat'
  | 'geotiff'
  | 'analyze'
  | 'advanced'
  | 'temporal'
  | 'map'
  | 'comparison'
  | 'history'
  | 'reports';

export type Theme = 'dark' | 'light';

export type ModelId =
'Auto' |
'InternVL3' |
'GeoGround' |
'OWLv2' |
'ChangeFormerV6' |
'UPerNet' |
'CROMA' |
'ChangeVQA' |
'OpticalSAR';

export interface ModelSettings {
  model: ModelId;
  routing: 'auto' | 'manual';
  validation: boolean;
  comparisonMode: 'before-after' | 'single' | 'optical-sar' | 'multi-date';
  output: 'visual' | 'mask' | 'data';
}

export type TaskType =
'change-detection' |
'temporal' |
'object-detection' |
'segmentation' |
'scene-description' |
'spectral' |
'fire' |
'water' |
'general' |
'optical-sar';

export type AdvancedToolId = 'temporal' | 'spectral' | 'change' | 'measure' | 'fire' | 'water';

export type LatLngTuple = [number, number];
/** [west, south, east, north] in degrees */
export type BBox = [number, number, number, number];

export interface Aoi {
  type: 'point' | 'rectangle' | 'polygon';
  coordinates: LatLngTuple[];
  bbox: BBox;
  areaKm2: number;
  perimeterKm: number;
  centroid: LatLngTuple;
}

export type MapTool = 'select' | 'point' | 'rectangle' | 'polygon' | 'measure';
export type BasemapId = 'street' | 'satellite' | 'dark';
export type OverlayId = 'ndvi' | 'thermal' | 'sst';
export type ImageryLayerKey = 'optical' | 'sar' | 'gibs' | 'overlay';

export interface ImagerySettings {
  basemap: BasemapId;
  labels: boolean;
  optical: boolean;
  sar: boolean;
  gibs: boolean;
  overlay: OverlayId | null;
  opacity: Record<ImageryLayerKey, number>;
  /** Single observation date used by GIBS, overlays and the "after" side of compare */
  date: string;
  /** Date range used by scene search and Sentinel Hub rendering */
  startDate: string;
  endDate: string;
  compare: boolean;
  compareDate: string;
  showFootprints: boolean;
  showAoi: boolean;
}

import type { GeoTiffBbox, GeoTiffMetadata, GeoTiffWgs84Bounds } from './geotiff';

export interface AttachedImage {
  id: string;
  name: string;
  size: number;
  type: string;
  url: string;
  file: File;
  width: number;
  height: number;
  previewable: boolean;
  image: HTMLImageElement | null;
  // GeoTIFF & Geospatial extensions
  isGeoTiff?: boolean;
  isSar?: boolean;
  crs?: string;
  crsName?: string;
  epsg?: number | null;
  bounds?: [[number, number], [number, number]]; // Leaflet bounds
  wgs84Bounds?: GeoTiffWgs84Bounds;
  nativeBbox?: GeoTiffBbox;
  bands?: number;
  dataType?: string;
  metadata?: GeoTiffMetadata;
  previewStatus?: 'idle' | 'loading' | 'ready' | 'error';
  previewError?: string;
  mapImageUrl?: string;
}

export type ApiResult<T> =
{status: 'success';data: T;} |
{status: 'empty';message: string;} |
{status: 'error';message: string;code?: number;} |
{status: 'network';message: string;} |
{status: 'invalid';message: string;} |
{status: 'unconfigured';message: string;};

export type RequestState<T> = {status: 'idle';} | {status: 'loading';message?: string;} | ApiResult<T>;

export interface AnalysisFinding {
  label: string;
  detail: string;
  confidence?: number;
}

export interface ScientificSections {
  measured_from_raster?: string[];
  model_candidate?: {
    model: string;
    observation: string;
    validation: string;
  };
  interpretation_requiring_review?: string[];
}

export interface AnalysisResponse {
  summary: string;
  supporting_findings?: string[];
  findings?: AnalysisFinding[];
  maskUrl?: string;
  model?: string;
  participating_models?: string[];
  validation?: 'passed' | 'failed' | 'skipped' | string;
  metrics?: Record<string, string | number>;
  sections?: ScientificSections;
  decision_reason?: string;
}

export interface AnalysisRequest {
  task: TaskType;
  query: string;
  model: ModelId;
  routing: ModelSettings['routing'];
  validation: boolean;
  comparisonMode: ModelSettings['comparisonMode'];
  output: ModelSettings['output'];
  aoi: Aoi | null;
  date: string;
  dateRange: [string, string];
  layers: string[];
  mode?: string;
}

export interface SearchRequest {
  collection: string;
  bbox: BBox;
  start: string;
  end: string;
  maxCloud: number | null;
  limit?: number;
}

export interface ImageryRequest {
  source: 'sentinel-2' | 'sentinel-1' | 'gibs';
  bbox: BBox;
  date: string;
  dateRange?: [string, string];
  layer?: string;
}

export interface ImageryResponse {
  tileUrl?: string;
  imageUrl?: string;
  bounds?: BBox;
  acquired?: string;
}

export interface StacGeometry {
  type: string;
  coordinates: unknown;
}

export interface StacScene {
  id: string;
  collection: string;
  datetime: string;
  cloudCover: number | null;
  platform: string | null;
  bbox: BBox | null;
  geometry: StacGeometry | null;
  thumbnail: string | null;
}

export type HistoryStatus = 'complete' | 'local' | 'failed' | 'backend-unavailable';

export interface HistoryEntry {
  id: string;
  createdAt: number;
  task: TaskType;
  title: string;
  query: string;
  inputs: string[];
  model: string;
  status: HistoryStatus;
  summary: string;
  aoi: Aoi | null;
  findings: AnalysisFinding[];
  sections?: ScientificSections;
  metrics?: Record<string, string | number>;
  maskUrl?: string;
  decisionReason?: string;
  reportId?: string;
}

export interface ReportEntry {
  id: string;
  createdAt: number;
  title: string;
  entry: HistoryEntry;
}

export interface ChatSession {
  id: string;
  query: string;
  attachments: AttachedImage[];
  aoi: Aoi | null;
  task: TaskType;
  createdAt: number;
  run: RequestState<AnalysisResponse>;
  historyId: string | null;
}

export interface ComparisonPair {
  before: AttachedImage | null;
  after: AttachedImage | null;
}

export interface ConversationItem {
  id: string;
  title: string;
  state_revision: number;
  created_at: string | null;
  updated_at: string | null;
  message_count: number;
  dataset_count: number;
  pending_task?: any;
}

export interface ConversationMessageItem {
  id: string;
  conversation_id: string;
  turn_id?: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  client_request_id?: string;
  created_at: string | null;
  metadata?: Record<string, any>;
  summary?: string;
  supporting_findings?: string[];
  findings?: AnalysisFinding[];
  sections?: ScientificSections;
  model?: string;
  maskUrl?: string;
  mapAction?: any;
  validation?: string;
}

export interface ConversationDatasetItem {
  id: string;
  file_name: string;
  file_path: string;
  role: string;
  file_size: number;
  mime_type: string;
  acquisition_date: string | null;
  created_at: string | null;
}

export interface ConversationSnapshot {
  conversation: {
    id: string;
    title: string;
    state_revision: number;
    created_at: string | null;
    updated_at: string | null;
  };
  messages: ConversationMessageItem[];
  datasets: ConversationDatasetItem[];
  active_context: Record<string, any>;
  pending_task?: any;
  latest_map_action?: any;
}

export interface ConversationTurnResponse {
  conversation_id: string;
  turn_id: string;
  client_request_id: string;
  state_revision: number;
  user_message: {
    id: string;
    role: string;
    content: string;
    created_at: string | null;
  };
  assistant_message: {
    id: string;
    role: string;
    content: string;
    metadata: Record<string, any>;
    created_at: string | null;
  };
  summary: string;
  supporting_findings?: string[];
  findings: AnalysisFinding[];
  sections: ScientificSections;
  model: string;
  maskUrl?: string;
  mapAction?: any;
  pending_task?: any;
  active_context: Record<string, any>;
  status: string;
}