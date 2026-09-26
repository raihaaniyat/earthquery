import { API_CONFIG, SATELLITE_SOURCES } from '../data/apiConfig';
import { clampBbox, validateDateRange } from './geo';
import type {
  AnalysisRequest,
  AnalysisResponse,
  ApiResult,
  BBox,
  ImageryRequest,
  ImageryResponse,
  ModelId,
  SearchRequest,
  StacGeometry,
  StacScene } from
'../types/app';

type Body = Record<string, unknown> | FormData;

const EMPTY_MESSAGE = 'No results were returned for this request.';

function isEmptyPayload(data: unknown): boolean {
  if (data == null) return true;
  if (Array.isArray(data)) return data.length === 0;
  if (typeof data === 'object') {
    const obj = data as Record<string, unknown>;
    for (const key of ['features', 'results', 'items']) {
      if (Array.isArray(obj[key]) && (obj[key] as unknown[]).length === 0) return true;
    }
  }
  return false;
}

async function readError(res: Response, fallback: string): Promise<string> {
  try {
    const text = await res.text();
    try {
      const json = JSON.parse(text) as {detail?: unknown;message?: unknown;error?: {message?: string}};
      if (typeof json.detail === 'string') return json.detail;
      if (typeof json.message === 'string') return json.message;
      if (json.error && typeof json.error.message === 'string') return json.error.message;
    } catch {
      if (text && text.length < 240) return text;
    }
  } catch {
    return fallback;
  }
  return fallback;
}

export async function fetchJson<T>(url: string, body?: Body, method: 'GET' | 'POST' = 'POST'): Promise<ApiResult<T>> {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    return { status: 'network', message: 'You appear to be offline. Check your connection and try again.' };
  }
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), API_CONFIG.timeoutMs);
  try {
    const isForm = body instanceof FormData;
    const res = await fetch(url, {
      method,
      signal: controller.signal,
      headers: body && !isForm ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? isForm ? body as FormData : JSON.stringify(body) : undefined
    });
    if (res.status === 400 || res.status === 422) {
      return { status: 'invalid', message: await readError(res, 'The request was rejected. Check the AOI, dates and inputs.') };
    }
    if (!res.ok) return { status: 'error', message: await readError(res, `Server responded with ${res.status}.`), code: res.status };
    if (res.status === 204) return { status: 'empty', message: EMPTY_MESSAGE };
    const data = (await res.json()) as T;
    if (isEmptyPayload(data)) return { status: 'empty', message: EMPTY_MESSAGE };
    return { status: 'success', data };
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      return { status: 'network', message: 'The request timed out. Try again or narrow the AOI and date range.' };
    }
    return { status: 'network', message: 'Could not reach the server. It may be offline or blocking cross-origin requests.' };
  } finally {
    window.clearTimeout(timer);
  }
}

/**
 * Calls the SatQuery backend through the Vite dev proxy.
 * Since baseUrl is empty and Vite proxies /api/*, we just use the endpoint path directly.
 */
export async function request<T>(endpoint: string, body?: Body, method: 'GET' | 'POST' = 'POST'): Promise<ApiResult<T>> {
  // With the Vite proxy, we use relative paths directly
  return fetchJson<T>(endpoint, body, method);
}

function withFiles(payload: object, files: File[]): Body {
  if (!files.length) return payload as Record<string, unknown>;
  const fd = new FormData();
  fd.append('payload', JSON.stringify(payload));
  files.forEach((f) => fd.append('images', f, f.name));
  return fd;
}

/* ── Map frontend ModelId → backend model id ── */
const MODEL_MAP: Record<string, string> = {
  'Auto': '',
  'InternVL3': 'internvl3',
  'GeoGround': 'geoground',
  'OWLv2': 'owlv2',
  'owlv2': 'owlv2',
  'ChangeFormerV6': 'changeformer',
  'UPerNet': 'upernet',
  'CROMA': 'croma',
  'ChangeVQA': 'change_vqa',
  'OpticalSAR': 'optical_sar_head',
};

/* ── Map frontend TaskType → backend task key for /api/dispatch ── */
const TASK_MAP: Record<string, string> = {
  'change-detection': 'change_detection',
  'temporal': 'change_detection',
  'object-detection': 'visual_grounding',
  'segmentation': 'segmentation',
  'scene-description': 'internvl',
  'spectral': 'internvl',
  'fire': 'internvl',
  'water': 'internvl',
  'general': 'internvl',
};

const E = API_CONFIG.endpoints;

/**
 * Checks backend connectivity by hitting the health endpoint.
 * Returns the raw health response on success.
 */
export async function checkHealth(): Promise<ApiResult<Record<string, unknown>>> {
  return fetchJson<Record<string, unknown>>(E.health, undefined, 'GET');
}

/**
 * Fetches the model capability matrix from the backend.
 */
export async function fetchCapabilities(): Promise<ApiResult<Record<string, unknown>>> {
  return fetchJson<Record<string, unknown>>(E.v1Capabilities, undefined, 'GET');
}

