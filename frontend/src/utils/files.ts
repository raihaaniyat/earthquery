import type { AttachedImage } from '../types/app';

export function createId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

import { loadGeoTiffAsAttachedImage } from './geotiff';

/**
 * Loads a local file into a first-class AttachedImage representation.
 * GeoTIFF files (.tif/.tiff) are automatically processed to generate visual raster previews,
 * extract CRS/dimensions/bands/SAR status, and preserve the original binary for analysis.
 */
export async function loadAttachedImage(file: File): Promise<AttachedImage> {
  const lower = file.name.toLowerCase();
  const isTiff = lower.endsWith('.tif') || lower.endsWith('.tiff') || file.type.includes('tiff');

  if (isTiff) {
    return loadGeoTiffAsAttachedImage(file);
  }

  const url = URL.createObjectURL(file);
  const base: AttachedImage = {
    id: createId(),
    name: file.name,
    size: file.size,
    type: file.type || 'image/png',
    url,
    file,
    width: 0,
    height: 0,
    previewable: false,
    image: null,
    isGeoTiff: false,
    previewStatus: 'loading'
  };

  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve({
      ...base,
      width: img.naturalWidth,
      height: img.naturalHeight,
      previewable: true,
      image: img,
      previewStatus: 'ready'
    });
    img.onerror = () => resolve({
      ...base,
      width: 0,
      height: 0,
      previewable: false,
      image: null,
      previewStatus: 'error',
      previewError: 'Browser could not decode image format.'
    });
    img.src = url;
  });
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function downloadFile(name: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function formatDateTime(ts: number): string {
  return new Date(ts).toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}