import React, { useState } from 'react';
import { AlertTriangleIcon, ChevronDownIcon, ChevronUpIcon, InfoIcon } from 'lucide-react';
import type { NormalizedAnalysis } from '../../utils/normalizeAnalysis';

interface LimitationsCardProps {
  limitations: NormalizedAnalysis['limitations'];
}

export const LimitationsCard: React.FC<LimitationsCardProps> = ({ limitations }) => {
  const [isOpen, setIsOpen] = useState(true);

  if (!limitations || limitations.length === 0) {
    return null;
  }

  return (
    <section 
      className="rounded-2xl border border-amber-500/30 bg-amber-950/10 p-5 shadow-lg backdrop-blur-sm"
      style={{
        boxShadow: '0 4px 20px -2px rgba(245, 158, 11, 0.05)'
      }}
    >
      <div className="flex items-center justify-between gap-3 border-b border-amber-500/20 pb-3 mb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-500/15 text-amber-400 border border-amber-500/30">
            <AlertTriangleIcon className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase tracking-wider text-amber-400 font-semibold px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20">
                Scientific Review
              </span>
            </div>
            <h3 className="text-sm font-semibold text-[var(--ink)] flex items-center gap-2">
              Interpretation Requiring Review ({limitations.length})
            </h3>
          </div>
        </div>

        <button
          onClick={() => setIsOpen(!isOpen)}
          className="text-xs text-[var(--muted)] hover:text-[var(--ink)] font-mono flex items-center gap-1 transition-colors"
        >
          {isOpen ? 'Collapse' : 'Expand'}
          {isOpen ? <ChevronUpIcon className="h-4 w-4" /> : <ChevronDownIcon className="h-4 w-4" />}
        </button>
      </div>

      {isOpen && (
        <div className="space-y-3">
          {limitations.map((lim, idx) => (
            <div 
              key={idx}
              className="p-3.5 rounded-xl border border-amber-500/20 bg-[var(--surface-1)] text-xs text-[var(--ink)] space-y-2"
            >
              <div className="flex items-center justify-between text-[11px] font-mono">
                <span className="px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-400 font-medium">
                  Source: {lim.source}
                </span>
              </div>
              <p className="leading-relaxed text-[var(--ink)]">
                {lim.warning}
              </p>
              {lim.impact && (
                <div className="flex items-start gap-1.5 text-[11px] text-[var(--muted)] pt-1 border-t border-[var(--line)]">
                  <InfoIcon className="h-3.5 w-3.5 text-amber-400 shrink-0 mt-0.5" />
                  <span><strong className="text-[var(--ink)] font-normal">Impact:</strong> {lim.impact}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
};
