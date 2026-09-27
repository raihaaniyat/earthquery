import React from 'react';
import { GitCompareIcon, CheckIcon, MinusIcon } from 'lucide-react';
import type { NormalizedAnalysis } from '../../utils/normalizeAnalysis';

interface CrossModelEvidenceProps {
  evidence: NormalizedAnalysis['crossModelEvidence'];
}

export const CrossModelEvidence: React.FC<CrossModelEvidenceProps> = ({ evidence }) => {
  if (!evidence || !evidence.features || evidence.features.length === 0) {
    return null;
  }

  return (
    <section 
      className="rounded-2xl border border-[var(--line)] bg-[var(--panel-solid)] p-5 shadow-lg backdrop-blur-sm"
      style={{
        boxShadow: '0 4px 20px -2px rgba(0, 0, 0, 0.4)'
      }}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[var(--line)] pb-4 mb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <GitCompareIcon className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase tracking-wider text-indigo-400 font-semibold px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20">
                Synthesis Layer
              </span>
              <span className="text-[10px] font-mono text-[var(--muted)]">Evidence Matrix</span>
            </div>
            <h3 className="text-base font-semibold text-[var(--ink)] flex items-center gap-2">
              Cross-Model Evidence
            </h3>
          </div>
        </div>
        <p className="text-xs text-[var(--muted)] max-w-sm">
          How independent analysis streams and deterministic measurements corroborate observed features.
        </p>
      </div>

      <div className="overflow-x-auto rounded-xl border border-[var(--line)] bg-[var(--surface-1)]">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-[var(--line)] bg-[var(--surface-2)] text-[var(--muted)] font-mono uppercase tracking-wider text-[10px]">
              <th className="py-2.5 px-4 font-medium">Feature / Land Cover</th>
              <th className="py-2.5 px-3 font-medium text-center">InternVL3-2B</th>
              <th className="py-2.5 px-3 font-medium text-center">UPerNet</th>
              <th className="py-2.5 px-3 font-medium text-center">OWLv2</th>
              <th className="py-2.5 px-3 font-medium text-center">Raster Data</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--line)]">
            {evidence.features.map((item, idx) => (
              <tr 
                key={idx} 
                className="hover:bg-[var(--surface-2)]/50 transition-colors font-mono"
              >
                <td className="py-2.5 px-4 font-sans font-medium text-[var(--ink)] text-xs">
                  {item.name}
                </td>
                <td className="py-2.5 px-3 text-center">
                  {item.internvl ? (
                    <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                      <CheckIcon className="h-3 w-3 stroke-[3]" />
                    </span>
                  ) : (
                    <span className="inline-flex items-center justify-center text-[var(--muted)] opacity-40">
                      <MinusIcon className="h-3 w-3" />
                    </span>
                  )}
                </td>
                <td className="py-2.5 px-3 text-center">
                  {item.upernet ? (
                    <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-blue-500/15 text-blue-400 border border-blue-500/30">
                      <CheckIcon className="h-3 w-3 stroke-[3]" />
                    </span>
                  ) : (
                    <span className="inline-flex items-center justify-center text-[var(--muted)] opacity-40">
                      <MinusIcon className="h-3 w-3" />
                    </span>
                  )}
                </td>
                <td className="py-2.5 px-3 text-center">
                  {item.owlv2 ? (
                    <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/30">
                      <CheckIcon className="h-3 w-3 stroke-[3]" />
                    </span>
                  ) : (
                    <span className="inline-flex items-center justify-center text-[var(--muted)] opacity-40">
                      <MinusIcon className="h-3 w-3" />
                    </span>
                  )}
                </td>
                <td className="py-2.5 px-3 text-center">
                  {item.raster ? (
                    <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">
                      <CheckIcon className="h-3 w-3 stroke-[3]" />
                    </span>
                  ) : (
                    <span className="inline-flex items-center justify-center text-[var(--muted)] opacity-40">
                      <MinusIcon className="h-3 w-3" />
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex items-center justify-between text-[11px] text-[var(--muted)] px-1">
        <span className="italic">
          * A checkmark denotes verifiable observation or measurement present in the model or raster stream.
        </span>
        <span className="font-mono text-[10px]">
          Confidence: Multi-stream Verified
        </span>
      </div>
    </section>
  );
};
