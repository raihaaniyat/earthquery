import React from 'react';
import { NetworkIcon, CheckCircle2Icon, AlertCircleIcon, ShieldCheckIcon } from 'lucide-react';
import type { NormalizedAnalysis } from '../../utils/normalizeAnalysis';

interface FusionSummaryCardProps {
  fusion: NormalizedAnalysis['fusion'];
}

export const FusionSummaryCard: React.FC<FusionSummaryCardProps> = ({ fusion }) => {
  if (!fusion || !fusion.sceneSummary) {
    return null;
  }

  return (
    <section 
      className="rounded-2xl border border-[var(--line)] bg-[var(--panel-solid)] p-6 shadow-xl backdrop-blur-sm relative overflow-hidden"
      style={{
        boxShadow: '0 8px 30px -4px rgba(0, 0, 0, 0.5)'
      }}
    >
      {/* Decorative gradient glow at top */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-emerald-500 via-indigo-500 to-cyan-500 opacity-80" />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[var(--line)] pb-4 mb-5">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500/20 to-emerald-500/20 text-indigo-400 border border-indigo-500/30">
            <NetworkIcon className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400 font-semibold px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20">
                Synthesis Engine
              </span>
              <span className="text-[10px] font-mono text-[var(--muted)]">Fusion Output</span>
            </div>
            <h3 className="text-lg font-semibold text-[var(--ink)] flex items-center gap-2">
              Cross-Model Synthesis
            </h3>
          </div>
        </div>
        <p className="text-xs text-[var(--muted)] max-w-sm sm:text-right">
          Combined interpretation synthesized from multimodal neural reasoning and raster telemetry.
        </p>
      </div>

      {/* Main Scene Summary */}
      <div className="mb-6 rounded-xl border border-[var(--line)] bg-[var(--surface-1)] p-4">
        <div className="text-[10px] font-mono uppercase tracking-wider text-[var(--muted)] mb-2 font-semibold flex items-center gap-1.5">
          <ShieldCheckIcon className="h-3.5 w-3.5 text-emerald-400" />
          Scene Summary & Consensus
        </div>
        <p className="text-sm text-[var(--ink)] leading-relaxed whitespace-pre-line font-sans">
          {fusion.sceneSummary}
        </p>
      </div>

      {/* Grid of Supporting Sources & Agreement / Conflict */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Supporting Sources */}
        <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-1)]/60 p-4">
          <div className="text-[10px] font-mono uppercase tracking-wider text-[var(--muted)] mb-2.5 font-semibold">
            Corroborating Evidence Streams ({fusion.supportingSources.length})
          </div>
          <div className="flex flex-wrap gap-2">
            {fusion.supportingSources.map((source, idx) => (
              <span 
                key={idx}
                className="inline-flex items-center gap-1.5 text-xs font-mono px-2.5 py-1 rounded-lg bg-[var(--surface-2)] border border-[var(--line)] text-[var(--ink)] shadow-sm"
              >
                <CheckCircle2Icon className="h-3.5 w-3.5 text-emerald-400" />
                {source}
              </span>
            ))}
          </div>
        </div>

        {/* Cross-Model Consensus / Conflict State */}
        <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-1)]/60 p-4">
          <div className="text-[10px] font-mono uppercase tracking-wider text-[var(--muted)] mb-2 font-semibold">
            Agreement & Discrepancies
          </div>
          <div className="space-y-2">
            <div className="flex items-start gap-2 text-xs text-[var(--ink)]">
              <CheckCircle2Icon className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
              <span>{fusion.agreement || 'Multiple analysis streams support this interpretation.'}</span>
            </div>
            
            {fusion.conflictsOrUncertainties ? (
              <div className="flex items-start gap-2 text-xs text-amber-400 bg-amber-500/10 p-2 rounded border border-amber-500/20">
                <AlertCircleIcon className="h-4 w-4 shrink-0 mt-0.5" />
                <span>{fusion.conflictsOrUncertainties}</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-xs text-[var(--muted)] pl-6">
                <span>No significant cross-model conflicts detected across model pipelines.</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};
