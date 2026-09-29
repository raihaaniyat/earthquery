import React, { useEffect, useRef, useState } from 'react';
import { MapIcon, CrosshairIcon, ArrowRightIcon, SparklesIcon, XIcon } from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import { useWorkspace } from '../contexts/WorkspaceContext';
import { StateNotice } from '../components/StateNotice';
import { AnalysisResult } from '../components/AnalysisResult';
import { advancedTools } from '../data/advancedTools';
import { ANALYSIS_OVERLAYS } from '../data/apiConfig';
import { api } from '../utils/api';
import { TASK_LABELS, describeAoi, validateAoi, validateDate } from '../utils/geo';
import type { AdvancedToolId, AnalysisResponse, RequestState, TaskType } from '../types/app';

const TOOL_TASK: Partial<Record<AdvancedToolId, TaskType>> = { spectral: 'spectral', fire: 'fire', water: 'water' };

export function Advanced() {
  const { navigate } = useApp();
  const { activeTool, setActiveTool, setMapTool, aoi, setAoi, imagery, updateImagery, setQuery, buildRequest, logResult } = useWorkspace();
  const [run, setRun] = useState<RequestState<AnalysisResponse>>({ status: 'idle' });
  const panelRef = useRef<HTMLDivElement>(null);

  const task = activeTool ? TOOL_TASK[activeTool] : undefined;
  const overlay = ANALYSIS_OVERLAYS.find((o) => o.tool === activeTool);
  const tool = advancedTools.find((t) => t.id === activeTool);

  useEffect(() => {
    setRun({ status: 'idle' });
    if (task) panelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [activeTool, task]);

  const open = (id: AdvancedToolId) => {
    if (id === 'temporal') return navigate('temporal');
    if (id === 'change') return navigate('comparison');
    if (id === 'measure') {
      setMapTool('measure');
      return navigate('map');
    }
    setActiveTool(id);
  };

  const runTool = async () => {
    if (!task) return;
    if (!aoi) return setRun({ status: 'invalid', message: 'Select an AOI on the map first — specialist tools run on a region.' });
    const invalid = validateAoi(aoi) ?? validateDate(imagery.date);
    if (invalid) return setRun({ status: 'invalid', message: invalid });
    setRun({ status: 'loading', message: `Running ${TASK_LABELS[task].toLowerCase()}…` });
    const q = `${TASK_LABELS[task]} for the selected AOI on ${imagery.date}`;
    const res = await api.analysis(buildRequest(task, q, { mode: overlay?.id }));
    setRun(res);
    logResult(task, q, [`AOI · ${describeAoi(aoi)}`, `Date ${imagery.date}`], res);
  };

  return (
    <section className="page">
      <div className="section-head">
        <div>
          <h2>Advanced analysis</h2>
          <p>Specialist tools stay separate from the AI-first workflow.</p>
        </div>
      </div>

      <div className="advanced-grid">
        {advancedTools.map((t) =>
        <div key={t.id} className={`panel tool-card${activeTool === t.id && TOOL_TASK[t.id] ? ' active' : ''}`}>
            <div className="icon">{t.number}</div>
            <h3>{t.title}</h3>
            <p>{t.description}</p>
            <button className="btn small" onClick={() => open(t.id)}>
              Open <ArrowRightIcon size={12} />
            </button>
          </div>
        )}
      </div>

      {task && tool && overlay &&
      <div ref={panelRef} className="panel panel-pad tool-panel">
          <div className="toolbar">
            <b style={{ fontSize: 16 }}>{tool.title}</b>
            <span className="badge accent">{overlay.source}</span>
            <span className="spacer" />
            <button className="btn small" onClick={() => setActiveTool(null)}>Close</button>
          </div>
          <p className="muted" style={{ margin: '8px 0 12px' }}>
            Preview the {overlay.label.toLowerCase()} product on the map for the selected date, then run the specialist model on your AOI.
          </p>
          <div className="chips">
            <span className="chip" style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
              AOI: {aoi ? describeAoi(aoi) : 'Not selected'}
              {aoi && (
                <button
                  onClick={() => setAoi(null)}
                  style={{ background: 'none', border: 'none', color: '#f87171', cursor: 'pointer', padding: '0 2px' }}
                  title="Clear AOI"
                >
                  <XIcon size={12} />
                </button>
              )}
            </span>
            <span className="chip">Date: {imagery.date}</span>
            <span className="chip">Layer: {overlay.label}</span>
            <span className="chip">Model: {buildRequest(task, '').model}</span>
          </div>
          <div className="actions-row">
            <button
            className="btn"
            onClick={() => {
              updateImagery({ overlay: overlay.id });
              navigate('map');
            }}>
            
              <MapIcon size={14} /> Show on map
            </button>
            {!aoi &&
              <button
                className="btn"
                onClick={() => {
                  setMapTool('rectangle');
                  navigate('map');
                }}>
                <CrosshairIcon size={14} /> Select AOI
              </button>
            }
            <button className="btn green" onClick={() => void runTool()} disabled={run.status === 'loading'}>
              Run {tool.title.toLowerCase()} analysis <ArrowRightIcon size={14} />
            </button>
            <button
              className="btn primary"
              onClick={() => {
                const promptText = `${tool.title} analysis for the selected AOI${aoi ? ` (${describeAoi(aoi)})` : ''} on ${imagery.date}. Focus on ${overlay.label.toLowerCase()} characteristics and anomalies.`;
                setQuery(promptText);
                navigate('home');
              }}
              title="Continue this specialist analysis in the AI Analyst workspace"
            >
              <SparklesIcon size={14} /> Send to AI Analyst
            </button>
          </div>
          <StateNotice state={run} onRetry={() => void runTool()} />
          {run.status === 'success' &&
        <div style={{ marginTop: 12 }}>
              <AnalysisResult result={run.data} title={`${tool.title} result`} />
            </div>
        }
        </div>
      }
    </section>);

}