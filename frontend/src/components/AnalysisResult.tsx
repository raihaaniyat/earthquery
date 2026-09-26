import React from 'react';
import { CheckCircle2Icon, AlertCircleIcon, ShieldAlertIcon, ActivityIcon } from 'lucide-react';
import type { AnalysisResponse } from '../types/app';

export function AnalysisResult({ result, title = 'Scientific Analysis Result' }: { result: AnalysisResponse; title?: string; }) {
  const findings = result.findings ?? [];
  const metrics = Object.entries(result.metrics ?? {});
  const sections = result.sections;

  return (
    <div className="result-text">
      <div className="toolbar" style={{ marginBottom: 8, flexWrap: 'wrap', gap: 6 }}>
        <h3 style={{ margin: 0 }}>{title}</h3>
        {result.validation && (
          <span className={`badge ${result.validation === 'passed' ? 'ok' : result.validation === 'failed' ? 'bad' : ''}`}>
            Validation: {result.validation}
          </span>
        )}
        {result.model && <span className="badge">{result.model}</span>}
        {result.decision_reason && (
          <span className="badge" title={result.decision_reason} style={{ fontSize: 11, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            Route: {result.decision_reason}
          </span>
        )}
      </div>

      <p style={{ fontSize: 14, lineHeight: 1.5, marginBottom: 12 }}>{result.summary}</p>
      {result.maskUrl && <img className="result-mask" src={result.maskUrl} alt="Model output mask" style={{ maxHeight: 280, borderRadius: 6, margin: '8px 0' }} />}

      {/* 3 Scientific Sections */}
      {sections ? (
        <div className="scientific-sections" style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 12 }}>
          {/* 1. Measured from raster */}
          {sections.measured_from_raster && sections.measured_from_raster.length > 0 && (
            <div className="scientific-panel" style={{ background: 'rgba(34, 197, 94, 0.08)', border: '1px solid rgba(34, 197, 94, 0.25)', borderRadius: 8, padding: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                <CheckCircle2Icon size={16} color="#22c55e" />
                <b style={{ fontSize: 13, color: 'var(--text-main, #e2e8f0)' }}>Measured from raster</b>
                <span className="badge ok" style={{ fontSize: 10, marginLeft: 'auto' }}>Deterministic</span>
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.6 }}>
                {sections.measured_from_raster.map((item, i) => (
                  <li key={i} style={{ color: 'var(--text-muted, #cbd5e1)' }}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {/* 2. Model candidate */}
          {sections.model_candidate && sections.model_candidate.observation && (
            <div className="scientific-panel" style={{ background: 'rgba(99, 102, 241, 0.08)', border: '1px solid rgba(99, 102, 241, 0.25)', borderRadius: 8, padding: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                <ActivityIcon size={16} color="#818cf8" />
                <b style={{ fontSize: 13, color: 'var(--text-main, #e2e8f0)' }}>Model candidate ({sections.model_candidate.model})</b>
                <span className="badge" style={{ fontSize: 10, marginLeft: 'auto' }}>Visual Observation</span>
              </div>
              <p style={{ margin: 0, fontSize: 13, lineHeight: 1.5, color: 'var(--text-muted, #cbd5e1)' }}>
                {sections.model_candidate.observation}
              </p>
            </div>
          )}

          {/* 3. Interpretation requiring review */}
          {sections.interpretation_requiring_review && sections.interpretation_requiring_review.length > 0 && (
            <div className="scientific-panel" style={{ background: 'rgba(234, 179, 8, 0.08)', border: '1px solid rgba(234, 179, 8, 0.25)', borderRadius: 8, padding: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                <ShieldAlertIcon size={16} color="#eab308" />
                <b style={{ fontSize: 13, color: 'var(--text-main, #e2e8f0)' }}>Interpretation requiring review</b>
                <span className="badge warn" style={{ fontSize: 10, marginLeft: 'auto' }}>Limitations</span>
              </div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.6 }}>
                {sections.interpretation_requiring_review.map((item, i) => (
                  <li key={i} style={{ color: 'var(--text-muted, #cbd5e1)' }}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        /* Fallback findings display */
        findings.length > 0 && (
          <div style={{ marginTop: 10 }}>
            {findings.map((f, i) => (
              <div className="finding" key={`${f.label}-${i}`}>
                <div className="toolbar">
                  <b>{f.label}</b>
                  {typeof f.confidence === 'number' && (
                    <span className="badge">{Math.round(f.confidence * 100)}% confidence</span>
                  )}
                </div>
                <span className="muted">{f.detail}</span>
              </div>
            ))}
          </div>
        )
      )}

      {metrics.length > 0 && (
        <div className="chips" style={{ marginTop: 12 }}>
          {metrics.map(([k, v]) => (
            <span className="chip" key={k}>
              {k}: {String(v)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}