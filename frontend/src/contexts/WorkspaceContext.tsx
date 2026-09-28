import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useApp } from './AppContext';
import { usePersistentState } from '../hooks/usePersistentState';
import { api, MODEL_MAP, TASK_MAP } from '../utils/api';
import { createId, loadAttachedImage } from '../utils/files';
import { TASK_LABELS, describeAoi, inferTask, todayIso, validateAoi } from '../utils/geo';
import type {
  AdvancedToolId,
  AnalysisRequest,
  AnalysisResponse,
  Aoi,
  ApiResult,
  AttachedImage,
  ChatSession,
  ComparisonPair,
  ConversationSnapshot,
  ConversationMessageItem,
  HistoryEntry,
  HistoryStatus,
  ImagerySettings,
  MapTool,
  ReportEntry,
  TaskType } from
'../types/app';

interface WorkspaceValue {
  query: string;
  setQuery: (q: string) => void;
  attachments: AttachedImage[];
  addFiles: (files: FileList | File[]) => Promise<void>;
  removeAttachment: (id: string) => void;
  aoi: Aoi | null;
  setAoi: (aoi: Aoi | null) => void;
  imagery: ImagerySettings;
  updateImagery: (patch: Partial<ImagerySettings>) => void;
  mapTool: MapTool;
  setMapTool: (t: MapTool) => void;
  activeTool: AdvancedToolId | null;
  setActiveTool: (t: AdvancedToolId | null) => void;
  chat: ChatSession | null;
  startAnalysis: (query?: string, files?: File[]) => Promise<void>;
  rerunChat: () => void;
  newAnalysis: () => void;
  comparisonPair: ComparisonPair;
  setComparisonPair: (p: ComparisonPair, runDiff?: boolean) => void;
  pendingDiff: boolean;
  clearPendingDiff: () => void;
  temporalImages: AttachedImage[];
  addTemporalFiles: (files: FileList | File[]) => Promise<void>;
  removeTemporalImage: (id: string) => void;
  buildRequest: (task: TaskType, query: string, extra?: Partial<AnalysisRequest>) => AnalysisRequest;
  history: HistoryEntry[];
  logHistory: (e: Omit<HistoryEntry, 'id' | 'createdAt' | 'model'> & {model?: string;}) => HistoryEntry;
  logResult: (task: TaskType, query: string, inputs: string[], res: ApiResult<AnalysisResponse>) => HistoryEntry;
  removeHistory: (id: string) => void;
  clearHistory: () => void;
  reports: ReportEntry[];
  createReport: (historyId: string) => void;
  removeReport: (id: string) => void;
  conversationId: string | null;
  conversationSnapshot: ConversationSnapshot | null;
  isConversationLoading: boolean;
  conversationError: string | null;
  latestMapAction: any | null;
  setLatestMapAction: (action: any | null) => void;
  loadConversation: (id: string) => Promise<void>;
  sendFollowUp: (prompt: string, newFiles?: File[]) => Promise<void>;
  retryLastTurn: () => Promise<void>;
  deleteConversationById: (id: string) => Promise<void>;
  newChat: () => void;
}

const WorkspaceContext = createContext<WorkspaceValue | null>(null);

const defaultImagery = (): ImagerySettings => ({
  basemap: 'street',
  labels: false,
  optical: true,
  sar: false,
  gibs: false,
  overlay: null,
  opacity: { optical: 0.85, sar: 0.8, gibs: 0.72, overlay: 0.75 },
  date: todayIso(-1),
  startDate: todayIso(-30),
  endDate: todayIso(0),
  compare: false,
  compareDate: todayIso(-31),
  showFootprints: true,
  showAoi: true
});

function statusOf(res: ApiResult<AnalysisResponse>): HistoryStatus {
  if (res.status === 'success') return 'complete';
  if (res.status === 'unconfigured') return 'backend-unavailable';
  return 'failed';
}

