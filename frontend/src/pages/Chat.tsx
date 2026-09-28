import React, { useState, useRef, useEffect } from 'react';
import {
  PlusIcon,
  MessageSquareIcon,
  MapPinIcon,
  FileImageIcon,
  SendIcon,
  PaperclipIcon,
  MapIcon,
  RefreshCwIcon,
  AlertTriangleIcon,
  SparklesIcon,
  CheckCircle2Icon,
  LayersIcon
} from 'lucide-react';
import { useWorkspace } from '../contexts/WorkspaceContext';
import { useApp } from '../contexts/AppContext';
import { ChatConfigCard } from '../components/chat/ChatConfigCard';
import { ChatResult } from '../components/chat/ChatResult';
import { AnalysisResult } from '../components/AnalysisResult';
import type { AttachedImage } from '../types/app';
import { TASK_LABELS, describeAoi } from '../utils/geo';
import { formatBytes } from '../utils/files';

function getDynamicSuggestions(
  snapshot: any,
  isLoading: boolean,
  lastMsgIsUser: boolean
): string[] {
  if (isLoading || lastMsgIsUser || !snapshot) return [];
  const msgs = snapshot.messages || [];
  const assistantMsgs = msgs.filter((m: any) => m.role === 'assistant');
  if (assistantMsgs.length === 0) return [];
  const lastAsst = assistantMsgs[assistantMsgs.length - 1];
  const lastOp = snapshot.active_context?.last_operation?.type || '';
  const findings = lastAsst.findings || [];
  const hasBuildings = findings.some((f: any) => /building|structure|house/i.test(f.label || ''));
  const hasDetection = findings.length > 0;
  const hasMapAction = Boolean(lastAsst.mapAction);
  const wasProximity = lastOp === 'spatial_proximity' || /proximity|distance|buffer/i.test(lastAsst.content || '');

  const chips: string[] = [];

  if (hasBuildings) {
    chips.push('How many buildings did you find?');
    chips.push('What was the total number of buildings you originally detected?');
    const isGeotiff = (snapshot.datasets || []).some(
      (d: any) => (d.mime_type && d.mime_type.includes('tiff')) || (d.file_name && d.file_name.endsWith('.tif'))
    );
    if (isGeotiff) {
      chips.push('Which of those are close to roads?');
    }
  } else if (hasDetection) {
    const lbl = findings[0].label || 'feature';
    chips.push(`What is the confidence of the detected ${lbl}?`);
    chips.push('Show them on the map.');
  } else {
    // Optical Scene description or VQA (e.g. "describe this image")
    chips.push('What type of terrain or land cover is visible?');
    chips.push('Are there any prominent infrastructure or water features?');
    chips.push('Provide a detailed breakdown of this satellite scene.');
  }

  if (wasProximity) {
    chips.push('Use 500 meters instead.');
  }

  if (hasMapAction && !chips.includes('Show them on the map.')) {
    chips.push('Show them on the map.');
  }

  chips.push('Explain this result.');

  return chips.slice(0, 5);
}

