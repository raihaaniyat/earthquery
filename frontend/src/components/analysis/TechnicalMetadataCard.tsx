import React, { useState } from 'react';
import { Settings2Icon, ChevronDownIcon, ChevronUpIcon, CpuIcon, ClockIcon, GlobeIcon, GaugeIcon } from 'lucide-react';
import type { NormalizedAnalysis } from '../../utils/normalizeAnalysis';

interface TechnicalMetadataCardProps {
  metadata: NormalizedAnalysis['metadata'];
}

export const TechnicalMetadataCard: React.FC<TechnicalMetadataCardProps> = ({ metadata }) => {
  const [isOpen, setIsOpen] = useState(false);

  if (!metadata || (
    !metadata.task &&
    (!metadata.participatingModels || metadata.participatingModels.length === 0) &&
    !metadata.crs &&
    !metadata.groundResolution &&
    !metadata.executionTimeMs
  )) {
    return null;
  }

  return (
    <section 
      className="rounded-2xl border border-[var(--line)] bg-[var(--panel-solid)] shadow-md backdrop-blur-sm overflow-hidden transition-all"
    >
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 sm:p-5 text-left hover:bg-[var(--surface-1)] transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--surface-2)] text-[var(--muted)] border border-[var(--line)]">
            <Settings2Icon className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--muted)] font-semibold">
                Diagnostics & Telemetry
              </span>
            </div>
            <h3 className="text-sm font-semibold text-[var(--ink)] flex items-center gap-2">
              Technical Analysis Metadata
            </h3>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {metadata.executionTimeMs && (
            <span className="hidden sm:inline-flex items-center gap-1 text-[11px] font-mono text-[var(--muted)] bg-[var(--surface-2)] px-2 py-0.5 rounded border border-[var(--line)]">
              <ClockIcon className="h-3 w-3" />
              {metadata.executionTimeMs}
            </span>
          )}
          <span className="text-xs text-[var(--muted)] font-mono flex items-center gap-1">
            {isOpen ? 'Hide' : 'Show details'}
            {isOpen ? <ChevronUpIcon className="h-4 w-4" /> : <ChevronDownIcon className="h-4 w-4" />}
          </span>
        </div>
      </button>

      {isOpen && (
        <div className="p-5 border-t border-[var(--line)] bg-[var(--surface-1)]/40 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {metadata.task && (
              <div className="p-3 rounded-xl border border-[var(--line)] bg-[var(--surface-1)]">
                <div className="text-[10px] font-mono text-[var(--muted)] uppercase tracking-wider mb-1 flex items-center gap-1.5">
                  <CpuIcon className="h-3.5 w-3.5 text-indigo-400" />
                  Primary Task
                </div>
                <div className="text-xs font-mono text-[var(--ink)] font-medium">
                  {metadata.task}
                </div>
              </div>
            )}

            {metadata.crs && (
              <div className="p-3 rounded-xl border border-[var(--line)] bg-[var(--surface-1)]">
                <div className="text-[10px] font-mono text-[var(--muted)] uppercase tracking-wider mb-1 flex items-center gap-1.5">
                  <GlobeIcon className="h-3.5 w-3.5 text-cyan-400" />
                  Coordinate Reference System
                </div>
                <div className="text-xs font-mono text-[var(--ink)] font-medium">
                  {metadata.crs}
                </div>
              </div>
            )}

            {metadata.groundResolution && (
              <div className="p-3 rounded-xl border border-[var(--line)] bg-[var(--surface-1)]">
                <div className="text-[10px] font-mono text-[var(--muted)] uppercase tracking-wider mb-1 flex items-center gap-1.5">
                  <GaugeIcon className="h-3.5 w-3.5 text-amber-400" />
                  Ground Resolution
                </div>
                <div className="text-xs font-mono text-[var(--ink)] font-medium">
                  {metadata.groundResolution}
                </div>
              </div>
            )}

            {metadata.sceneFootprint && (
              <div className="p-3 rounded-xl border border-[var(--line)] bg-[var(--surface-1)]">
                <div className="text-[10px] font-mono text-[var(--muted)] uppercase tracking-wider mb-1">
                  Scene Footprint Area
                </div>
                <div className="text-xs font-mono text-[var(--ink)] font-medium">
                  {metadata.sceneFootprint}
                </div>
              </div>
            )}

            {metadata.executionTimeMs && (
              <div className="p-3 rounded-xl border border-[var(--line)] bg-[var(--surface-1)]">
                <div className="text-[10px] font-mono text-[var(--muted)] uppercase tracking-wider mb-1 flex items-center gap-1.5">
                  <ClockIcon className="h-3.5 w-3.5 text-emerald-400" />
                  Total Pipeline Latency
                </div>
                <div className="text-xs font-mono text-[var(--ink)] font-medium">
                  {metadata.executionTimeMs}
                </div>
              </div>
            )}

            {metadata.decisionReason && (
              <div className="p-3 rounded-xl border border-[var(--line)] bg-[var(--surface-1)] sm:col-span-2 lg:col-span-3">
                <div className="text-[10px] font-mono text-[var(--muted)] uppercase tracking-wider mb-1">
                  Engine Routing Reason
                </div>
                <div className="text-xs font-mono text-[var(--muted)]">
                  {metadata.decisionReason}
                </div>
              </div>
            )}
          </div>

          {metadata.participatingModels && metadata.participatingModels.length > 0 && (
            <div className="p-3.5 rounded-xl border border-[var(--line)] bg-[var(--surface-1)]">
              <div className="text-[10px] font-mono text-[var(--muted)] uppercase tracking-wider mb-2 font-semibold">
                Participating Models & Engines ({metadata.participatingModels.length})
              </div>
              <div className="flex flex-wrap gap-2">
                {metadata.participatingModels.map((m, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center text-xs font-mono px-2.5 py-1 rounded bg-[var(--surface-2)] border border-[var(--line)] text-[var(--ink)]"
                  >
                    {m}
                  </span>
                ))}
              </div>
            </div>
          )}

          {metadata.radiometry && (
            <div className="p-3 rounded-xl border border-[var(--line)] bg-[var(--surface-1)]">
              <div className="text-[10px] font-mono text-[var(--muted)] uppercase tracking-wider mb-1">
                Radiometric DN Summary
              </div>
              <div className="text-xs font-mono text-[var(--ink)]">
                {metadata.radiometry}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
};
