import React from 'react';
import { CheckIcon, CircleIcon, LoaderCircleIcon, XIcon, ArrowRightIcon, RefreshCwIcon, CpuIcon } from 'lucide-react';
import { useApp } from '../../contexts/AppContext';
import { TASK_LABELS, describeAoi } from '../../utils/geo';
import type { ChatSession } from '../../types/app';

type Step = { label: string; state: 'ok' | 'pending' | 'loading' | 'bad'; note?: string; };

export function ChatConfigCard({ chat, onRun }: { chat: ChatSession; onRun: () => void; }) {
  const { openDrawer, modelSettings } = useApp();
  const run = chat.run.status;
  const imgs = chat.attachments.length;
  const hasGeotiff = chat.attachments.some(a => a.name.toLowerCase().endsWith('.tif') || a.name.toLowerCase().endsWith('.tiff'));
  const inputLabel = hasGeotiff
    ? (imgs >= 2 ? 'Dual GeoTIFF Rasters' : 'GeoTIFF Raster')
    : (imgs >= 2 ? 'Dual Benchmark Images' : imgs === 1 ? 'Benchmark Image' : chat.aoi ? 'Map AOI' : 'Text query');

  const steps: Step[] = [
    { label: 'Input sifter', state: 'ok', note: [imgs ? `${imgs} file${imgs > 1 ? 's' : ''} (${hasGeotiff ? 'GeoTIFF' : 'Pixel'})` : '', chat.aoi ? 'AOI' : ''].filter(Boolean).join(' + ') || 'Question only' },
    { label: 'Scientific intent', state: 'ok', note: TASK_LABELS[chat.task] },
    { label: 'Automatic routing', state: 'ok', note: modelSettings.model === 'Auto' ? 'Deterministic / Adaptive' : `Override: ${modelSettings.model}` },
    {
      label: 'Evidence validation',
      state: run === 'loading' ? 'loading' : run === 'success' ? 'ok' : run === 'idle' ? 'pending' : 'bad',
      note: run === 'success' ? 'Validated' : run === 'loading' ? 'Computing' : run === 'idle' ? 'Ready' : 'Not completed'
    }
  ];

  return (
    <div className="analysis-card">
      <div className="card-head">
        <b>Automatic scientific routing</b>
        <span className="spacer" />
        <button className="btn small" onClick={openDrawer} title="Diagnostic developer override">
          <CpuIcon size={12} /> Diagnostic
        </button>
      </div>
      <div className="card-body">
        <div className="chips">
          <span className="chip">Intent: {TASK_LABELS[chat.task]}</span>
          <span className="chip">Input: {inputLabel}</span>
          <span className="chip">Routing: {modelSettings.model === 'Auto' ? 'Automatic' : `Override (${modelSettings.model})`}</span>
          {chat.aoi && <span className="chip">AOI: {describeAoi(chat.aoi)}</span>}
        </div>

        {run === 'success' && 'data' in chat.run && chat.run.data.decision_reason && (
          <div style={{ fontSize: 12, padding: '6px 10px', background: 'rgba(99, 102, 241, 0.08)', borderRadius: 6, margin: '8px 0', color: 'var(--text-muted, #94a3b8)' }}>
            <b>Routing decision:</b> {chat.run.data.decision_reason}
          </div>
        )}

        <details className="trace">
          <summary>View scientific execution trace</summary>
          {steps.map((s) => (
            <div className="trace-row" key={s.label}>
              {s.state === 'ok' && <CheckIcon size={14} className="ok" />}
              {s.state === 'pending' && <CircleIcon size={14} className="pending" />}
              {s.state === 'loading' && <LoaderCircleIcon size={14} className="spin" />}
              {s.state === 'bad' && <XIcon size={14} className="bad" />}
              {s.label}
              {s.note && <em>{s.note}</em>}
            </div>
          ))}
        </details>
        <button className="btn green" style={{ marginTop: 8 }} onClick={onRun} disabled={run === 'loading'}>
          {run === 'idle' ? (
            <>Run analysis <ArrowRightIcon size={14} /></>
          ) : (
            <><RefreshCwIcon size={13} /> Run again</>
          )}
        </button>
      </div>
    </div>
  );
}