import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { useApp } from './AppContext';
import { usePersistentState } from '../hooks/usePersistentState';
import { api } from '../utils/api';
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
  startAnalysis: (query?: string) => void;
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
      findings: res.status === 'success' ? res.data.findings ?? [] : []
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
    (override?: string) => {
      const q = (override ?? query).trim();
      if (!q && attachments.length === 0 && !aoi) {
        toast('Enter a question, attach imagery, or select an AOI', 'error');
        return;
      }
      const finalQuery = q || 'Analyze this satellite imagery.';
      const session: ChatSession = {
        id: createId(),
        query: finalQuery,
        attachments: [...attachments],
        aoi,
        task: inferTask(finalQuery, attachments.length),
        createdAt: Date.now(),
        run: { status: 'idle' },
        historyId: null
      };
      setChat(session);
      navigate('chat');
      void executeChat(session);
    },
    [query, attachments, aoi, toast, navigate, executeChat]
  );

  const rerunChat = useCallback(() => {
    if (chat) void executeChat({ ...chat, task: chat.task });
  }, [chat, executeChat]);

  const newAnalysis = useCallback(() => {
    setQuery('');
    setAttachments([]);
    setChat(null);
    navigate('home');
  }, [navigate]);

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
      removeReport: (id) => setReports((prev) => prev.filter((r) => r.id !== id))
    }),
    [
    query, attachments, addFiles, removeAttachment, aoi, imagery, updateImagery, mapTool, activeTool, chat,
    startAnalysis, rerunChat, newAnalysis, comparisonPair, setComparisonPair, pendingDiff, temporalImages,
    addTemporalFiles, removeTemporalImage, buildRequest, history, logHistory, logResult, setHistory, reports,
    createReport, setReports]

  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error('useWorkspace must be used inside WorkspaceProvider');
  return ctx;
}