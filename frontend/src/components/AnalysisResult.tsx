import React, { useMemo, useState } from 'react';
import type { AnalysisResponse, AttachedImage, TaskType } from '../types/app';
import { normalizeAnalysisResponse } from '../utils/normalizeAnalysis';
import { markdownToHtml } from '../utils/report';
import {
  ChevronDownIcon,
  ChevronUpIcon,
  SparklesIcon,
  CheckCircle2Icon,
  LayersIcon,
  MapIcon,
  SlidersIcon,
  CpuIcon,
  GlobeIcon,
  Maximize2Icon,
  ShieldAlertIcon,
  ActivityIcon
} from 'lucide-react';

export interface AnalysisResultProps {
  result: AnalysisResponse;
  title?: string;
  query?: string;
  attachments?: AttachedImage[];
  task?: TaskType;
  onOpenMap?: () => void;
}

export const AnalysisResult: React.FC<AnalysisResultProps> = ({
  result,
  query,
  attachments,
  task,
  onOpenMap
}) => {
  const [showDetails, setShowDetails] = useState(false);

  // Normalize response defensively
  const normalized = useMemo(() => {
    return normalizeAnalysisResponse(result, {
      query,
      attachments,
      task
    });
  }, [result, query, attachments, task]);

  if (!result) {
    return null;
  }

  const {
    answer,
    supportingFindings,
    header,
    models,
    raster,
    metadata,
    limitations
  } = normalized;

  // Active models only
  const activeModels: string[] = [];
  if (models.internvl?.available) activeModels.push('InternVL3-2B');
  if (models.upernet?.available) activeModels.push('UPerNet-ConvNeXt');
  if (models.owlv2?.available) activeModels.push('OWLv2 Grounding');
  if (models.changeformer?.available) activeModels.push('ChangeFormerV6');

  // Ground resolution & footprint deduplication
  const groundRes = raster?.resolutionM || metadata?.groundResolution;
  const crsVal = raster?.crs || metadata?.crs;
  const footprintVal = raster?.footprintKm2 || metadata?.sceneFootprint;

  const displayAnswer = answer || result.summary || '';
  const htmlAnswer = useMemo(() => markdownToHtml(displayAnswer), [displayAnswer]);

  return (
    <div className="w-full space-y-3.5 text-[var(--ink)] font-sans antialiased">
      {/* =========================================================================
          CARD 1: PRIMARY AI ANSWER (70-80% Visual Focus)
          Contains direct answer, substantive description, and inline map action if mask is present.
          ========================================================================= */}
      <div
        className="rounded-2xl border border-[var(--line)] bg-[var(--surface-2,rgba(255,255,255,0.03))] p-5 sm:p-6 shadow-md relative overflow-hidden backdrop-blur-sm"
        style={{
          boxShadow: '0 4px 20px -2px rgba(0, 0, 0, 0.25)'
        }}
      >
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-400 opacity-90" />

        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2 text-xs font-medium text-[var(--accent,#a56cff)]">
            <SparklesIcon className="h-4 w-4" />
            <span className="font-semibold uppercase tracking-wider text-[11px]">AI Geospatial Answer</span>
          </div>

          <div className="flex items-center gap-2">
            {result.maskUrl && onOpenMap && (
              <button
                type="button"
                onClick={onOpenMap}
                className="flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-full bg-indigo-500/15 text-indigo-300 hover:bg-indigo-500/25 border border-indigo-500/30 transition-all cursor-pointer"
                title="View spatial mask on interactive map"
              >
                <LayersIcon className="h-3.5 w-3.5" />
                <span>View on Map</span>
              </button>
            )}
            {header?.validation && (
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Verified Analysis
              </span>
            )}
          </div>
        </div>

        <div
          className="prose prose-invert max-w-none text-sm sm:text-base leading-relaxed text-[var(--ink)] space-y-3 font-sans"
          dangerouslySetInnerHTML={{ __html: htmlAnswer }}
        />
      </div>

      {/* =========================================================================
          CARD 2: KEY FINDINGS (Relevant factual measurements directly supporting answer)
          Only displayed if supporting findings exist.
          ========================================================================= */}
      {supportingFindings && supportingFindings.length > 0 && (
        <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-1,rgba(255,255,255,0.02))] p-4 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-[var(--ink)] uppercase tracking-wider">
            <CheckCircle2Icon className="h-4 w-4 text-emerald-400" />
            Key Findings
          </div>
          <ul className="space-y-1.5 pl-1 pt-1">
            {supportingFindings.map((finding, idx) => (
              <li key={idx} className="flex items-start gap-2 text-xs sm:text-sm text-[var(--text-soft)]">
                <span className="text-emerald-400 mt-0.5">•</span>
                <span>{finding}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* =========================================================================
          CARD 3: ANALYSIS DETAILS (Collapsed by default, strictly consolidated)
          Single unified card containing compact technical metadata, active models, and limitations.
          No separate cards for CRS, resolution, models, or diagnostics.
          ========================================================================= */}
      <div className="pt-1">
        <button
          type="button"
          onClick={() => setShowDetails((prev) => !prev)}
          className="flex items-center gap-2 text-xs font-medium text-[var(--muted)] hover:text-[var(--ink)] transition-colors py-1.5 px-3 rounded-lg border border-[var(--line)] bg-[var(--surface-1)] cursor-pointer"
        >
          <SlidersIcon className="h-3.5 w-3.5" />
          <span>{showDetails ? 'Analysis Details' : 'Analysis Details ▾'}</span>
          {showDetails ? <ChevronUpIcon className="h-3.5 w-3.5 ml-0.5" /> : null}
        </button>

        {showDetails && (
          <div className="mt-3 rounded-xl border border-[var(--line)] bg-[var(--surface-1)] p-4 sm:p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--line)] pb-2.5">
              <span className="text-xs font-semibold uppercase tracking-wider text-[var(--ink)]">Technical Analysis Details</span>
              <span className="text-[11px] text-[var(--muted)]">Internal Engine Telemetry</span>
            </div>

            {/* Compact Technical Metadata Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {activeModels.length > 0 && (
                <div className="p-2.5 rounded-lg border border-[var(--line)] bg-[var(--surface-2)]">
                  <div className="flex items-center gap-1.5 text-[11px] text-[var(--muted)] mb-1">
                    <CpuIcon className="h-3.5 w-3.5 text-indigo-400" />
                    <span>Models Used</span>
                  </div>
                  <div className="text-xs font-medium text-[var(--ink)]">
                    {activeModels.join(', ')}
                  </div>
                </div>
              )}

              {crsVal && (
                <div className="p-2.5 rounded-lg border border-[var(--line)] bg-[var(--surface-2)]">
                  <div className="flex items-center gap-1.5 text-[11px] text-[var(--muted)] mb-1">
                    <GlobeIcon className="h-3.5 w-3.5 text-blue-400" />
                    <span>Coordinate Reference System</span>
                  </div>
                  <div className="text-xs font-mono text-[var(--ink)]">
                    {crsVal}
                  </div>
                </div>
              )}

              {groundRes && (
                <div className="p-2.5 rounded-lg border border-[var(--line)] bg-[var(--surface-2)]">
                  <div className="flex items-center gap-1.5 text-[11px] text-[var(--muted)] mb-1">
                    <Maximize2Icon className="h-3.5 w-3.5 text-amber-400" />
                    <span>Ground Resolution</span>
                  </div>
                  <div className="text-xs font-medium text-[var(--ink)]">
                    {groundRes}
                  </div>
                </div>
              )}

              {footprintVal && (
                <div className="p-2.5 rounded-lg border border-[var(--line)] bg-[var(--surface-2)]">
                  <div className="flex items-center gap-1.5 text-[11px] text-[var(--muted)] mb-1">
                    <MapIcon className="h-3.5 w-3.5 text-emerald-400" />
                    <span>Spatial Footprint</span>
                  </div>
                  <div className="text-xs font-medium text-[var(--ink)]">
                    {footprintVal}
                  </div>
                </div>
              )}

              <div className="p-2.5 rounded-lg border border-[var(--line)] bg-[var(--surface-2)]">
                <div className="flex items-center gap-1.5 text-[11px] text-[var(--muted)] mb-1">
                  <ActivityIcon className="h-3.5 w-3.5 text-purple-400" />
                  <span>Processing Method</span>
                </div>
                <div className="text-xs font-medium text-[var(--ink)]">
                  Deterministic Raster & Multi-Model Inference
                </div>
              </div>
            </div>

            {/* Scientific Limitations & Review (if present) */}
            {limitations && limitations.length > 0 && (
              <div className="pt-2 border-t border-[var(--line)]">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-[var(--muted)] mb-2">
                  <ShieldAlertIcon className="h-3.5 w-3.5 text-amber-400" />
                  <span>Scientific Limitations & Interpretation Notes</span>
                </div>
                <ul className="space-y-1 pl-1">
                  {limitations.map((lim, idx) => (
                    <li key={idx} className="text-xs text-[var(--text-soft)] leading-relaxed">
                      • {typeof lim === 'string' ? lim : (lim.warning || `${lim.source}: ${lim.impact || ''}`)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};