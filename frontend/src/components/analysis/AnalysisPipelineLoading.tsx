import React from 'react';
import { Loader2Icon, CheckCircle2Icon, CircleDashedIcon, CpuIcon, LayersIcon } from 'lucide-react';

interface AnalysisPipelineLoadingProps {
  message?: string;
}

export const AnalysisPipelineLoading: React.FC<AnalysisPipelineLoadingProps> = ({ message }) => {
  return (
    <div 
      className="rounded-2xl border border-[var(--line)] bg-[var(--panel-solid)] p-6 shadow-xl backdrop-blur-sm space-y-5"
      role="status"
    >
      <div className="flex items-center justify-between border-b border-[var(--line)] pb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <CpuIcon className="h-5 w-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase tracking-wider text-indigo-400 font-semibold px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20">
                Pipeline Active
              </span>
            </div>
            <h3 className="text-sm font-semibold text-[var(--ink)]">
              Satellite Scene Analysis Pipeline
            </h3>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono text-[var(--muted)]">
          <Loader2Icon className="h-4 w-4 animate-spin text-indigo-400" />
          <span>Processing…</span>
        </div>
      </div>

      {/* Pipeline Stages */}
      <div className="space-y-3 font-mono text-xs">
        <div className="flex items-center justify-between p-2.5 rounded-lg bg-[var(--surface-1)] border border-[var(--line)]">
          <div className="flex items-center gap-2.5 text-emerald-400">
            <CheckCircle2Icon className="h-4 w-4 shrink-0" />
            <span className="text-[var(--ink)]">Input raster verified & georeferenced</span>
          </div>
          <span className="text-[10px] text-emerald-400 font-medium">Ready</span>
        </div>

        <div className="flex items-center justify-between p-2.5 rounded-lg bg-indigo-500/10 border border-indigo-500/30">
          <div className="flex items-center gap-2.5 text-indigo-400">
            <Loader2Icon className="h-4 w-4 animate-spin shrink-0 text-indigo-400" />
            <span className="text-[var(--ink)] font-medium">
              {message || 'Executing multimodal models & raster radiometry…'}
            </span>
          </div>
          <span className="text-[10px] text-indigo-400 font-medium animate-pulse">Running</span>
        </div>

        <div className="flex items-center justify-between p-2.5 rounded-lg bg-[var(--surface-1)] border border-[var(--line)] opacity-60">
          <div className="flex items-center gap-2.5 text-[var(--muted)]">
            <CircleDashedIcon className="h-4 w-4 shrink-0" />
            <span>Cross-model synthesis & validation review</span>
          </div>
          <span className="text-[10px] text-[var(--muted)]">Queued</span>
        </div>
      </div>

      <div className="flex items-center gap-2 text-[11px] text-[var(--muted)] pt-1">
        <LayersIcon className="h-3.5 w-3.5 text-indigo-400" />
        <span>Executing available ensemble engines with deterministically bounded VRAM.</span>
      </div>
    </div>
  );
};
