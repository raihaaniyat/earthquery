export interface DiffResult {
  changedPct: number;
  width: number;
  height: number;
  threshold: number;
}

export function drawImageCover(ctx: CanvasRenderingContext2D, img: HTMLImageElement, w: number, h: number): void {
  const s = Math.max(w / img.naturalWidth, h / img.naturalHeight);
  const nw = img.naturalWidth * s;
  const nh = img.naturalHeight * s;
  ctx.drawImage(img, (w - nw) / 2, (h - nh) / 2, nw, nh);
}

/**
 * Browser-side per-pixel RGB difference. Pixels above the threshold are painted in the accent
 * colour over a darkened grayscale of the BEFORE image. This is a visual comparison only.
 */
export function computeDifference(
before: HTMLImageElement,
after: HTMLImageElement,
canvas: HTMLCanvasElement,
threshold: number)
: DiffResult {
  const width = Math.min(1200, before.naturalWidth);
  const height = Math.max(1, Math.round(width * before.naturalHeight / before.naturalWidth));
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Canvas unavailable');

  const a = document.createElement('canvas');
  const b = document.createElement('canvas');
  a.width = b.width = width;
  a.height = b.height = height;
  const actx = a.getContext('2d');
  const bctx = b.getContext('2d');
  if (!actx || !bctx) throw new Error('Canvas unavailable');
  drawImageCover(actx, before, width, height);
  drawImageCover(bctx, after, width, height);

  const A = actx.getImageData(0, 0, width, height).data;
  const B = bctx.getImageData(0, 0, width, height).data;
  const out = ctx.createImageData(width, height);
  let changed = 0;
  for (let i = 0; i < A.length; i += 4) {
    const d = (Math.abs(A[i] - B[i]) + Math.abs(A[i + 1] - B[i + 1]) + Math.abs(A[i + 2] - B[i + 2])) / 3;
    if (d > threshold) {
      out.data[i] = 235;
      out.data[i + 1] = 110;
      out.data[i + 2] = 255;
      out.data[i + 3] = 235;
      changed++;
    } else {
      const g = (A[i] * 0.299 + A[i + 1] * 0.587 + A[i + 2] * 0.114) * 0.42;
      out.data[i] = g;
      out.data[i + 1] = g;
      out.data[i + 2] = g;
      out.data[i + 3] = 255;
    }
  }
  ctx.putImageData(out, 0, 0);
  return { changedPct: changed / (width * height) * 100, width, height, threshold };
}

/** Mean Excess Green index (2g − r − b on chromatic coordinates) — an RGB vegetation proxy, not NDVI. */
export function computeGreenness(img: HTMLImageElement): number {
  const w = 256;
  const h = Math.max(1, Math.round(w * img.naturalHeight / img.naturalWidth));
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  const ctx = c.getContext('2d');
  if (!ctx) return 0;
  ctx.drawImage(img, 0, 0, w, h);
  const d = ctx.getImageData(0, 0, w, h).data;
  let sum = 0;
  let n = 0;
  for (let i = 0; i < d.length; i += 4) {
    const t = d[i] + d[i + 1] + d[i + 2];
    if (t === 0) continue;
    sum += (2 * d[i + 1] - d[i] - d[i + 2]) / t;
    n++;
  }
  return n ? sum / n : 0;
}