import { TASK_LABELS, describeAoi, formatBbox } from './geo';
import { formatDateTime } from './files';
import type { ReportEntry } from '../types/app';

const esc = (s: string) =>
s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

const STATUS_TEXT: Record<string, string> = {
  complete: 'Complete',
  local: 'Local computation',
  failed: 'Failed',
  'backend-unavailable': 'Backend not connected'
};

export function reportRows(r: ReportEntry): [string, string][] {
  const e = r.entry;
  const rows: [string, string][] = [
  ['Task', TASK_LABELS[e.task]],
  ['Query', e.query || '—'],
  ['Inputs', e.inputs.length ? e.inputs.join(', ') : '—'],
  ['Model', e.model],
  ['Status', STATUS_TEXT[e.status] ?? e.status],
  ['Run at', formatDateTime(e.createdAt)]];

  if (e.aoi) {
    rows.push(['AOI', describeAoi(e.aoi)]);
    rows.push(['AOI bbox (W,S,E,N)', formatBbox(e.aoi.bbox)]);
  }
  return rows;
}

export function buildReportHtml(r: ReportEntry): string {
  const rows = reportRows(r).
  map(([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).
  join('');
  const findings = r.entry.findings.length ?
  `<h2>Findings</h2><ul>${r.entry.findings.map((f) => `<li><b>${esc(f.label)}</b> — ${esc(f.detail)}</li>`).join('')}</ul>` :
  '';
  return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>${esc(r.title)}</title>
<style>body{font:14px/1.55 Inter,system-ui,sans-serif;color:#24212a;max-width:780px;margin:40px auto;padding:0 24px}
h1{font-size:22px;margin:0 0 4px}p.meta{color:#6e6878;margin:0 0 24px}table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:9px;border-bottom:1px solid #e3e1e8;vertical-align:top}th{width:180px;color:#6e6878;font-weight:600}
h2{font-size:16px;margin:28px 0 8px}</style></head><body>
<h1>${esc(r.title)}</h1><p class="meta">SatQuery AI report · generated ${esc(formatDateTime(r.createdAt))}</p>
<table>${rows}</table><h2>Summary</h2><p>${esc(r.entry.summary)}</p>${findings}</body></html>`;
}