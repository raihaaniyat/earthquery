import { TASK_LABELS, describeAoi, formatBbox } from './geo';
import { formatDateTime, downloadFile } from './files';
import type { ReportEntry, HistoryEntry } from '../types/app';

const esc = (s: string) =>
  (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

const STATUS_TEXT: Record<string, string> = {
  complete: 'Complete',
  local: 'Local computation',
  failed: 'Failed',
  'backend-unavailable': 'Backend not connected'
};

export function markdownToHtml(md: string): string {
  if (!md) return '';
  const lines = md.split('\n');
  const out: string[] = [];
  let inList = false;

  for (const line of lines) {
    const trimmed = line.trim();

    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      if (!inList) {
        out.push('<ul>');
        inList = true;
      }
      const itemContent = formatInline(trimmed.slice(2));
      out.push(`<li>${itemContent}</li>`);
      continue;
    }

    if (inList) {
      out.push('</ul>');
      inList = false;
    }

    if (trimmed.startsWith('### ')) {
      out.push(`<h3>${formatInline(trimmed.slice(4))}</h3>`);
    } else if (trimmed.startsWith('## ')) {
      out.push(`<h2>${formatInline(trimmed.slice(3))}</h2>`);
    } else if (trimmed.startsWith('# ')) {
      out.push(`<h1>${formatInline(trimmed.slice(2))}</h1>`);
    } else if (trimmed === '') {
      // Empty line / paragraph break
    } else {
      out.push(`<p>${formatInline(trimmed)}</p>`);
    }
  }

  if (inList) {
    out.push('</ul>');
  }

  return out.join('\n');
}

function formatInline(text: string): string {
  // Pre-clean raw markdown glitches like **\*\* or duplicated bullet points
  let clean = (text || '')
    .replace(/\*{3,}/g, '**')
    .replace(/^[-*•\s]+/, '')
    .trim();

  let s = esc(clean);
  // Bold: **text**
  s = s.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Italic: *text*
  s = s.replace(/\*(.*?)\*/g, '<em>$1</em>');
  // Inline code: `code`
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  return s;
}

export function reportRows(r: ReportEntry): [string, string][] {
  const e = r.entry;
  const rows: [string, string][] = [
    ['Task', TASK_LABELS[e.task] || e.task],
    ['Query / Request', e.query || '—'],
    ['Input Imagery', e.inputs.length ? e.inputs.join(', ') : '—'],
    ['Analysis Engine', e.model || 'SatQuery Multi-Model Pipeline'],
    ['Execution Status', STATUS_TEXT[e.status] ?? e.status],
    ['Timestamp', formatDateTime(e.createdAt)]
  ];

  if (e.decisionReason) {
    rows.push(['Routing Reason', e.decisionReason]);
  }

  if (e.metrics) {
    if (e.metrics.duration_ms) {
      rows.push(['Execution Time', `${e.metrics.duration_ms} ms`]);
    }
    if (e.metrics.participating_models_count) {
      rows.push(['Models Executed', `${e.metrics.participating_models_count} verified models`]);
    }
  }

  if (e.aoi) {
    rows.push(['AOI Description', describeAoi(e.aoi)]);
    rows.push(['AOI Bounding Box', formatBbox(e.aoi.bbox)]);
  }

  return rows;
}

