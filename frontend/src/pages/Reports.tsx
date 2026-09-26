import React, { useState } from 'react';
import { PlusIcon, FileTextIcon, EyeIcon, DownloadIcon, Trash2Icon, PrinterIcon } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { useApp } from '../contexts/AppContext';
import { useWorkspace } from '../contexts/WorkspaceContext';
import { EmptyState } from '../components/EmptyState';
import { buildReportHtml, reportRows } from '../utils/report';
import { downloadFile, formatDateTime } from '../utils/files';
import type { ReportEntry } from '../types/app';

export function Reports() {
  const { navigate, toast } = useApp();
  const { reports, history, createReport, removeReport } = useWorkspace();
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [source, setSource] = useState<string>('');

  const selected = source || history[0]?.id || '';
  const slug = (r: ReportEntry) => r.title.toLowerCase().replace(/[^a-z0-9]+/g, '-');

  const exportReport = (r: ReportEntry) => {
    downloadFile(`${slug(r)}-${new Date(r.createdAt).toISOString().slice(0, 10)}.html`, buildReportHtml(r), 'text/html');
    toast('Report exported', 'success');
  };

  const printReport = (r: ReportEntry) => {
    const w = window.open('', '_blank');
    if (!w) return toast('Allow pop-ups to print the report', 'error');
    w.document.write(buildReportHtml(r));
    w.document.close();
    w.focus();
    w.print();
  };

  return (
    <section className="page">
      <div className="section-head">
        <div>
          <h2>Reports</h2>
          <p>Generate and manage analysis reports from your history.</p>
        </div>
        <div className="section-actions">
          {history.length > 0 &&
          <select value={selected} onChange={(e) => setSource(e.target.value)} style={{ width: 'auto', maxWidth: 280 }} aria-label="Analysis to report on">
              {history.map((h) =>
            <option key={h.id} value={h.id}>
                  {h.title} · {formatDateTime(h.createdAt)}
                </option>
            )}
            </select>
          }
          <button className="btn green" disabled={!selected} onClick={() => createReport(selected)}>
            <PlusIcon size={14} /> Generate report
          </button>
        </div>
      </div>

      <div className="panel history-list">
        {reports.length === 0 ?
        <EmptyState
          icon={FileTextIcon}
          title="No reports yet"
          text={history.length ? 'Choose an analysis above and generate a report you can preview, print or export.' : 'Run an analysis first — reports are built from your analysis history.'}
          action={!history.length ? <button className="btn primary" onClick={() => navigate('home')}>Start an analysis</button> : undefined} /> :


        reports.map((r) =>
        <div className="history-item" key={r.id}>
              <div className="history-icon">HTML</div>
              <div className="history-main">
                <b>{r.title}</b>
                <p>
                  {formatDateTime(r.createdAt)} · {r.entry.inputs.length} input{r.entry.inputs.length === 1 ? '' : 's'} · {r.entry.model}
                </p>
              </div>
              <div className="history-actions">
                <button className="btn small" onClick={() => setPreviewId(previewId === r.id ? null : r.id)} aria-expanded={previewId === r.id}>
                  <EyeIcon size={12} /> {previewId === r.id ? 'Hide' : 'Preview'}
                </button>
                <button className="btn small" onClick={() => printReport(r)}>
                  <PrinterIcon size={12} /> Print
                </button>
                <button className="btn small" onClick={() => exportReport(r)}>
                  <DownloadIcon size={12} /> Export
                </button>
                <button className="btn small" onClick={() => removeReport(r.id)} aria-label={`Delete ${r.title}`}>
                  <Trash2Icon size={12} />
                </button>
              </div>
              <AnimatePresence initial={false}>
                {previewId === r.id &&
            <motion.div
              className="report-preview"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2, ease: [0.23, 1, 0.32, 1] }}
              style={{ overflow: 'hidden' }}>
              
                    <table>
                      <tbody>
                        {reportRows(r).map(([k, v]) =>
                  <tr key={k}>
                            <th>{k}</th>
                            <td>{v}</td>
                          </tr>
                  )}
                        <tr>
                          <th>Summary</th>
                          <td>{r.entry.summary}</td>
                        </tr>
                        {r.entry.findings.map((f, i) =>
                  <tr key={i}>
                            <th>{i === 0 ? 'Findings' : ''}</th>
                            <td>
                              <b>{f.label}</b> — {f.detail}
                            </td>
                          </tr>
                  )}
                      </tbody>
                    </table>
                  </motion.div>
            }
              </AnimatePresence>
            </div>
        )
        }
      </div>
    </section>);

}