export function Chat() {
  const { navigate } = useApp();
  const {
    chat,
    rerunChat,
    newAnalysis,
    conversationId,
    conversationSnapshot,
    isConversationLoading,
    conversationError,
    sendFollowUp,
    retryLastTurn,
    startAnalysis,
    attachments: workspaceAttachments
  } = useWorkspace();

  const [inputPrompt, setInputPrompt] = useState('');
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const threadEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages or loading updates
  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversationSnapshot?.messages, isConversationLoading]);

  const hasMessages = conversationSnapshot && conversationSnapshot.messages.length > 0;
  const messages = conversationSnapshot?.messages || [];
  const lastMsg = messages.length > 0 ? messages[messages.length - 1] : null;
  const lastMsgIsUser = Boolean(lastMsg && lastMsg.role === 'user');
  const pendingTask = conversationSnapshot?.pending_task;
  const datasets = conversationSnapshot?.datasets || [];
  const origDataset = datasets.find((d) => d.role === 'original');
  const compDataset = datasets.find((d) => d.role === 'comparison_input');

  const dynamicSuggestions = getDynamicSuggestions(
    conversationSnapshot,
    isConversationLoading,
    lastMsgIsUser
  );

  const handleSend = async (overridePrompt?: string) => {
    if (isConversationLoading) return;
    const textToSend = (overridePrompt ?? inputPrompt).trim();
    if (!textToSend && pendingFiles.length === 0) return;

    const filesToSend = pendingFiles;
    setInputPrompt('');
    setPendingFiles([]);

    if (!hasMessages && !conversationId) {
      await startAnalysis(textToSend, filesToSend.length > 0 ? filesToSend : undefined);
    } else {
      await sendFollowUp(textToSend, filesToSend.length > 0 ? filesToSend : undefined);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isConversationLoading) {
        void handleSend();
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const fl = Array.from(e.target.files);
      setPendingFiles((prev) => [...prev, ...fl]);
    }
  };

  return (
    <section className="page">
      <div className="chat-layout">
        {/* Section Header */}
        <div className="section-head">
          <div className="conversation-title-wrap">
            <div>
              <h2>{conversationSnapshot?.conversation.title || 'AI Analyst'}</h2>
              <p>Persistent multi-turn satellite analysis workspace</p>
            </div>
          </div>
          <button className="btn" onClick={newAnalysis} id="btn-new-analysis">
            <PlusIcon size={14} /> New analysis
          </button>
        </div>

        {/* Empty State when no conversation is active */}
        {!hasMessages && !chat ? (
          <div className="panel" style={{ padding: '40px 24px', textAlign: 'center' }}>
            <div style={{ maxWidth: '540px', margin: '0 auto' }}>
              <div
                style={{
                  width: '52px',
                  height: '52px',
                  borderRadius: '14px',
                  background: 'rgba(99, 102, 241, 0.12)',
                  display: 'grid',
                  placeItems: 'center',
                  margin: '0 auto 16px',
                  color: 'var(--accent)'
                }}
              >
                <MessageSquareIcon size={26} />
              </div>
              <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '8px' }}>
                Begin Conversational Satellite Analysis
              </h3>
              <p style={{ color: 'var(--muted)', fontSize: '14px', lineHeight: 1.5, marginBottom: '20px' }}>
                Enter your analytical question and attach satellite imagery below. SatQuery automatically captures your query and image as one submission, executes the specialized models, and enables follow-ups.
              </p>
            </div>
          </div>
        ) : (
          <div className="chat-thread">
            {/* Active Context Strip */}
            <div className="context-strip">
              <span style={{ fontWeight: 600, color: 'var(--text-strong)' }}>Active Context:</span>
              {origDataset && (
                <span className="context-tag">
                  <FileImageIcon size={13} />
                  Base: {origDataset.file_name}
                </span>
              )}
              {compDataset && (
                <span className="context-tag">
                  <LayersIcon size={13} />
                  Comparison: {compDataset.file_name}
                </span>
              )}
              {conversationSnapshot?.active_context?.original_result_id && (
                <span className="context-tag" style={{ color: 'var(--ok)' }}>
                  <CheckCircle2Icon size={13} />
                  Result Lineage Active
                </span>
              )}
            </div>

            {/* Contextual Pending Comparison Banner */}
            {pendingTask && (
              <div className="pending-task-banner">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <AlertTriangleIcon size={18} color="var(--accent)" />
                  <div>
                    <b>Comparison Task Pending:</b> {pendingTask.query || 'Temporal change comparison'}
                    <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '2px' }}>
                      Attach the earlier/second satellite image below to resume execution without retyping your query.
                    </div>
                  </div>
                </div>
                <button
                  className="btn primary"
                  style={{ whiteSpace: 'nowrap' }}
                  disabled={isConversationLoading}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <PaperclipIcon size={14} /> Attach Comparison Image
                </button>
              </div>
            )}

            {/* Multi-turn Messages Stream */}
            {hasMessages ? (
              conversationSnapshot.messages.map((m, mIdx) => {
                const isUser = m.role === 'user';
                const meta = m.metadata || {};
                const findingsCount = m.findings?.length ?? 0;
                const hasMapAction = Boolean(m.mapAction);

                // Detect if this assistant message is an analytical response that should use the cards
                const isAnalysis = !isUser && (
                  Boolean(
                    m.content && (
                      m.content.includes('## Direct Answer') ||
                      m.content.includes('## Image / Scene Type') ||
                      m.content.includes('## What Is Present') ||
                      m.content.includes('## Detailed Visual') ||
                      m.content.includes('## Supporting Model Evidence') ||
                      m.content.includes('## Technical Analysis Metadata') ||
                      m.content.includes('## ')
                    )
                  ) ||
                  Boolean(m.findings && m.findings.length > 0) ||
                  Boolean(m.sections && Object.keys(m.sections).length > 0) ||
                  meta.turn_action_type === 'new_analysis'
                );

                const prevUserMsg = !isUser
                  ? conversationSnapshot.messages
                      .slice(0, mIdx)
                      .reverse()
                      .find((msg) => msg.role === 'user')
                  : null;
                const turnQuery = prevUserMsg?.content || conversationSnapshot?.conversation.title || 'Satellite Scene Analysis';

                const activeAttachments: AttachedImage[] = (workspaceAttachments && workspaceAttachments.length > 0)
                  ? workspaceAttachments
                  : (conversationSnapshot?.datasets || []).map((d) => ({
                      id: d.id,
                      name: d.file_name,
                      url: `/api/assets/${d.file_name}`,
                      previewable: !d.file_name.toLowerCase().endsWith('.tif') && !d.file_name.toLowerCase().endsWith('.tiff'),
                      size: d.file_size,
                      type: d.mime_type || 'image/jpeg',
                      width: 0,
                      height: 0,
                      file: undefined as any,
                      image: null
                    }));

                return (
                  <div className="msg" key={m.id}>
                    <div className={`avatar ${isUser ? 'user' : 'ai'}`}>
                      {isUser ? 'U' : 'AI'}
                    </div>
                    <div className="msgbody">
                      <div className="who">
                        {isUser ? 'You' : `SatQuery AI · ${m.model || meta.model || 'Analyst Engine'}`}
                        {m.created_at && (
                          <span style={{ fontSize: '11px', color: 'var(--faint)', marginLeft: '8px', fontWeight: 'normal' }}>
                            {new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        )}
                      </div>

                      {isUser ? (
                        <div className="bubble">
                          <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{m.content}</div>
                        </div>
                      ) : isAnalysis ? (
                        <div className="bubble analysis-bubble" style={{ background: 'transparent', border: 'none', padding: 0 }}>
                          <AnalysisResult
                            result={{
                              summary: m.summary || m.content,
                              findings: m.findings || meta.findings || [],
                              sections: m.sections || meta.sections || {},
                              model: m.model || meta.model || 'InternVL3-2B',
                              validation: (m.validation || meta.validation || 'passed') as any,
                              metrics: meta.metrics || {},
                              decision_reason: meta.decision_reason
                            }}
                            query={turnQuery}
                            attachments={activeAttachments}
                            task={(meta.task || 'internvl') as any}
                          />

                          {hasMapAction && (
                            <div style={{ marginTop: '12px', display: 'flex', gap: '8px', alignItems: 'center' }}>
                              <button
                                className="btn small"
                                onClick={() => navigate('map')}
                                style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}
                              >
                                <MapIcon size={13} /> View on Interactive Map
                              </button>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="bubble">
                          <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{m.content}</div>

                          {findingsCount > 0 && (
                            <div style={{ marginTop: '10px', display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                              <span className="context-tag">
                                <b>{findingsCount}</b> verified features recorded
                              </span>
                              {hasMapAction && (
                                <button
                                  className="btn small"
                                  onClick={() => navigate('map')}
                                  style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}
                                >
                                  <MapIcon size={13} /> View on Interactive Map
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            ) : chat ? (
              /* Fallback single-turn legacy display */
              <>
                <div className="msg">
                  <div className="avatar user">U</div>
                  <div className="msgbody">
                    <div className="who">You</div>
                    <div className="bubble">{chat.query}</div>
                    {(chat.attachments.length > 0 || chat.aoi) && (
                      <div className="attachments">
                        {chat.attachments.map((a) => (
                          <div className="attachment" key={a.id}>
                            <div className="thumb">
                              {a.previewable ? <img src={a.url} alt={a.name} /> : <FileImageIcon size={20} />}
                            </div>
                            <b>{a.name}</b>
                            <small>{a.previewable ? `${a.width}×${a.height}` : 'Backend format'} · {formatBytes(a.size)}</small>
                          </div>
                        ))}
                        {chat.aoi && (
                          <div className="attachment">
                            <div className="thumb"><MapPinIcon size={20} /></div>
                            <b>Selected AOI</b>
                            <small>{describeAoi(chat.aoi)}</small>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                <div className="msg">
                  <div className="avatar ai">AI</div>
                  <div className="msgbody">
                    <div className="who">SatQuery AI</div>
                    <div className="bubble">
                      <b>{TASK_LABELS[chat.task]} task identified.</b>
                      <ChatConfigCard chat={chat} onRun={rerunChat} />
                    </div>
                  </div>
                </div>

                <ChatResult key={chat.historyId ?? chat.id} chat={chat} onRetry={rerunChat} />
              </>
            ) : null}

            {/* In-Flight Processing Indicator */}
            {isConversationLoading && (
              <div className="msg" id="msg-in-flight-loading">
                <div className="avatar ai">AI</div>
                <div className="msgbody">
                  <div className="who">SatQuery AI · Processing</div>
                  <div className="bubble" style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '14px 18px' }}>
                    <RefreshCwIcon size={18} className="spin" color="var(--accent)" />
                    <div>
                      <div style={{ fontWeight: 500, color: 'var(--text-strong)' }}>
                        Analyzing satellite imagery…
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '3px' }}>
                        Executing LangGraph multi-model routing, raster verification, and scientific response synthesis.
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Orphaned / Interrupted Turn Recovery Banner */}
            {lastMsgIsUser && !isConversationLoading && (
              <div
                className="recovery-banner"
                id="turn-recovery-banner"
                style={{
                  margin: '14px 0',
                  padding: '14px 18px',
                  background: 'rgba(99, 102, 241, 0.08)',
                  border: '1px solid rgba(99, 102, 241, 0.25)',
                  borderRadius: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '12px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <AlertTriangleIcon size={18} color="var(--accent)" />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '13px' }}>Analysis Pending for This Submission</div>
                    <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '2px' }}>
                      SatQuery has not yet executed the analytical model pipeline for &quot;{lastMsg?.content}&quot;.
                    </div>
                  </div>
                </div>
                <button
                  className="btn primary"
                  onClick={() => void retryLastTurn()}
                  id="btn-execute-pending-turn"
                  style={{ whiteSpace: 'nowrap' }}
                >
                  <SparklesIcon size={14} /> Execute Analysis
                </button>
              </div>
            )}

            {/* Safe Failure Notice */}
            {conversationError && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '12px 16px',
                  background: 'rgba(239, 102, 112, 0.12)',
                  border: '1px solid rgba(239, 102, 112, 0.3)',
                  borderRadius: '10px',
                  fontSize: '13px',
                  color: 'var(--text)'
                }}
              >
                <span>{conversationError}</span>
                <button
                  className="btn small"
                  onClick={() => {
                    if (lastMsgIsUser) {
                      void retryLastTurn();
                    } else {
                      void handleSend();
                    }
                  }}
                >
                  Retry
                </button>
              </div>
            )}

            <div ref={threadEndRef} />
          </div>
        )}

        {/* Permanent Chat Composer (Always Present across all states) */}
        <div className="chat-composer-sticky">
          {/* Pending Attached Files Preview */}
          {pendingFiles.length > 0 && (
            <div style={{ display: 'flex', gap: '8px', marginBottom: '8px', flexWrap: 'wrap' }}>
              {pendingFiles.map((f, i) => (
                <span key={i} className="context-tag" style={{ border: '1px solid var(--accent)' }}>
                  <PaperclipIcon size={12} />
                  {f.name} ({formatBytes(f.size)})
                  <button
                    type="button"
                    disabled={isConversationLoading}
                    onClick={() => setPendingFiles((prev) => prev.filter((_, idx) => idx !== i))}
                    style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', padding: 0 }}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}

          <div className="composer-input-row">
            <input
              type="file"
              ref={fileInputRef}
              style={{ display: 'none' }}
              multiple
              accept="image/*,.tif,.tiff"
              onChange={handleFileChange}
            />
            <button
              type="button"
              className="btn secondary"
              disabled={isConversationLoading}
              onClick={() => !isConversationLoading && fileInputRef.current?.click()}
              title={isConversationLoading ? 'Disabled during active analysis' : 'Attach imagery for analysis or comparison'}
              style={{
                height: '44px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                opacity: isConversationLoading ? 0.5 : 1,
                cursor: isConversationLoading ? 'not-allowed' : 'pointer'
              }}
              id="btn-attach-imagery"
            >
              <PaperclipIcon size={16} />
              <span className="hide-sm">Attach imagery</span>
            </button>

            <textarea
              className="composer-textarea"
              disabled={isConversationLoading}
              placeholder={
                isConversationLoading
                  ? 'Analyzing satellite imagery… follow-up submission will unlock upon completion.'
                  : pendingTask
                  ? 'Awaiting comparison image, or enter clarification query...'
                  : !hasMessages
                  ? 'Ask a question about the satellite imagery...'
                  : 'Ask a follow-up question or modify analytical parameters...'
              }
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              id="chat-composer-input"
            />

            <button
              type="button"
              className="btn primary"
              disabled={isConversationLoading || (!inputPrompt.trim() && pendingFiles.length === 0)}
              onClick={() => void handleSend()}
              style={{ height: '44px', width: '48px', display: 'grid', placeItems: 'center', padding: 0 }}
              id="btn-send-message"
            >
              {isConversationLoading ? <RefreshCwIcon size={16} className="spin" /> : <SendIcon size={16} />}
            </button>
          </div>

          {/* Quick Action Suggestion Chips - Only appear when analysis has finished and results are present */}
          {dynamicSuggestions.length > 0 && (
            <div className="suggestion-chips" id="active-suggestion-chips">
              <span style={{ fontSize: '11px', color: 'var(--muted)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                <SparklesIcon size={12} /> Suggested follow-ups:
              </span>
              {dynamicSuggestions.map((text) => (
                <button
                  key={text}
                  type="button"
                  className="chip-btn"
                  disabled={isConversationLoading}
                  onClick={() => void handleSend(text)}
                >
                  {text}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}