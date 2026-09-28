import { fromBlob, fromArrayBuffer, type GeoTIFFImage } from 'geotiff';
import proj4 from 'proj4';
import type {
  GeoTiffBbox,
  GeoTiffLayer,
  GeoTiffMetadata,
  GeoTiffProcessState,
  GeoTiffWgs84Bounds
} from '../types/geotiff';

// Register standard projections in proj4
if (!proj4.defs('EPSG:4326')) {
  proj4.defs('EPSG:4326', '+proj=longlat +datum=WGS84 +no_defs');
}
if (!proj4.defs('EPSG:3857')) {
  proj4.defs(
    'EPSG:3857',
    '+proj=merc +a=6378137 +b=6378137 +lat_ts=0 +lon_0=0 +x_0=0 +y_0=0 +k=1 +units=m +nadgrids=@null +wktext +no_defs'
  );
}

// Common projections lookup
const COMMON_PROJ_DEFS: Record<number, string> = {
  4326: '+proj=longlat +datum=WGS84 +no_defs',
  3857: '+proj=merc +a=6378137 +b=6378137 +lat_ts=0 +lon_0=0 +x_0=0 +y_0=0 +k=1 +units=m +nadgrids=@null +wktext +no_defs',
  900913: '+proj=merc +a=6378137 +b=6378137 +lat_ts=0 +lon_0=0 +x_0=0 +y_0=0 +k=1 +units=m +nadgrids=@null +wktext +no_defs',
  4269: '+proj=longlat +datum=NAD83 +no_defs',
  27700: '+proj=tmerc +lat_0=49 +lon_0=-2 +k=0.9996012717 +x_0=400000 +y_0=-100000 +ellps=airy +datum=OSGB36 +units=m +no_defs',
  2154: '+proj=lcc +lat_1=49 +lat_2=44 +lat_0=46.5 +lon_0=3 +x_0=700000 +y_0=6600000 +ellps=GRS80 +units=m +no_defs',
  3413: '+proj=stere +lat_0=90 +lat_ts=70 +lon_0=-45 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs',
  3031: '+proj=stere +lat_0=-90 +lat_ts=-71 +lon_0=0 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs',
  25832: '+proj=utm +zone=32 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs',
  25833: '+proj=utm +zone=33 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs'
};

const COMPRESSION_NAMES: Record<number, string> = {
  1: 'None (Uncompressed)',
  2: 'CCITT 1D',
  3: 'Group 3 Fax',
  4: 'Group 4 Fax',
  5: 'LZW',
  6: 'JPEG (Old)',
  7: 'JPEG',
  8: 'Deflate / ZIP',
  32773: 'PackBits',
  34887: 'LERC',
  50000: 'ZSTD'
};

const PHOTOMETRIC_NAMES: Record<number, string> = {
  0: 'WhiteIsZero (Monochrome)',
  1: 'BlackIsZero (Grayscale)',
  2: 'RGB',
  3: 'Palette color',
  4: 'Transparency mask',
  5: 'CMYK',
  6: 'YCbCr',
  8: 'CIELab'
};

export function formatBytes(bytes: number): string {
  if (bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
}

/**
 * Resolves a proj4 definition for a given EPSG code or GeoKeys.
 */
export async function resolveProjDef(epsg: number | null): Promise<string | null> {
  if (!epsg) return null;

  if (COMMON_PROJ_DEFS[epsg]) {
    return COMMON_PROJ_DEFS[epsg];
  }

  // UTM Zones Northern hemisphere: EPSG:32601 - EPSG:32660
  if (epsg >= 32601 && epsg <= 32660) {
    const zone = epsg - 32600;
    return `+proj=utm +zone=${zone} +datum=WGS84 +units=m +no_defs`;
  }

  // UTM Zones Southern hemisphere: EPSG:32701 - EPSG:32760
  if (epsg >= 32701 && epsg <= 32760) {
    const zone = epsg - 32700;
    return `+proj=utm +zone=${zone} +south +datum=WGS84 +units=m +no_defs`;
  }

  // Check if already registered in proj4
  try {
    const def = proj4.defs(`EPSG:${epsg}`);
    if (def) return `EPSG:${epsg}`;
  } catch {
    // Continue
  }

  // Dynamic lookup fallback via epsg.io
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 4000);
    const res = await fetch(`https://epsg.io/${epsg}.proj4`, { signal: controller.signal });
    clearTimeout(timeoutId);
    if (res.ok) {
      const text = (await res.text()).trim();
      if (text.startsWith('+proj=')) {
        proj4.defs(`EPSG:${epsg}`, text);
        return text;
      }
    }
  } catch {
    // Network lookup failed or offline
  }

  return null;
}