/**
 * Submits an analysis task through the LangGraph task router (/api/dispatch).
 * Transforms the frontend AnalysisRequest into the backend's dispatch contract.
 */
async function submitAnalysis(p: AnalysisRequest, files: File[]): Promise<ApiResult<AnalysisResponse>> {
  // If files are attached, use the v1 structured scene upload + job submission flow
  if (files.length > 0) {
    // Upload files first, then dispatch
    const fd = new FormData();
    fd.append('payload', JSON.stringify({
      task: TASK_MAP[p.task] || 'internvl',
      input_category: 'benchmark',
      pair_type: files.length >= 2 ? 'bitemporal' : 'single_image',
      prompt: p.query || 'Analyze this satellite imagery.',
      model: MODEL_MAP[p.model] || '',
    }));
    files.forEach((f) => fd.append('images', f, f.name));
    return request<AnalysisResponse>(E.analysis, fd);
  }

  // No files — dispatch with AOI/query only
  const body: Record<string, unknown> = {
    task: TASK_MAP[p.task] || 'internvl',
    input_category: 'benchmark',
    pair_type: 'single_image',
    prompt: p.query || 'Analyze this satellite imagery.',
    model: MODEL_MAP[p.model] || '',
  };
  if (p.aoi) {
    body.aoi = p.aoi;
  }
  return request<AnalysisResponse>(E.analysis, body);
}

export const api = {
  search:          (p: SearchRequest) => request<StacScene[]>(E.search, p as unknown as Record<string, unknown>),
  imagery:         (p: ImageryRequest) => request<ImageryResponse>(E.imagery, p as unknown as Record<string, unknown>),
  optical:         (p: ImageryRequest) => request<ImageryResponse>(E.optical, p as unknown as Record<string, unknown>),
  sar:             (p: ImageryRequest) => request<ImageryResponse>(E.sar, p as unknown as Record<string, unknown>),
  analysis:        (p: AnalysisRequest, files: File[] = []) => submitAnalysis(p, files),
  changeDetection: (p: AnalysisRequest, files: File[] = []) => submitAnalysis({ ...p, task: 'change-detection' }, files),
  prediction:      (p: AnalysisRequest, files: File[] = []) => submitAnalysis(p, files),
};

interface RawStacItem {
  id?: string;
  collection?: string;
  bbox?: number[];
  geometry?: StacGeometry | null;
  properties?: Record<string, unknown>;
  assets?: Record<string, {href?: string;}>;
}

function toScene(x: RawStacItem, fallbackCollection: string): StacScene {
  const p = x.properties ?? {};
  const cloud = p['eo:cloud_cover'];
  const thumb = x.assets?.thumbnail?.href ?? x.assets?.QUICKLOOK?.href ?? x.assets?.quicklook?.href ?? null;
  return {
    id: x.id ?? 'Unnamed scene',
    collection: x.collection ?? fallbackCollection,
    datetime: String(p.datetime ?? p.start_datetime ?? ''),
    cloudCover: typeof cloud === 'number' ? cloud : null,
    platform: typeof p.platform === 'string' ? p.platform : null,
    bbox: Array.isArray(x.bbox) && x.bbox.length >= 4 ? x.bbox.slice(0, 4) as BBox : null,
    geometry: x.geometry ?? null,
    thumbnail: thumb && /^https?:/.test(thumb) ? thumb : null
  };
}

/** Direct Copernicus Data Space STAC search (public, no key). Real scene metadata only. */
export async function searchStac(p: SearchRequest): Promise<ApiResult<StacScene[]>> {
  const dateError = validateDateRange(p.start, p.end);
  if (dateError) return { status: 'invalid', message: dateError };
  const bbox = clampBbox(p.bbox);
  if (bbox[0] >= bbox[2] || bbox[1] >= bbox[3]) return { status: 'invalid', message: 'The search area is not a valid bounding box.' };

  const res = await fetchJson<{features?: RawStacItem[];}>(SATELLITE_SOURCES.copernicusStac, {
    collections: [p.collection],
    bbox,
    datetime: `${p.start}T00:00:00Z/${p.end}T23:59:59Z`,
    limit: 50
  });
  if (res.status === 'network') {
    return { status: 'network', message: 'Could not reach Copernicus STAC. Check your connection or route the search through /api/search.' };
  }
  if (res.status !== 'success') return res.status === 'empty' ? { status: 'empty', message: 'No Sentinel scenes found for this area and date range.' } : res;

  let scenes = (res.data.features ?? []).map((f) => toScene(f, p.collection));
  if (p.maxCloud != null) scenes = scenes.filter((s) => s.cloudCover == null || s.cloudCover <= (p.maxCloud as number));
  scenes.sort((a, b) => b.datetime.localeCompare(a.datetime));
  scenes = scenes.slice(0, p.limit ?? 20);
  if (!scenes.length) return { status: 'empty', message: 'No Sentinel scenes matched this area, date range and cloud limit.' };
  return { status: 'success', data: scenes };
}