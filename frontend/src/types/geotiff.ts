export interface GeoTiffBbox {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

export interface GeoTiffWgs84Bounds {
  minLat: number;
  maxLat: number;
  minLon: number;
  maxLon: number;
}

export interface GeoTiffMetadata {
  fileName: string;
  fileSizeBytes: number;
  width: number;
  height: number;
  numBands: number;
  crsName: string;
  epsg: number | null;
  proj4Def: string | null;
  resolution: [number, number];
  origin: [number, number];
  nativeBbox: GeoTiffBbox;
  wgs84Bounds: GeoTiffWgs84Bounds;
  corners: [number, number][]; // [lat, lon] tuples
  noData: number | string | null;
  dataType: string;
  compression: string;
  photometric: string;
  hasAlpha: boolean;
  modelTransformation?: number[];
  warnings: string[];
}

export interface GeoTiffLayer {
  id: string;
  file: File;
  name: string;
  imageUrl: string;
  metadata: GeoTiffMetadata;
  bounds: [[number, number], [number, number]]; // Leaflet [[south, west], [north, east]]
  visible: boolean;
  opacity: number;
  canvasWidth: number;
  canvasHeight: number;
  createdAt: number;
}

export type GeoTiffProcessStage =
  | 'idle'
  | 'reading'
  | 'metadata'
  | 'crs'
  | 'rendering'
  | 'success'
  | 'error';

export interface GeoTiffProcessState {
  stage: GeoTiffProcessStage;
  message: string;
  progressPercent?: number;
  error?: string;
}