/**
 * Extracts and validates geospatial metadata from a GeoTIFF image.
 */
export async function extractGeoTiffMetadata(
  image: GeoTIFFImage,
  fileName: string,
  fileSizeBytes: number
): Promise<GeoTiffMetadata> {
  const width = image.getWidth();
  const height = image.getHeight();
  const numBands = image.getSamplesPerPixel();

  // Inspect GeoKeys
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const geoKeys = (image.getGeoKeys?.() || {}) as Record<string, any>;
  const fileDir = (image as unknown as { fileDirectory: Record<string, unknown> }).fileDirectory || {};

  // Extract EPSG code
  let epsg: number | null = null;
  if (geoKeys.ProjectedCSTypeGeoKey && geoKeys.ProjectedCSTypeGeoKey !== 32767) {
    epsg = Number(geoKeys.ProjectedCSTypeGeoKey);
  } else if (geoKeys.GeographicTypeGeoKey && geoKeys.GeographicTypeGeoKey !== 32767) {
    epsg = Number(geoKeys.GeographicTypeGeoKey);
  }

  // Check ModelType
  const modelType = geoKeys.GTModelTypeGeoKey; // 1 = Projected, 2 = Geographic

  // CRS Citation / Name
  let crsName =
    geoKeys.GTCitationGeoKey ||
    geoKeys.GeogCitationGeoKey ||
    (epsg ? `EPSG:${epsg}` : modelType === 2 ? 'WGS 84 (Geographic)' : 'Unknown CRS');

  if (epsg && !crsName.includes(String(epsg))) {
    crsName = `${crsName} (EPSG:${epsg})`;
  }

  // If no EPSG but modelType is geographic (2), default to EPSG:4326
  if (!epsg && modelType === 2) {
    epsg = 4326;
  }

  // Resolve proj4 definition
  let proj4Def: string | null = null;
  if (epsg) {
    proj4Def = await resolveProjDef(epsg);
  }

  // Extract origin and resolution
  let origin: [number, number] = [0, 0];
  let resolution: [number, number] = [1, -1];
  try {
    const orig = image.getOrigin();
    if (orig && orig.length >= 2) {
      origin = [orig[0], orig[1]];
    }
  } catch {
    // Origin not found
  }

  try {
    const res = image.getResolution();
    if (res && res.length >= 2) {
      resolution = [res[0], res[1]];
    }
  } catch {
    // Resolution not found
  }

  // ModelTransformation (4x4 matrix) if present
  let modelTransformation: number[] | undefined;
  if (fileDir.ModelTransformation) {
    modelTransformation = Array.from(fileDir.ModelTransformation as Iterable<number>);
  }

  // Native Bounding Box
  let nativeBbox: GeoTiffBbox;
  try {
    const rawBbox = image.getBoundingBox();
    if (
      rawBbox &&
      rawBbox.length === 4 &&
      rawBbox.every((n) => typeof n === 'number' && !Number.isNaN(n) && Number.isFinite(n))
    ) {
      nativeBbox = {
        minX: rawBbox[0],
        minY: rawBbox[1],
        maxX: rawBbox[2],
        maxY: rawBbox[3]
      };
    } else {
      throw new Error('Bounding box returned invalid values');
    }
  } catch {
    // If getBoundingBox fails, calculate from origin & resolution
    if (origin[0] !== 0 || origin[1] !== 0 || resolution[0] !== 1 || resolution[1] !== -1) {
      const x1 = origin[0];
      const y1 = origin[1];
      const x2 = origin[0] + resolution[0] * width;
      const y2 = origin[1] + resolution[1] * height;
      nativeBbox = {
        minX: Math.min(x1, x2),
        minY: Math.min(y1, y2),
        maxX: Math.max(x1, x2),
        maxY: Math.max(y1, y2)
      };
    } else {
      throw new Error('This TIFF does not contain sufficient geospatial information to determine its geographic location.');
    }
  }

  // Validate that geospatial metadata is actually present
  const hasGeospatialData =
    Boolean(epsg) ||
    Boolean(modelType) ||
    Boolean(geoKeys.GTCitationGeoKey) ||
    Boolean(geoKeys.GeogCitationGeoKey) ||
    Boolean(fileDir.ModelTransformation) ||
    Boolean(fileDir.ModelTiepoint && fileDir.ModelPixelScale);

  if (!hasGeospatialData) {
    throw new Error('This TIFF does not contain sufficient geospatial information to determine its geographic location.');
  }

  // Check if native coordinates are already lat/lon (EPSG:4326)
  if (!epsg && nativeBbox.minX >= -180 && nativeBbox.maxX <= 180 && nativeBbox.minY >= -90 && nativeBbox.maxY <= 90) {
    epsg = 4326;
    proj4Def = COMMON_PROJ_DEFS[4326];
    crsName = 'WGS 84 (EPSG:4326)';
  }

  if (epsg && !proj4Def) {
    throw new Error(`The GeoTIFF uses CRS EPSG:${epsg}, which is currently unsupported for direct map rendering.`);
  }

  // Calculate 4 corners in native CRS
  const nativeCorners: [number, number][] = [];
  if (modelTransformation && modelTransformation.length >= 8) {
    const [a, b, , d, e, f, , h] = modelTransformation;
    const pixelCorners = [
      [0, 0],
      [width, 0],
      [width, height],
      [0, height]
    ];
    for (const [px, py] of pixelCorners) {
      nativeCorners.push([d + a * px + b * py, h + e * px + f * py]);
    }
  } else {
    nativeCorners.push([origin[0], origin[1]]); // Top-left
    nativeCorners.push([origin[0] + resolution[0] * width, origin[1]]); // Top-right
    nativeCorners.push([origin[0] + resolution[0] * width, origin[1] + resolution[1] * height]); // Bottom-right
    nativeCorners.push([origin[0], origin[1] + resolution[1] * height]); // Bottom-left
  }

  // Transform native coordinates to WGS84 (Lat, Lon)
  const lons: number[] = [];
  const lats: number[] = [];
  const corners: [number, number][] = []; // [lat, lon] tuples

  const isWgs84 = epsg === 4326;
  const isWebMercator = epsg === 3857 || epsg === 900913;

  for (const [nx, ny] of nativeCorners) {
    let lon = nx;
    let lat = ny;
    if (!isWgs84) {
      if (!proj4Def) {
        throw new Error(`Unable to reproject native coordinates without CRS definition for EPSG:${epsg}`);
      }
      try {
        const [pLon, pLat] = proj4(proj4Def, 'EPSG:4326', [nx, ny]);
        lon = pLon;
        lat = pLat;
      } catch (err) {
        throw new Error(`Projection error transforming coordinates: ${String(err)}`);
      }
    }

    if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
      throw new Error('Reprojected coordinates resulted in non-finite values.');
    }

    lons.push(lon);
    lats.push(lat);
    corners.push([lat, lon]);
  }

  // Also sample along the bounding box edges to ensure tight extent for curved projections
  if (!isWgs84 && proj4Def) {
    const edgeSamples = 5;
    for (let i = 1; i < edgeSamples; i++) {
      const frac = i / edgeSamples;
      const testPts = [
        [nativeBbox.minX + frac * (nativeBbox.maxX - nativeBbox.minX), nativeBbox.minY],
        [nativeBbox.minX + frac * (nativeBbox.maxX - nativeBbox.minX), nativeBbox.maxY],
        [nativeBbox.minX, nativeBbox.minY + frac * (nativeBbox.maxY - nativeBbox.minY)],
        [nativeBbox.maxX, nativeBbox.minY + frac * (nativeBbox.maxY - nativeBbox.minY)]
      ];
      for (const [sx, sy] of testPts) {
        try {
          const [tLon, tLat] = proj4(proj4Def, 'EPSG:4326', [sx, sy]);
          if (Number.isFinite(tLon) && Number.isFinite(tLat)) {
            lons.push(tLon);
            lats.push(tLat);
          }
        } catch {
          // ignore edge sample failure
        }
      }
    }
  }

  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);

  // Validate bounds
  if (minLat < -90 || maxLat > 90 || minLon < -360 || maxLon > 360) {
    throw new Error(
      `Computed geographic coordinates outside valid range: Lat [${minLat.toFixed(4)}, ${maxLat.toFixed(4)}], Lon [${minLon.toFixed(4)}, ${maxLon.toFixed(4)}]. Check the GeoTIFF CRS.`
    );
  }

  const wgs84Bounds: GeoTiffWgs84Bounds = {
    minLat: Math.max(-89.9, minLat),
    maxLat: Math.min(89.9, maxLat),
    minLon,
    maxLon
  };

  // Additional metadata
  const noData = fileDir.GDAL_NODATA ?? fileDir.NoData ?? null;
  const compressionCode = Number(fileDir.Compression ?? 1);
  const compression = COMPRESSION_NAMES[compressionCode] || `Type ${compressionCode}`;
  const photometricCode = Number(fileDir.PhotometricInterpretation ?? (numBands >= 3 ? 2 : 1));
  const photometric = PHOTOMETRIC_NAMES[photometricCode] || `Code ${photometricCode}`;

  let sampleFormat = 1;
  try {
    sampleFormat = image.getSampleFormat();
  } catch {
    // default uint
  }

  let bits = 8;
  try {
    const bps = fileDir.BitsPerSample;
    if (Array.isArray(bps)) bits = bps[0];
    else if (typeof bps === 'number') bits = bps;
  } catch {
    // default 8
  }

  let dataType = `uint${bits}`;
  if (sampleFormat === 2) dataType = `int${bits}`;
  else if (sampleFormat === 3) dataType = `float${bits}`;

  const hasAlpha = numBands === 4 || Boolean(fileDir.ExtraSamples);

  const warnings: string[] = [];
  if (width * height > 40_000_000) {
    warnings.push(`High resolution raster (${width} × ${height} px). Downsampled safely for fast interactive rendering.`);
  }

  return {
    fileName,
    fileSizeBytes,
    width,
    height,
    numBands,
    crsName,
    epsg,
    proj4Def,
    resolution,
    origin,
    nativeBbox,
    wgs84Bounds,
    corners,
    noData: noData !== null ? String(noData) : null,
    dataType,
    compression,
    photometric,
    hasAlpha,
    modelTransformation,
    warnings
  };
}