export function buildReportHtml(r: ReportEntry): string {
  const e = r.entry;
  const rows = reportRows(r)
    .map(([k, v]) => `<tr><th>${esc(k)}</th><td>${v}</td></tr>`)
    .join('');

  // Structured summary from markdown
  const summaryHtml = e.summary ? markdownToHtml(e.summary) : '<p>No narrative recorded for this analysis.</p>';

  // Scientific Evidence Sections (if available)
  let sectionsHtml = '';
  if (e.sections) {
    const s1 = (e.sections.measured_from_raster || []).map((m) => `<li>${esc(m)}</li>`).join('');
    const s2 = e.sections.model_candidate
      ? `<div>
          <p><strong>Lead Instrument:</strong> ${esc(e.sections.model_candidate.model)}</p>
          <p><strong>Candidate Observation:</strong> ${esc(e.sections.model_candidate.observation)}</p>
          <p><strong>Validation Status:</strong> <span class="badge ok">${esc(e.sections.model_candidate.validation)}</span></p>
        </div>`
      : '';
    const s3 = (e.sections.interpretation_requiring_review || []).map((m) => `<li>${esc(m)}</li>`).join('');

    sectionsHtml = `
      <section class="scientific-sections">
        <h2>Scientific Evidence & Separation of Facts</h2>
        <div class="sec-card">
          <h3>1. Measured from Raster (Deterministic Ground Truth)</h3>
          ${s1 ? `<ul>${s1}</ul>` : '<p class="muted">No physical raster measurements required for this query.</p>'}
        </div>
        ${s2 ? `
        <div class="sec-card">
          <h3>2. Specialist Model Candidates</h3>
          ${s2}
        </div>` : ''}
        <div class="sec-card">
          <h3>3. Limitations & Interpretations Requiring Review</h3>
          ${s3 ? `<ul>${s3}</ul>` : '<p class="muted">Standard remote sensing assumptions apply; verify with ground-truth data.</p>'}
        </div>
      </section>
    `;
  }

  // Findings Table
  let findingsHtml = '';
  if (e.findings && e.findings.length > 0) {
    const fRows = e.findings
      .map((f) => `
        <tr>
          <td><strong>${esc(f.label)}</strong></td>
          <td>${esc(f.detail)}</td>
          <td>${f.confidence !== undefined ? `${Math.round(f.confidence * 100)}%` : '—'}</td>
        </tr>
      `)
      .join('');

    findingsHtml = `
      <section>
        <h2>Extracted Features & Model Detections</h2>
        <table class="findings-table">
          <thead>
            <tr>
              <th style="width: 25%;">Feature / Classification</th>
              <th style="width: 60%;">Observation Detail</th>
              <th style="width: 15%;">Confidence</th>
            </tr>
          </thead>
          <tbody>${fRows}</tbody>
        </table>
      </section>
    `;
  }

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>${esc(r.title)} · SatQuery AI</title>
  <style>
    :root {
      --bg: #ffffff;
      --text: #1d192b;
      --muted: #6750a4;
      --line: #e7e0ec;
      --surface-2: #f7f2fa;
      --accent: #6750a4;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      font-size: 14px;
      line-height: 1.6;
      color: #24212a;
      max-width: 860px;
      margin: 40px auto;
      padding: 0 24px;
      background: #faf8fd;
    }
    .report-container {
      background: #ffffff;
      border: 1px solid #e7e0ec;
      border-radius: 12px;
      padding: 36px 40px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.04);
    }
    .header {
      border-bottom: 2px solid #6750a4;
      padding-bottom: 18px;
      margin-bottom: 24px;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
    }
    h1 { font-size: 24px; margin: 0 0 6px; color: #1d192b; font-weight: 700; }
    h2 { font-size: 17px; margin: 28px 0 12px; color: #322f37; border-bottom: 1px solid #e7e0ec; padding-bottom: 6px; }
    h3 { font-size: 15px; margin: 18px 0 8px; color: #49454f; }
    p.meta { color: #79747e; margin: 0; font-size: 13px; }
    .badge-satquery {
      background: #6750a4;
      color: white;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.5px;
    }
    table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 13.5px; }
    th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid #e7e0ec; vertical-align: top; }
    th { width: 200px; color: #49454f; font-weight: 600; background: #fdfbff; }
    .sec-card {
      background: #fdfbff;
      border: 1px solid #e7e0ec;
      border-radius: 8px;
      padding: 14px 18px;
      margin-bottom: 12px;
    }
    .sec-card h3 { margin-top: 0; color: #6750a4; font-size: 14px; }
    ul { margin: 6px 0 10px 20px; padding: 0; }
    li { margin-bottom: 4px; }
    code { background: #f4eff4; padding: 2px 5px; border-radius: 4px; font-family: monospace; font-size: 12px; }
    .badge { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 11.5px; font-weight: 600; }
    .badge.ok { background: #e8f5e9; color: #2e7d32; }
    .muted { color: #79747e; font-style: italic; }
    .findings-table thead th { background: #f3edf7; color: #49454f; }
    .footer {
      margin-top: 40px;
      padding-top: 14px;
      border-top: 1px solid #e7e0ec;
      text-align: center;
      color: #79747e;
      font-size: 12px;
    }
    @media print {
      body { background: white; margin: 0; padding: 0; max-width: 100%; }
      .report-container { border: none; box-shadow: none; padding: 0; }
    }
  </style>
</head>
<body>
  <div class="report-container">
    <div class="header">
      <div>
        <h1>${esc(r.title)}</h1>
        <p class="meta">SatQuery AI Scientific Analysis Report · Generated ${esc(formatDateTime(r.createdAt))}</p>
      </div>
      <div>
        <span class="badge-satquery">SatQuery AI</span>
      </div>
    </div>

    <section class="analysis-section">
      ${summaryHtml}
    </section>

    ${findingsHtml}

    ${sectionsHtml}

    <section style="margin-top: 32px; border-top: 2px solid #e7e0ec; padding-top: 20px;">
      <h2>Technical Analysis Metadata</h2>
      <table>${rows}</table>
    </section>

    <div class="footer">
      Generated automatically by SatQuery AI Scientific Analysis Pipeline · Local execution under isolated GPU runtime.
    </div>
  </div>
</body>
</html>`;
}

export function downloadReport(report: ReportEntry): void {
  const e = report.entry;
  const slug = (report.title || 'satquery-report').toLowerCase().replace(/[^a-z0-9]+/g, '-');
  const dateStr = new Date(e.createdAt || report.createdAt || Date.now()).toISOString().slice(0, 10);
  const filename = `${slug}-${dateStr}.html`;
  const htmlContent = buildReportHtml(report);
  downloadFile(filename, htmlContent, 'text/html');
}