import React from "react";
import { PlusIcon, HistoryIcon, Trash2Icon, FileTextIcon, ArrowLeftRightIcon, Clock3Icon, CrosshairIcon, ApertureIcon, FlameIcon, WavesIcon, SparklesIcon, ScanSearchIcon, type LucideIcon } from "lucide-react";
import { useApp } from "../contexts/AppContext";
import { useWorkspace } from "../contexts/WorkspaceContext";
import { EmptyState } from "../components/EmptyState";
import { formatDateTime } from "../utils/files";
import { HistoryStatus, TaskType } from "../types/app";
const TASK_ICON: Record<TaskType, LucideIcon> = {
  'change-detection': ArrowLeftRightIcon,
  temporal: Clock3Icon,
  'object-detection': CrosshairIcon,
  segmentation: ScanSearchIcon,
  'scene-description': ScanSearchIcon,
  spectral: ApertureIcon,
  fire: FlameIcon,
  water: WavesIcon,
  general: SparklesIcon
};
export const STATUS_BADGE: Record<HistoryStatus, {
  label: string;
  tone: string;
}> = {
  complete: {
    label: 'Complete',
    tone: 'ok'
  },
  local: {
    label: 'Local result',
    tone: 'accent'
  },
  failed: {
    label: 'Failed',
    tone: 'bad'
  },
  'backend-unavailable': {
    label: 'Backend not connected',
    tone: 'warn'
  }
};
export function History() {
  const {
    toast
  } = useApp();
  const {
    history,
    newAnalysis,
    removeHistory,
    clearHistory,
    createReport
  } = useWorkspace();
  return <section className="page">
      <div className="section-head">
        <div>
          <h2>History</h2>
          <p>Analyses run in this browser, including local computations and backend requests.</p>
        </div>
        <div className="section-actions">
          {history.length > 0 && <button className="btn" onClick={() => {
          clearHistory();
          toast('History cleared');
        }}>
              Clear history
            </button>}
          <button className="btn" onClick={newAnalysis}>
            <PlusIcon size={14} /> New analysis
          </button>
        </div>
      </div>

      <div className="panel history-list">
        {history.length === 0 ? <EmptyState icon={HistoryIcon} title="No analyses yet" text="Run an analysis from the AI Analyst, Imagery, Temporal or Advanced pages and it will appear here." action={<button className="btn primary" onClick={newAnalysis}>Start an analysis</button>} /> : history.map((h) => {
        const Icon = TASK_ICON[h.task];
        const badge = STATUS_BADGE[h.status];
        return <div className="history-item" key={h.id}>
                <div className="history-icon"><Icon size={16} /></div>
                <div className="history-main">
                  <b>{h.title}</b>
                  <p>
                    “{h.query}” · {h.inputs.length ? `${h.inputs.length} input${h.inputs.length > 1 ? 's' : ''}` : 'No inputs'} · {h.model} · {formatDateTime(h.createdAt)}
                  </p>
                </div>
                <div className="history-actions">
                  <span className={`badge ${badge.tone}`}>{badge.label}</span>
                  <button className="btn small" onClick={() => createReport(h.id)}>
                    <FileTextIcon size={12} /> Report
                  </button>
                  <button className="btn small" onClick={() => removeHistory(h.id)} aria-label={`Delete ${h.title}`}>
                    <Trash2Icon size={12} />
                  </button>
                </div>
              </div>;
      })}
      </div>
    </section>;
}