/**
 * Renders the GeoTIFF raster to an HTMLCanvasElement with accurate visual contrast
 * and reprojects onto WGS84 geographic coordinates if necessary.
 */
export async function renderGeoTiffRaster(
  image: GeoTIFFImage,
  metadata: GeoTiffMetadata,
  onProgress?: (progress: number, stage: string) => void
): Promise<{ canvas: HTMLCanvasElement; dataUrl: string }> {
  const origW = metadata.width;
  const origH = metadata.height;

  // Determine safe downsampled dimensions to keep canvas highly responsive and avoid memory limits
  const maxDim = 1536;
  let targetW = origW;
  let targetH = origH;
  if (origW > maxDim || origH > maxDim) {
    const scale = maxDim / Math.max(origW, origH);
    targetW = Math.max(64, Math.round(origW * scale));
    targetH = Math.max(64, Math.round(origH * scale));
  }

  onProgress?.(40, `Reading raster bands (${targetW} × ${targetH} preview)...`);

  // Read raster channels
  const rasters = await image.readRasters({
    width: targetW,
    height: targetH,
    interleave: false
  });

  if (!rasters || rasters.length === 0) {
    throw new Error('Unable to read raster data from GeoTIFF.');
  }

  onProgress?.(65, 'Processing color bands and contrast...');

  // Identify channels
  const numBands = rasters.length;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const band0 = rasters[0] as any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const band1 = (numBands > 1 ? rasters[1] : band0) as any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const band2 = (numBands > 2 ? rasters[2] : band0) as any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const band3 = (numBands > 3 ? rasters[3] : null) as any;

  // Check data ranges for automatic contrast scaling
  const sampleSize = Math.min(band0.length, 10000);
  const step = Math.max(1, Math.floor(band0.length / sampleSize));
  let minVal = Infinity;
  let maxVal = -Infinity;
  const noDataNum = metadata.noData !== null ? Number(metadata.noData) : NaN;

  for (let i = 0; i < band0.length; i += step) {
    const v = band0[i];
    if (!Number.isNaN(noDataNum) && v === noDataNum) continue;
    if (v < minVal) minVal = v;
    if (v > maxVal) maxVal = v;
  }

  if (minVal === Infinity || maxVal === -Infinity) {
    minVal = 0;
    maxVal = 255;
  }
  if (maxVal <= minVal) maxVal = minVal + 1;

  // Needs scaling if not standard uint8 (0-255)
  const needsScale = minVal < 0 || maxVal > 255 || metadata.dataType.includes('float') || metadata.dataType.includes('16');

  // Direct native canvas
  const nativeCanvas = document.createElement('canvas');
  nativeCanvas.width = targetW;
  nativeCanvas.height = targetH;
  const ctx = nativeCanvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) throw new Error('Could not create 2D canvas context');

  const imgData = ctx.createImageData(targetW, targetH);
  const buf = imgData.data;

  const isRgb = numBands >= 3;
  const hasAlpha = metadata.hasAlpha && band3 !== null;

  for (let i = 0; i < band0.length; i++) {
    const idx = i * 4;
    const v0 = band0[i];

    // Check NoData
    if (!Number.isNaN(noDataNum) && v0 === noDataNum) {
      buf[idx + 3] = 0;
      continue;
    }

    if (isRgb) {
      let r = v0;
      let g = band1[i];
      let b = band2[i];

      if (needsScale) {
        r = Math.min(255, Math.max(0, ((r - minVal) / (maxVal - minVal)) * 255));
        g = Math.min(255, Math.max(0, ((g - minVal) / (maxVal - minVal)) * 255));
        b = Math.min(255, Math.max(0, ((b - minVal) / (maxVal - minVal)) * 255));
      }

      buf[idx] = r;
      buf[idx + 1] = g;
      buf[idx + 2] = b;

      // Alpha
      if (hasAlpha) {
        buf[idx + 3] = band3[i];
      } else {
        // If pure black and nodata border
        if (r === 0 && g === 0 && b === 0 && (metadata.epsg !== 4326 || numBands > 3)) {
          // Keep solid or check context
          buf[idx + 3] = 255;
        } else {
          buf[idx + 3] = 255;
        }
      }
    } else {
      // Grayscale
      let gray = v0;
      if (needsScale) {
        gray = Math.min(255, Math.max(0, ((gray - minVal) / (maxVal - minVal)) * 255));
      }
      buf[idx] = gray;
      buf[idx + 1] = gray;
      buf[idx + 2] = gray;
      buf[idx + 3] = 255;
    }
  }

  ctx.putImageData(imgData, 0, 0);

  // If already EPSG:4326 (WGS84) and north-up, native canvas directly aligns with Leaflet bounds
  if (metadata.epsg === 4326 && !metadata.modelTransformation) {
    onProgress?.(90, 'Preparing raster overlay...');
    return {
      canvas: nativeCanvas,
      dataUrl: nativeCanvas.toDataURL('image/png')
    };
  }

  // If projected CRS (e.g. UTM, Web Mercator, etc.), reproject onto an axis-aligned WGS84 canvas
  onProgress?.(80, 'Reprojecting coordinates to map grid...');
  const projCanvas = document.createElement('canvas');
  projCanvas.width = targetW;
  projCanvas.height = targetH;
  const projCtx = projCanvas.getContext('2d');
  if (!projCtx) throw new Error('Could not create projected canvas context');

  const projImgData = projCtx.createImageData(targetW, targetH);
  const outBuf = projImgData.data;

  const { minLon, maxLon, minLat, maxLat } = metadata.wgs84Bounds;
  const lonSpan = maxLon - minLon;
  const latSpan = maxLat - minLat;

  const { minX, maxY } = metadata.nativeBbox;
  const resX = (metadata.nativeBbox.maxX - metadata.nativeBbox.minX) / targetW;
  const resY = (metadata.nativeBbox.maxY - metadata.nativeBbox.minY) / targetH;

  const projDef = metadata.proj4Def || 'EPSG:4326';
  const toNative = proj4('EPSG:4326', projDef);

  for (let py = 0; py < targetH; py++) {
    const lat = maxLat - (py / targetH) * latSpan;
    for (let px = 0; px < targetW; px++) {
      const lon = minLon + (px / targetW) * lonSpan;

      let natX = lon;
      let natY = lat;
      try {
        const [nx, ny] = toNative.forward([lon, lat]);
        natX = nx;
        natY = ny;
      } catch {
        continue;
      }

      // Map native coordinate to source pixel
      const sx = Math.floor((natX - minX) / resX);
      const sy = Math.floor((maxY - natY) / resY);

      if (sx >= 0 && sx < targetW && sy >= 0 && sy < targetH) {
        const srcIdx = (sy * targetW + sx) * 4;
        const outIdx = (py * targetW + px) * 4;

        outBuf[outIdx] = buf[srcIdx];
        outBuf[outIdx + 1] = buf[srcIdx + 1];
        outBuf[outIdx + 2] = buf[srcIdx + 2];
        outBuf[outIdx + 3] = buf[srcIdx + 3];
      }
    }
  }

  projCtx.putImageData(projImgData, 0, 0);

  onProgress?.(95, 'Finalizing image overlay...');
  return {
    canvas: projCanvas,
    dataUrl: projCanvas.toDataURL('image/png')
  };
}

