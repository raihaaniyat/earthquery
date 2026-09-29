import React, { useEffect, useState } from "react";
import {
  PlusIcon,
  HistoryIcon,
  Trash2Icon,
  FileTextIcon,
  DownloadIcon,
  ArrowLeftRightIcon,
  Clock3Icon,
  CrosshairIcon,
  ApertureIcon,
  FlameIcon,
  WavesIcon,
  SparklesIcon,
  ScanSearchIcon,
  MessageSquareIcon,
  ExternalLinkIcon,
  AlertCircleIcon,
  LayersIcon,
  type LucideIcon
} from "lucide-react";
import { useApp } from "../contexts/AppContext";
import { useWorkspace } from "../contexts/WorkspaceContext";
import { EmptyState } from "../components/EmptyState";
import { formatDateTime, createId } from "../utils/files";
import { downloadReport } from "../utils/report";
import { api } from "../utils/api";
import { HistoryStatus, TaskType, HistoryEntry, ReportEntry, ConversationItem } from "../types/app";

const TASK_ICON: Record<TaskType, LucideIcon> = {
  'change-detection': ArrowLeftRightIcon,
  temporal: Clock3Icon,
  'object-detection': CrosshairIcon,
  segmentation: ScanSearchIcon,
  'scene-description': ScanSearchIcon,
  spectral: ApertureIcon,
  fire: FlameIcon,
  water: WavesIcon,
  general: SparklesIcon,
  'optical-sar': LayersIcon
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
  const { toast } = useApp();
  const {
    history,
    reports,
    newAnalysis,
    removeHistory,
    clearHistory,
    createReport,
    loadConversation,
    deleteConversationById,
    conversationId
  } = useWorkspace();

  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [loadingConversations, setLoadingConversations] = useState(false);

  // Invariant 13: Opening history fetches lightweight metadata without model inference
  const fetchPersistedConversations = async () => {
    setLoadingConversations(true);
    try {
      const res = await api.listConversations();
      if (res.status === 'success') {
        setConversations(res.data);
      }
    } catch {
      // Backend may be offline in local mode
    } finally {
      setLoadingConversations(false);
    }
  };

  useEffect(() => {
    void fetchPersistedConversations();
  }, []);

  const handleDeleteConversation = async (id: string) => {
    await deleteConversationById(id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
  };

  const handleDownloadReport = (h: HistoryEntry) => {
    try {
      if (h.status === 'failed' && !h.summary && (!h.findings || h.findings.length === 0)) {
        toast('Cannot download report for a failed analysis with no output.', 'error');
        return;
      }

      let rep = reports.find((r) => r.entry.id === h.id);
      if (!rep) {
        rep = {
          id: createId(),
          createdAt: Date.now(),
          title: `${h.title} report`,
          entry: h
        };
      }

      downloadReport(rep);
      toast('Report downloaded successfully', 'success');
    } catch {
      toast('Failed to download report. Please try again.', 'error');
    }
  };

  return (
    <section className="page">
      <div className="section-head">
        <div>
          <h2>History & Resumable Conversations</h2>
          <p>Persisted multi-turn analyst conversations and historical analyses.</p>
        </div>
        <div className="section-actions">
          {history.length > 0 && (
            <button
              className="btn"
              onClick={() => {
                clearHistory();
                toast('Local history cleared');
              }}
            >
              Clear local history
            </button>
          )}
          <button className="btn primary" onClick={newAnalysis} id="btn-history-new-analysis">
            <PlusIcon size={14} /> New analysis
          </button>
        </div>
      </div>

      {/* 1. Persistent Analyst Conversations (Backend Authoritative) */}
      <div style={{ marginBottom: '28px' }}>
        <h3 style={{ fontSize: '15px', color: 'var(--text-strong)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <MessageSquareIcon size={16} color="var(--accent)" />
          Active Analyst Conversations
          {conversations.length > 0 && (
            <span style={{ fontSize: '12px', color: 'var(--muted)', fontWeight: 'normal' }}>
              ({conversations.length})
            </span>
          )}
        </h3>

        <div className="panel history-list">
          {conversations.length === 0 ? (
            <div style={{ padding: '24px', textAlign: 'center', color: 'var(--muted)', fontSize: '13px' }}>
              {loadingConversations ? 'Checking for active conversations…' : 'No persistent conversations recorded yet. Start an analysis to begin.'}
            </div>
          ) : (
            conversations.map((c) => {
              const isCurrent = c.id === conversationId;
              const dateStr = c.updated_at ? new Date(c.updated_at).toLocaleString() : 'Recently';

              return (
                <div
                  className="history-item"
                  key={c.id}
                  style={isCurrent ? { borderLeft: '3px solid var(--accent)', background: 'var(--surface-3)' } : {}}
                >
                  <div className="history-icon" style={{ background: 'var(--accent-soft)', color: 'var(--accent-ink)' }}>
                    <MessageSquareIcon size={16} />
                  </div>
                  <div className="history-main">
                    <b>{c.title || 'Untitled Conversation'}</b>
                    <p>
                      {c.message_count} turn{c.message_count === 1 ? '' : 's'} · {c.dataset_count} dataset{c.dataset_count === 1 ? '' : 's'} · Updated {dateStr}
                    </p>
                  </div>
                  <div className="history-actions">
                    {c.pending_task && (
                      <span className="badge warn" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <AlertCircleIcon size={11} /> Awaiting image
                      </span>
                    )}
                    <button
                      className="btn primary small"
                      onClick={() => void loadConversation(c.id)}
                      title="Resume multi-turn analyst conversation"
                      id={`btn-resume-conv-${c.id.slice(0, 8)}`}
                    >
                      <ExternalLinkIcon size={12} /> Open
                    </button>
                    <button
                      className="btn small"
                      onClick={() => void handleDeleteConversation(c.id)}
                      aria-label={`Delete conversation ${c.title}`}
                      id={`btn-delete-conv-${c.id.slice(0, 8)}`}
                    >
                      <Trash2Icon size={12} />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* 2. Local Session History Entries */}
      <h3 style={{ fontSize: '15px', color: 'var(--text-strong)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Clock3Icon size={16} />
        Single-Run Session Records ({history.length})
      </h3>

      <div className="panel history-list">
        {history.length === 0 ? (
          <EmptyState
            icon={HistoryIcon}
            title="No single-run analyses"
            text="Local single-run computations will appear here."
            action={<button className="btn primary" onClick={newAnalysis}>Start an analysis</button>}
          />
        ) : (
          history.map((h) => {
            const Icon = TASK_ICON[h.task];
            const badge = STATUS_BADGE[h.status];
            return (
              <div className="history-item" key={h.id}>
                <div className="history-icon"><Icon size={16} /></div>
                <div className="history-main">
                  <b>{h.title}</b>
                  <p>
                    “{h.query}” · {h.inputs.length ? `${h.inputs.length} input${h.inputs.length > 1 ? 's' : ''}` : 'No inputs'} · {h.model} · {formatDateTime(h.createdAt)}
                  </p>
                </div>
                <div className="history-actions">
                  <span className={`badge ${badge.tone}`}>{badge.label}</span>
                  <button
                    className="btn small"
                    onClick={() => createReport(h.id)}
                    title="Generate and view report preview"
                  >
                    <FileTextIcon size={12} /> Report
                  </button>
                  <button
                    className="btn small"
                    onClick={() => handleDownloadReport(h)}
                    title="Download complete scientific report file"
                  >
                    <DownloadIcon size={12} /> Download
                  </button>
                  <button
                    className="btn small"
                    onClick={() => removeHistory(h.id)}
                    aria-label={`Delete ${h.title}`}
                  >
                    <Trash2Icon size={12} />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}