export function WorkspaceProvider({ children }: {children: React.ReactNode;}) {
  const { navigate, modelSettings, toast } = useApp();
  const [query, setQuery] = useState('');
  const [attachments, setAttachments] = useState<AttachedImage[]>([]);
  const [aoi, setAoi] = useState<Aoi | null>(null);
  const [imagery, setImagery] = useState<ImagerySettings>(defaultImagery);
  const [mapTool, setMapTool] = useState<MapTool>('select');
  const [activeTool, setActiveTool] = useState<AdvancedToolId | null>(null);
  const [chat, setChat] = useState<ChatSession | null>(null);
  const [comparisonPair, setPair] = useState<ComparisonPair>({ before: null, after: null });
  const [pendingDiff, setPendingDiff] = useState(false);
  const [temporalImages, setTemporalImages] = useState<AttachedImage[]>([]);
  const [history, setHistory] = usePersistentState<HistoryEntry[]>('satquery-history', []);
  const [reports, setReports] = usePersistentState<ReportEntry[]>('satquery-reports', []);

  // Multi-Turn Persistent Conversational Analyst state
  const [conversationId, setConversationId] = usePersistentState<string | null>('satquery-active-conv-id', null);
  const [conversationSnapshot, setConversationSnapshot] = useState<ConversationSnapshot | null>(null);
  const [isConversationLoading, setIsConversationLoading] = useState(false);
  const [conversationError, setConversationError] = useState<string | null>(null);
  const [latestMapAction, setLatestMapAction] = useState<any | null>(null);

  // Restore active conversation on page load / refresh (Invariant 10, Section 5, 26)
  useEffect(() => {
    if (conversationId && !conversationSnapshot) {
      setIsConversationLoading(true);
      api.getConversationSnapshot(conversationId).then((res) => {
        setIsConversationLoading(false);
        if (res.status === 'success') {
          setConversationSnapshot(res.data);
          if (res.data.latest_map_action) setLatestMapAction(res.data.latest_map_action);
        }
      }).catch(() => {
        setIsConversationLoading(false);
      });
    }
  }, [conversationId, conversationSnapshot]);

  const updateImagery = useCallback((patch: Partial<ImagerySettings>) => setImagery((p) => ({ ...p, ...patch })), []);

  const addFiles = useCallback(
    async (files: FileList | File[]) => {
      const list = Array.from(files).slice(0, 8);
      if (!list.length) return;
      const loaded = await Promise.all(list.map(loadAttachedImage));
      setAttachments((prev) => [...prev, ...loaded].slice(0, 8));
      toast(`${loaded.length} image${loaded.length > 1 ? 's' : ''} attached`);
    },
    [toast]
  );

  const removeAttachment = useCallback((id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  }, []);

  const addTemporalFiles = useCallback(
    async (files: FileList | File[]) => {
      const list = Array.from(files);
      if (!list.length) return;
      const loaded = await Promise.all(list.map(loadAttachedImage));
      setTemporalImages((prev) => [...prev, ...loaded]);
      toast(`${loaded.length} temporal image${loaded.length > 1 ? 's' : ''} loaded`);
    },
    [toast]
  );

  const removeTemporalImage = useCallback((id: string) => {
    setTemporalImages((prev) => prev.filter((a) => a.id !== id));
  }, []);

  const buildRequest = useCallback(
    (task: TaskType, q: string, extra?: Partial<AnalysisRequest>): AnalysisRequest => ({
      task,
      query: q,
      model: modelSettings.model,
      routing: modelSettings.routing,
      validation: modelSettings.validation,
      comparisonMode: modelSettings.comparisonMode,
      output: modelSettings.output,
      aoi,
      date: imagery.date,
      dateRange: [imagery.startDate, imagery.endDate],
      layers: [
      imagery.optical && 'sentinel-2',
      imagery.sar && 'sentinel-1',
      imagery.gibs && 'gibs-truecolor',
      imagery.overlay && `gibs-${imagery.overlay}`].
      filter((x): x is string => Boolean(x)),
      ...extra
    }),
    [modelSettings, aoi, imagery]
  );

  const logHistory = useCallback<WorkspaceValue['logHistory']>(
    (e) => {
      const entry: HistoryEntry = { ...e, id: createId(), createdAt: Date.now(), model: e.model ?? modelSettings.model };
      setHistory((prev) => [entry, ...prev].slice(0, 100));
      return entry;
    },
    [modelSettings.model, setHistory]
  );

  const logResult = useCallback<WorkspaceValue['logResult']>(
    (task, q, inputs, res) =>
    logHistory({
      task,
      title: TASK_LABELS[task],
      query: q,
      inputs,
      status: statusOf(res),
      summary: res.status === 'success' ? res.data.summary : 'message' in res ? res.message : '',
      aoi,
      findings: res.status === 'success' ? res.data.findings ?? [] : [],
      model: res.status === 'success' && res.data.model ? res.data.model : undefined,
      sections: res.status === 'success' ? res.data.sections : undefined,
      metrics: res.status === 'success' ? res.data.metrics : undefined,
      maskUrl: res.status === 'success' ? res.data.maskUrl : undefined,
      decisionReason: res.status === 'success' ? res.data.decision_reason : undefined
    }),
    [logHistory, aoi]
  );

  const executeChat = useCallback(
    async (session: ChatSession) => {
      const update = (patch: Partial<ChatSession>) =>
      setChat((s) => s && s.id === session.id ? { ...s, ...patch } : s);
      const imgs = session.attachments;
      const inputs = [...imgs.map((i) => i.name), ...(session.aoi ? [`AOI · ${describeAoi(session.aoi)}`] : [])];

      let invalid: string | null = validateAoi(session.aoi);
      if (!invalid && session.task === 'change-detection' && imgs.length < 2 && !session.aoi) {
        invalid = 'Change detection needs two images (before and after) or a selected AOI with a date range.';
      }
      if (!invalid && session.task === 'temporal' && imgs.length < 2 && !session.aoi) {
        invalid = 'Temporal analysis needs at least two dated images or a selected AOI.';
      }
      if (invalid) {
        update({ run: { status: 'invalid', message: invalid } });
        return;
      }

      update({ run: { status: 'loading', message: `Running ${TASK_LABELS[session.task].toLowerCase()}…` } });
      const req = buildRequest(session.task, session.query, { aoi: session.aoi });
      const files = imgs.map((i) => i.file);
      const res =
      session.task === 'change-detection' ?
      await api.changeDetection(req, files) :
      session.task === 'object-detection' || session.task === 'segmentation' ?
      await api.prediction(req, files) :
      await api.analysis(req, files);
      const entry = logResult(session.task, session.query, inputs, res);
      update({ run: res, historyId: entry.id });
    },
    [buildRequest, logResult]
  );

  const startAnalysis = useCallback(
    async (override?: string, filesOverride?: File[]) => {
      // Prevent double submissions
      if (isConversationLoading) return;

      const q = (override ?? query).trim();
      const imgs: AttachedImage[] = filesOverride && filesOverride.length > 0
        ? filesOverride.map((f) => ({
            id: createId(),
            name: f.name,
            size: f.size,
            type: f.type,
            file: f,
            url: URL.createObjectURL(f),
            width: 0,
            height: 0,
            previewable: f.type.startsWith('image/'),
            image: null
          }))
        : attachments;

      if (!q && imgs.length === 0 && !aoi) {
        toast('Enter a question, attach imagery, or select an AOI', 'error');
        return;
      }

      // Snapshot immutable values
      const finalQuery = q || 'Analyze this satellite imagery.';
      const filesToSubmit = [...imgs];
      // Always generate a fresh conversation ID for a new analysis session
      const newConvId = createId();
      const optimisticReqId = createId();

      // Clear composer drafts immediately so they don't linger
      setQuery('');
      setAttachments([]);

      setConversationId(newConvId);
      setIsConversationLoading(true);
      setConversationError(null);
      navigate('chat');

      // Optimistic initial user message
      const optimisticMsg: ConversationMessageItem = {
        id: createId(),
        conversation_id: newConvId,
        role: 'user',
        content: finalQuery,
        client_request_id: optimisticReqId,
        created_at: new Date().toISOString()
      };

      setConversationSnapshot({
        conversation: {
          id: newConvId,
          title: finalQuery.length > 38 ? finalQuery.slice(0, 38) + '...' : finalQuery,
          state_revision: 1,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        messages: [optimisticMsg],
        datasets: filesToSubmit.map((a) => ({
          id: a.id,
          file_name: a.name,
          file_path: a.url,
          role: 'original',
          file_size: a.size,
          mime_type: a.type || 'image/jpeg',
          acquisition_date: null,
          created_at: new Date().toISOString()
        })),
        active_context: {},
        pending_task: null
      });

      // Backward compatible session for legacy components
      const session: ChatSession = {
        id: newConvId,
        query: finalQuery,
        attachments: [...filesToSubmit],
        aoi,
        task: inferTask(finalQuery, filesToSubmit.length),
        createdAt: Date.now(),
        run: { status: 'loading', message: 'Analyzing scene with AI pipeline…' },
        historyId: null
      };
      setChat(session);

      const files = filesToSubmit.map((a) => a.file);
      try {
        const turnRes = await api.sendConversationMessage(newConvId, {
          prompt: finalQuery,
          client_request_id: optimisticReqId,
          task: TASK_MAP[session.task] || 'internvl',
          model: MODEL_MAP[modelSettings.model] || ''
        }, files.length > 0 ? files : undefined);

        setIsConversationLoading(false);
        if (turnRes.status === 'success') {
          // Immediately apply assistant message into conversation snapshot
          setConversationSnapshot((prev) => {
            const userMsg: ConversationMessageItem = {
              id: turnRes.data.user_message?.id || optimisticMsg.id,
              conversation_id: newConvId,
              role: 'user',
              content: turnRes.data.user_message?.content || optimisticMsg.content,
              client_request_id: optimisticReqId,
              created_at: turnRes.data.user_message?.created_at || optimisticMsg.created_at
            };
            const asstMsg: ConversationMessageItem | null = turnRes.data.assistant_message ? {
              id: turnRes.data.assistant_message.id,
              conversation_id: newConvId,
              role: 'assistant',
              content: turnRes.data.assistant_message.content,
              metadata: turnRes.data.assistant_message.metadata,
              created_at: turnRes.data.assistant_message.created_at,
              findings: turnRes.data.findings,
              sections: turnRes.data.sections,
              model: turnRes.data.model,
              maskUrl: turnRes.data.maskUrl,
              mapAction: turnRes.data.mapAction
            } : null;
            return {
              conversation: {
                id: newConvId,
                title: finalQuery.length > 38 ? finalQuery.slice(0, 38) + '...' : finalQuery,
                state_revision: turnRes.data.state_revision,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              },
              messages: [userMsg, ...(asstMsg ? [asstMsg] : [])],
              datasets: (prev?.datasets && prev.datasets.length > 0) ? prev.datasets : filesToSubmit.map((a) => ({
                id: a.id,
                file_name: a.name,
                file_path: a.url,
                role: 'original',
                file_size: a.size,
                mime_type: a.type || 'image/jpeg',
                acquisition_date: null,
                created_at: new Date().toISOString()
              })),
              active_context: turnRes.data.active_context || {},
              pending_task: turnRes.data.pending_task ?? null
            };
          });

          // Fetch canonical database snapshot to ensure persistence consistency
          const snapRes = await api.getConversationSnapshot(newConvId);
          if (snapRes.status === 'success') {
            setConversationSnapshot(snapRes.data);
            if (snapRes.data.latest_map_action) setLatestMapAction(snapRes.data.latest_map_action);
          }

          if (turnRes.data.mapAction) {
            setLatestMapAction(turnRes.data.mapAction);
          }

          logResult(session.task, finalQuery, filesToSubmit.map((a) => a.name), {
            status: 'success',
            data: {
              summary: turnRes.data.summary,
              findings: turnRes.data.findings,
              sections: turnRes.data.sections,
              model: turnRes.data.model,
              maskUrl: turnRes.data.maskUrl,
              metrics: turnRes.data.active_context?.last_operation?.parameters
            }
          });
          setChat({
            ...session,
            run: {
              status: 'success',
              data: {
                summary: turnRes.data.summary,
                findings: turnRes.data.findings,
                sections: turnRes.data.sections,
                model: turnRes.data.model,
                maskUrl: turnRes.data.maskUrl
              }
            }
          });
        } else {
          const errMsg = 'message' in turnRes ? turnRes.message : 'Error executing analysis';
          setConversationError(errMsg);
          toast(errMsg, 'error');
        }
      } catch (err: any) {
        setIsConversationLoading(false);
        const errMsg = err?.message || 'Network error executing analysis';
        setConversationError(errMsg);
        toast('Failed to complete analysis', 'error');
      }
    },
    [query, attachments, aoi, conversationId, isConversationLoading, toast, navigate, logResult, modelSettings, setConversationId]
  );

  const sendFollowUp = useCallback(
    async (promptText: string, newFiles?: File[]) => {
      if (!conversationId || isConversationLoading) return;
      const q = promptText.trim();
      if (!q && (!newFiles || newFiles.length === 0)) return;

      const reqId = createId();
      setIsConversationLoading(true);
      setConversationError(null);

      // Optimistic message
      const optimisticMsg: ConversationMessageItem = {
        id: createId(),
        conversation_id: conversationId,
        role: 'user',
        content: q || (newFiles && newFiles.length > 0 ? `Attached ${newFiles.length} file(s)` : ''),
        client_request_id: reqId,
        created_at: new Date().toISOString()
      };

      setConversationSnapshot((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          messages: [...prev.messages, optimisticMsg]
        };
      });

      try {
        const res = await api.sendConversationMessage(conversationId, {
          prompt: q,
          client_request_id: reqId,
          model: MODEL_MAP[modelSettings.model] || ''
        }, newFiles);

        setIsConversationLoading(false);
        if (res.status === 'success') {
          if (res.data.assistant_message) {
            setConversationSnapshot((prev) => {
              if (!prev) return prev;
              const filtered = prev.messages.filter((m) => m.client_request_id !== reqId);
              const userMsg: ConversationMessageItem = {
                id: res.data.user_message?.id || optimisticMsg.id,
                conversation_id: conversationId,
                role: 'user',
                content: res.data.user_message?.content || optimisticMsg.content,
                client_request_id: reqId,
                created_at: res.data.user_message?.created_at || optimisticMsg.created_at
              };
              const asstMsg: ConversationMessageItem = {
                id: res.data.assistant_message.id,
                conversation_id: conversationId,
                role: 'assistant',
                content: res.data.assistant_message.content,
                metadata: res.data.assistant_message.metadata,
                created_at: res.data.assistant_message.created_at,
                findings: res.data.findings,
                sections: res.data.sections,
                model: res.data.model,
                maskUrl: res.data.maskUrl,
                mapAction: res.data.mapAction
              };
              return {
                ...prev,
                conversation: {
                  ...prev.conversation,
                  state_revision: res.data.state_revision
                },
                messages: [...filtered, userMsg, asstMsg],
                active_context: res.data.active_context || prev.active_context,
                pending_task: res.data.pending_task ?? null
              };
            });
          }
          const snapRes = await api.getConversationSnapshot(conversationId);
          if (snapRes.status === 'success') {
            setConversationSnapshot(snapRes.data);
            if (snapRes.data.latest_map_action) {
              setLatestMapAction(snapRes.data.latest_map_action);
            }
          }
          if (res.data.mapAction) {
            setLatestMapAction(res.data.mapAction);
          }
        } else {
          const errMsg = 'message' in res ? res.message : 'Error processing follow-up';
          setConversationError(errMsg);
          toast(errMsg, 'error');
        }
      } catch (err: any) {
        setIsConversationLoading(false);
        setConversationError(err?.message || 'Network error');
        toast('Failed to send follow-up', 'error');
      }
    },
    [conversationId, isConversationLoading, modelSettings, toast]
  );

  const retryLastTurn = useCallback(
    async () => {
      if (!conversationId || isConversationLoading) return;
      const msgs = conversationSnapshot?.messages || [];
      if (msgs.length === 0) return;
      const lastMsg = msgs[msgs.length - 1];
      if (lastMsg.role !== 'user') return;

      const reqId = createId();
      setIsConversationLoading(true);
      setConversationError(null);

      try {
        const res = await api.sendConversationMessage(conversationId, {
          prompt: lastMsg.content,
          client_request_id: reqId,
          model: MODEL_MAP[modelSettings.model] || ''
        });

        setIsConversationLoading(false);
        if (res.status === 'success') {
          if (res.data.assistant_message) {
            setConversationSnapshot((prev) => {
              if (!prev) return prev;
              const asstMsg: ConversationMessageItem = {
                id: res.data.assistant_message.id,
                conversation_id: conversationId,
                role: 'assistant',
                content: res.data.assistant_message.content,
                metadata: res.data.assistant_message.metadata,
                created_at: res.data.assistant_message.created_at,
                findings: res.data.findings,
                sections: res.data.sections,
                model: res.data.model,
                maskUrl: res.data.maskUrl,
                mapAction: res.data.mapAction
              };
              return {
                ...prev,
                conversation: {
                  ...prev.conversation,
                  state_revision: res.data.state_revision
                },
                messages: [...prev.messages, asstMsg],
                active_context: res.data.active_context || prev.active_context,
                pending_task: res.data.pending_task ?? null
              };
            });
          }
          const snapRes = await api.getConversationSnapshot(conversationId);
          if (snapRes.status === 'success') {
            setConversationSnapshot(snapRes.data);
            if (snapRes.data.latest_map_action) {
              setLatestMapAction(snapRes.data.latest_map_action);
            }
          }
          if (res.data.mapAction) {
            setLatestMapAction(res.data.mapAction);
          }
          toast('Analysis complete', 'success');
        } else {
          const errMsg = 'message' in res ? res.message : 'Error executing analysis';
          setConversationError(errMsg);
          toast(errMsg, 'error');
        }
      } catch (err: any) {
        setIsConversationLoading(false);
        setConversationError(err?.message || 'Network error');
        toast('Failed to retry analysis', 'error');
      }
    },
    [conversationId, conversationSnapshot, isConversationLoading, modelSettings, toast]
  );

  const loadConversation = useCallback(
    async (id: string) => {
      setIsConversationLoading(true);
      setConversationError(null);
      setConversationId(id);
      try {
        const snapRes = await api.getConversationSnapshot(id);
        setIsConversationLoading(false);
        if (snapRes.status === 'success') {
          setConversationSnapshot(snapRes.data);
          if (snapRes.data.latest_map_action) {
            setLatestMapAction(snapRes.data.latest_map_action);
          }
          navigate('chat');
        } else {
          toast('Could not load conversation', 'error');
        }
      } catch {
        setIsConversationLoading(false);
        toast('Error loading conversation snapshot', 'error');
      }
    },
    [setConversationId, navigate, toast]
  );

  const deleteConversationById = useCallback(
    async (id: string) => {
      try {
        await api.deleteConversation(id);
        if (conversationId === id) {
          setConversationId(null);
          setConversationSnapshot(null);
        }
        toast('Conversation deleted', 'default');
      } catch {
        toast('Failed to delete conversation', 'error');
      }
    },
    [conversationId, setConversationId, toast]
  );

  const rerunChat = useCallback(() => {
    if (chat) void executeChat({ ...chat, task: chat.task });
  }, [chat, executeChat]);

  const newAnalysis = useCallback(() => {
    setQuery('');
    setAttachments([]);
    setChat(null);
    setConversationId(null);
    setConversationSnapshot(null);
    setConversationError(null);
    setLatestMapAction(null);
    navigate('home');
  }, [navigate, setConversationId]);

  const newChat = useCallback(() => {
    setQuery('');
    setAttachments([]);
    setChat(null);
    setConversationId(null);
    setConversationSnapshot(null);
    setConversationError(null);
    setLatestMapAction(null);
    navigate('chat');
  }, [navigate, setConversationId]);

  const setComparisonPair = useCallback((p: ComparisonPair, runDiff = false) => {
    setPair(p);
    setPendingDiff(runDiff);
  }, []);

  const createReport = useCallback(
    (historyId: string) => {
      const entry = history.find((h) => h.id === historyId);
      if (!entry) {
        toast('That analysis is no longer in history', 'error');
        return;
      }
      const report: ReportEntry = { id: createId(), createdAt: Date.now(), title: `${entry.title} report`, entry };
      setReports((prev) => [report, ...prev]);
      toast('Report generated', 'success');
    },
    [history, setReports, toast]
  );

  const value = useMemo<WorkspaceValue>(
    () => ({
      query,
      setQuery,
      attachments,
      addFiles,
      removeAttachment,
      aoi,
      setAoi,
      imagery,
      updateImagery,
      mapTool,
      setMapTool,
      activeTool,
      setActiveTool,
      chat,
      startAnalysis,
      rerunChat,
      newAnalysis,
      comparisonPair,
      setComparisonPair,
      pendingDiff,
      clearPendingDiff: () => setPendingDiff(false),
      temporalImages,
      addTemporalFiles,
      removeTemporalImage,
      buildRequest,
      history,
      logHistory,
      logResult,
      removeHistory: (id) => setHistory((prev) => prev.filter((h) => h.id !== id)),
      clearHistory: () => setHistory([]),
      reports,
      createReport,
      removeReport: (id) => setReports((prev) => prev.filter((r) => r.id !== id)),
      conversationId,
      conversationSnapshot,
      isConversationLoading,
      conversationError,
      latestMapAction,
      setLatestMapAction,
      loadConversation,
      sendFollowUp,
      retryLastTurn,
      deleteConversationById,
      newChat
    }),
    [
      query, attachments, addFiles, removeAttachment, aoi, imagery, updateImagery, mapTool, activeTool, chat,
      startAnalysis, rerunChat, newAnalysis, comparisonPair, setComparisonPair, pendingDiff, temporalImages,
      addTemporalFiles, removeTemporalImage, buildRequest, history, logHistory, logResult, setHistory, reports,
      createReport, setReports, conversationId, conversationSnapshot, isConversationLoading, conversationError,
      latestMapAction, setLatestMapAction, loadConversation, sendFollowUp, retryLastTurn, deleteConversationById,
      newChat
    ]
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error('useWorkspace must be used inside WorkspaceProvider');
  return ctx;
}