/**
 * Main entry point: Parses an uploaded GeoTIFF file, extracts metadata,
 * transforms coordinates, renders raster, and returns a complete GeoTiffLayer.
 */
export async function loadGeoTiffFile(
  file: File,
  onStateChange?: (state: GeoTiffProcessState) => void
): Promise<GeoTiffLayer> {
  const fileName = file.name;
  const lower = fileName.toLowerCase();
  if (!lower.endsWith('.tif') && !lower.endsWith('.tiff')) {
    throw new Error('This file is not a valid GeoTIFF. Supported extensions: .tif, .tiff');
  }

  onStateChange?.({
    stage: 'reading',
    message: 'Reading GeoTIFF binary file...',
    progressPercent: 15
  });

  let tiff;
  try {
    const arrayBuffer = await file.arrayBuffer();
    tiff = await fromArrayBuffer(arrayBuffer);
  } catch (err) {
    throw new Error(`Unable to read this GeoTIFF. The file may be corrupted or incomplete. (${String(err)})`);
  }

  let image: GeoTIFFImage;
  try {
    image = await tiff.getImage();
  } catch (err) {
    throw new Error(`Failed to decode GeoTIFF image headers: ${String(err)}`);
  }

  onStateChange?.({
    stage: 'metadata',
    message: 'Reading geospatial metadata & CRS...',
    progressPercent: 30
  });

  const metadata = await extractGeoTiffMetadata(image, fileName, file.size);

  onStateChange?.({
    stage: 'crs',
    message: `Detected CRS: ${metadata.crsName}. Calculating geographic extent...`,
    progressPercent: 45
  });

  onStateChange?.({
    stage: 'rendering',
    message: 'Rendering raster channels...',
    progressPercent: 60
  });

  const { canvas, dataUrl } = await renderGeoTiffRaster(image, metadata, (percent, msg) => {
    onStateChange?.({
      stage: 'rendering',
      message: msg,
      progressPercent: percent
    });
  });

  const layer: GeoTiffLayer = {
    id: `geotiff-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    file,
    name: fileName,
    imageUrl: dataUrl,
    metadata,
    bounds: [
      [metadata.wgs84Bounds.minLat, metadata.wgs84Bounds.minLon],
      [metadata.wgs84Bounds.maxLat, metadata.wgs84Bounds.maxLon]
    ],
    visible: true,
    opacity: 0.9,
    canvasWidth: canvas.width,
    canvasHeight: canvas.height,
    createdAt: Date.now()
  };

  onStateChange?.({
    stage: 'success',
    message: `GeoTIFF loaded successfully (${metadata.crsName})`,
    progressPercent: 100
  });

  return layer;
}
