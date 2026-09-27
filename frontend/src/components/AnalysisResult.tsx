import React, { useMemo } from 'react';
import type { AnalysisResponse, AttachedImage, TaskType } from '../types/app';
import { normalizeAnalysisResponse } from '../utils/normalizeAnalysis';
import { AnalysisHeader } from './analysis/AnalysisHeader';
import { AnalysisInputCard } from './analysis/AnalysisInputCard';
import { InternVLCard } from './analysis/InternVLCard';
import { UPerNetCard } from './analysis/UPerNetCard';
import { OWLv2Card } from './analysis/OWLv2Card';
import { RasterAnalysisCard } from './analysis/RasterAnalysisCard';
import { CrossModelEvidence } from './analysis/CrossModelEvidence';
import { FusionSummaryCard } from './analysis/FusionSummaryCard';
import { TechnicalMetadataCard } from './analysis/TechnicalMetadataCard';
import { LimitationsCard } from './analysis/LimitationsCard';
import { RawAnalysisFallback } from './analysis/RawAnalysisFallback';
import { CpuIcon } from 'lucide-react';

export interface AnalysisResultProps {
  result: AnalysisResponse;
  title?: string;
  query?: string;
  attachments?: AttachedImage[];
  task?: TaskType;
}

export const AnalysisResult: React.FC<AnalysisResultProps> = ({
  result,
  title = 'Satellite Scene Analysis',
  query,
  attachments,
  task
}) => {
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
    header,
    input,
    models,
    raster,
    crossModelEvidence,
    fusion,
    metadata,
    limitations,
    unrecognizedMarkdown
  } = normalized;

  const hasAnyModel = models.internvl?.available || models.upernet?.available || models.owlv2?.available || models.changeformer?.available;

  return (
    <div className="w-full space-y-6 text-[var(--ink)] font-sans antialiased">
      {/* 1. Scientific Analysis Header */}
      <AnalysisHeader header={{ ...header, title: title || header.title }} />

      {/* 2. Original Input / Query Card */}
      {input && <AnalysisInputCard input={input} />}

      {/* 3. Model Analysis Section */}
      <div className="space-y-4 pt-2">
        <div className="border-b border-[var(--line)] pb-2 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase tracking-wider text-indigo-400 font-semibold px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20">
                Inference Engines
              </span>
              <span className="text-[10px] font-mono text-[var(--muted)]">Model Breakdown</span>
            </div>
            <h2 className="text-base font-semibold text-[var(--ink)] mt-1 flex items-center gap-2">
              <CpuIcon className="h-4 w-4 text-indigo-400" />
              Model Analysis
            </h2>
          </div>
          <p className="text-xs text-[var(--muted)] hidden sm:block">
            Individual model outputs and supporting evidence
          </p>
        </div>

        {/* Dedicated Model Cards */}
        <div className="space-y-4">
          {/* InternVL3-2B Card */}
          {models.internvl && (
            <InternVLCard internvl={models.internvl} />
          )}

          {/* UPerNet ConvNeXt Card */}
          {models.upernet && (
            <UPerNetCard upernet={models.upernet} />
          )}

          {/* OWLv2 GeoGround Card */}
          {models.owlv2 && (
            <OWLv2Card owlv2={models.owlv2} />
          )}

          {!hasAnyModel && (
            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface-1)] p-4 text-center text-xs text-[var(--muted)] font-mono">
              Model-specific output unavailable in this response.
            </div>
          )}
        </div>
      </div>

      {/* 4. Deterministic Raster Analysis Card */}
      {raster && (
        <div className="pt-2">
          <RasterAnalysisCard raster={raster} />
        </div>
      )}

      {/* 5. Cross-Model Evidence Section */}
      {crossModelEvidence && crossModelEvidence.features && crossModelEvidence.features.length > 0 && (
        <div className="pt-2">
          <CrossModelEvidence evidence={crossModelEvidence} />
        </div>
      )}

      {/* 6. Final Cross-Model Synthesis Card */}
      {fusion && fusion.sceneSummary && (
        <div className="pt-2">
          <FusionSummaryCard fusion={fusion} />
        </div>
      )}

      {/* 7. Limitations & Scientific Review Card */}
      {limitations && limitations.length > 0 && (
        <div className="pt-2">
          <LimitationsCard limitations={limitations} />
        </div>
      )}

      {/* 8. Technical Analysis Metadata (Collapsible) */}
      {metadata && (
        <div className="pt-1">
          <TechnicalMetadataCard metadata={metadata} />
        </div>
      )}

      {/* 9. Raw Analysis Fallback (for unrecognized text or raw markdown review) */}
      {unrecognizedMarkdown && (
        <div className="pt-1">
          <RawAnalysisFallback content={unrecognizedMarkdown} />
        </div>
      )}
    </div>
  );
};