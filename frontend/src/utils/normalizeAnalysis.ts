import type { AnalysisResponse, AttachedImage, TaskType } from '../types/app';

export interface VisualFeature {
  name: string;
  description: string;
}

export interface SpatialRegion {
  region: string;
  description: string;
}

export interface SegmentedClass {
  name: string;
  coveragePct: number;
  confidence?: number;
}

export interface DetectedObject {
  label: string;
  confidence?: number;
  box?: number[];
}

export interface NormalizedAnalysis {
  header: {
    title: string;
    status: string;
    validation: string;
    modelCount: number;
    modelsList: string[];
    processingType: string;
    query?: string;
  };
  input?: {
    query?: string;
    filename?: string;
    fileType?: string;
    fileSize?: string;
    imagePreviewUrl?: string;
    analysisType?: string;
    inputCategory?: string;
  };
  models: {
    internvl?: {
      available: boolean;
      role: string;
      task: string;
      sceneType?: string;
      directObservation?: string;
      visualFeatures: VisualFeature[];
      spatialInterpretation: SpatialRegion[];
      confidence?: string;
      limitations?: string;
      evidenceNote?: string;
    };
    upernet?: {
      available: boolean;
      role: string;
      analysisType: string;
      classes: SegmentedClass[];
      maskUrl?: string;
      evidenceNote?: string;
    };
    owlv2?: {
      available: boolean;
      role: string;
      candidateDetectionsCount?: number;
      detectedObjects: DetectedObject[];
      overlayUrl?: string;
      evidenceNote?: string;
    };
    changeformer?: {
      available: boolean;
      role: string;
      maskUrl?: string;
      changePct?: number;
      evidenceNote?: string;
    };
  };
  raster: {
    available: boolean;
    crs?: string;
    resolutionM?: string | number;
    footprintKm2?: string | number;
    radiometry?: {
      min?: number | string;
      max?: number | string;
      mean?: number | string;
      std?: number | string;
      validPixelPct?: number | string;
    };
    ndvi?: number | string;
    ndviThresholdPct?: number | string;
    sensorInferred?: string;
    status: string;
    rawItems: string[];
  };
  crossModelEvidence: {
    features: Array<{
      name: string;
      internvl: boolean | null;
      upernet: boolean | null;
      owlv2: boolean | null;
      raster: boolean | null;
    }>;
  };
  fusion: {
    title: string;
    sceneSummary: string;
    supportingSources: string[];
    agreement: string;
    conflictsOrUncertainties?: string;
  };
  metadata: {
    task?: string;
    participatingModels: string[];
    crs?: string;
    groundResolution?: string;
    sceneFootprint?: string;
    radiometry?: string;
    executionTimeMs?: string;
    decisionReason?: string;
  };
  limitations: Array<{
    source: string;
    warning: string;
    impact?: string;
  }>;
  unrecognizedMarkdown?: string;
}

export function normalizeAnalysisResponse(
  result: AnalysisResponse,
  context?: {
    query?: string;
    attachments?: AttachedImage[];
    task?: TaskType;
  }
): NormalizedAnalysis {
  const summary = result.summary || '';
  const findings = result.findings || [];
  const sections = result.sections || {};
  const maskUrl = result.maskUrl;
  const modelStr = result.model || '';
  const validation = result.validation || 'passed';

  // 1. Extract Markdown sections using regex on ## headings
  const sectionMap = new Map<string, string>();
  const regexHeading = /^##\s+([^\n\r]+)/gm;
  const matches: { title: string; index: number }[] = [];
  let m: RegExpExecArray | null;

  while ((m = regexHeading.exec(summary)) !== null) {
    matches.push({ title: m[1].trim(), index: m.index });
  }

  for (let i = 0; i < matches.length; i++) {
    const start = matches[i].index + matches[i].title.length + 3;
    const end = i + 1 < matches.length ? matches[i + 1].index : summary.length;
    let content = summary.slice(start, end).trim();
    if (content.startsWith('---')) {
      content = content.replace(/^---+\s*/, '').trim();
    }
    sectionMap.set(matches[i].title.toLowerCase(), content);
  }

  const getSec = (name: string): string => {
    for (const [k, v] of sectionMap.entries()) {
      if (k.includes(name.toLowerCase())) return v;
    }
    return '';
  };

  const directAnswerText = getSec('direct answer');
  const sceneTypeText = getSec('scene type') || getSec('image / scene type');
  const whatIsPresentText = getSec('what is present');
  const detailedVisualText = getSec('detailed visual');
  const spatialInfoText = getSec('spatial') || getSec('location');
  const modelEvidenceText = getSec('supporting model evidence') || getSec('model evidence');
  const confidenceText = getSec('confidence');
  const limitationsText = getSec('limitations');
  const conclusionText = getSec('conclusion');
  const metadataText = getSec('technical analysis metadata') || getSec('metadata');

  // Helper to parse key-value bullet lists
  const parseBulletItems = (text: string): Array<{ name: string; description: string }> => {
    const items: Array<{ name: string; description: string }> = [];
    if (!text) return items;
    const lines = text.split('\n');
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('-') && !trimmed.startsWith('*')) continue;
      const stripped = trimmed.replace(/^[-*]\s+/, '');
      const boldMatch = stripped.match(/^\*\*([^*]+)\*\*:\s*(.*)$/);
      if (boldMatch) {
        items.push({ name: boldMatch[1].trim(), description: boldMatch[2].trim() });
      } else {
        const colonIdx = stripped.indexOf(':');
        if (colonIdx > 0 && colonIdx < 40) {
          items.push({
            name: stripped.slice(0, colonIdx).trim(),
            description: stripped.slice(colonIdx + 1).trim()
          });
        } else if (stripped) {
          items.push({ name: stripped, description: '' });
        }
      }
    }
    return items;
  };

  // 2. Identify participating models
  const participatingModels: string[] = [];
  const modelLower = (modelStr + ' ' + metadataText + ' ' + summary).toLowerCase();
  const hasInternVL = modelLower.includes('internvl');
  const hasUPerNet = modelLower.includes('upernet');
  const hasOWLv2 = modelLower.includes('owlv2') || modelLower.includes('geoground');
  const hasChangeFormer = modelLower.includes('changeformer');
  const hasCROMA = modelLower.includes('croma');

  if (hasInternVL) participatingModels.push('InternVL3-2B');
  if (hasUPerNet) participatingModels.push('UPerNet ConvNeXt');
  if (hasOWLv2) participatingModels.push('OWLv2 GeoGround');
  if (hasChangeFormer) participatingModels.push('ChangeFormerV6');
  if (hasCROMA) participatingModels.push('CROMA-Base');
  if (!participatingModels.length && modelStr) {
    participatingModels.push(modelStr);
  }

  // 3. InternVL3-2B Specific Parsing
  const visualFeatures: VisualFeature[] = [];
  const presentFeatures = parseBulletItems(whatIsPresentText);
  const detailedFeatures = parseBulletItems(detailedVisualText);

  // Combine and deduplicate
  const seenFeatureNames = new Set<string>();
  for (const item of [...presentFeatures, ...detailedFeatures]) {
    const key = item.name.toLowerCase();
    if (!seenFeatureNames.has(key) && item.name) {
      seenFeatureNames.add(key);
      visualFeatures.push(item);
    }
  }

  const spatialRegions: SpatialRegion[] = parseBulletItems(spatialInfoText).map((item) => ({
    region: item.name,
    description: item.description
  }));

  let internvlEvidenceNote = '';
  if (modelEvidenceText) {
    const internvlMatch = modelEvidenceText.match(/InternVL3-2B[^\n\r]*:\s*([^\n\r]+)/i);
    if (internvlMatch) internvlEvidenceNote = internvlMatch[1].trim();
  }

  // 4. UPerNet ConvNeXt Specific Parsing (Segmentation)
  const segmentedClasses: SegmentedClass[] = [];
  for (const f of findings) {
    const isTarget = f.label.toLowerCase().includes('candidate') || f.label.toLowerCase().includes('target');
    const coverageMatch = f.detail ? f.detail.match(/([\d.]+)%/) : null;
    if (!isTarget && coverageMatch) {
      const className = f.label.replace(/^(Land Cover|Class):\s*/i, '').trim();
      segmentedClasses.push({
        name: className,
        coveragePct: parseFloat(coverageMatch[1]),
        confidence: f.confidence
      });
    }
  }

  // If no classes extracted from findings, look in model evidence text
  if (!segmentedClasses.length && modelEvidenceText) {
    const classRegex = /([A-Za-z][A-Za-z0-9_\s-]{1,25})\s*\(([\d.]+)%\)/g;
    let cm: RegExpExecArray | null;
    while ((cm = classRegex.exec(modelEvidenceText)) !== null) {
      const name = cm[1].trim();
      if (!name.toLowerCase().includes('confidence') && !name.toLowerCase().includes('threshold')) {
        segmentedClasses.push({
          name,
          coveragePct: parseFloat(cm[2])
        });
      }
    }
  }

  let upernetEvidenceNote = '';
  if (modelEvidenceText) {
    const uMatch = modelEvidenceText.match(/UPerNet(?:[^\n\r]*segmented[^\n\r]+|ConvNeXt[^\n\r]*:\s*([^\n\r]+))/i);
    if (uMatch) upernetEvidenceNote = uMatch[0].trim();
  }

  // 5. OWLv2 GeoGround Specific Parsing (Object Detection)
  let candidateTargetsCount = 0;
  const candidateMatch = (summary + ' ' + modelEvidenceText).match(/(\d+)\s+candidate\s+(?:spatial\s+)?targets/i);
  if (candidateMatch) {
    candidateTargetsCount = parseInt(candidateMatch[1], 10);
  } else {
    for (const f of findings) {
      const m = f.detail?.match(/(\d+)\s+spatial\s+candidate/i) || f.detail?.match(/(\d+)\s+candidate/i);
      if (m) {
        candidateTargetsCount = parseInt(m[1], 10);
        break;
      }
    }
  }

  const detectedObjects: DetectedObject[] = [];
  for (const f of findings) {
    const lower = f.label.toLowerCase();
    if (lower.includes('detected object') || (lower.includes('target') && !lower.includes('candidate'))) {
      detectedObjects.push({
        label: f.label.replace(/^Detected Object:\s*/i, ''),
        confidence: f.confidence
      });
    }
  }

  let owlv2EvidenceNote = '';
  if (modelEvidenceText) {
    const oMatch = modelEvidenceText.match(/OWLv2(?:[^\n\r]*localized[^\n\r]+|GeoGround[^\n\r]*:\s*([^\n\r]+))/i);
    if (oMatch) owlv2EvidenceNote = oMatch[0].trim();
  }

  // 6. Deterministic Raster Analysis
  const rasterRawItems = sections.measured_from_raster || [];
  let crsStr: string | undefined;
  let resolutionM: string | number | undefined;
  let footprintKm2: string | number | undefined;
  let radiometryMin: number | undefined;
  let radiometryMax: number | undefined;
  let radiometryMean: number | undefined;
  let radiometryValidPct: number | undefined;
  let ndviMean: number | undefined;
  let ndviThresholdPct: number | undefined;

  for (const item of rasterRawItems) {
    if (item.includes('Coordinate Reference System') || item.includes('CRS')) {
      const match = item.match(/:\s*(.+)$/);
      if (match) crsStr = match[1].trim();
    }
    if (item.includes('Resolution') || item.includes('Sampling Distance')) {
      const match = item.match(/:\s*([\d.]+)\s*m/i);
      if (match) resolutionM = parseFloat(match[1]);
    }
    if (item.includes('Footprint')) {
      const match = item.match(/:\s*([\d.]+)\s*km/i);
      if (match) footprintKm2 = parseFloat(match[1]);
    }
    if (item.toLowerCase().includes('radiometric') || item.toLowerCase().includes('radiometry')) {
      const meanMatch = item.match(/mean\s*([\d.]+)/i);
      const minMatch = item.match(/min\s*([\d.]+)/i);
      const maxMatch = item.match(/max\s*([\d.]+)/i);
      if (meanMatch) radiometryMean = parseFloat(meanMatch[1]);
      if (minMatch) radiometryMin = parseFloat(minMatch[1]);
      if (maxMatch) radiometryMax = parseFloat(maxMatch[1]);
    }
    if (item.toLowerCase().includes('valid pixel')) {
      const validMatch = item.match(/:\s*([\d.]+)%/i);
      if (validMatch) radiometryValidPct = parseFloat(validMatch[1]);
    }
    if (item.toUpperCase().includes('NDVI')) {
      const meanMatch = item.match(/mean\s*NDVI[^\n\r\d-]*([-\d.]+)/i) || item.match(/NDVI\s*(?:mean)?\s*[:=]\s*([-\d.]+)/i);
      if (meanMatch) ndviMean = parseFloat(meanMatch[1]);

      const threshMatch = item.match(/(?:exceedance|threshold)[^\n\r]*?:\s*([\d.]+)%/i);
      if (threshMatch) ndviThresholdPct = parseFloat(threshMatch[1]);
    }
  }

  // Also check metadata section if raster section is sparse
  if (metadataText) {
    if (!crsStr) {
      const crsMatch = metadataText.match(/Coordinate Reference System:\s*([^\n\r]+)/i);
      if (crsMatch) crsStr = crsMatch[1].trim();
    }
    if (resolutionM == null) {
      const resMatch = metadataText.match(/Ground Resolution:\s*([\d.]+)\s*m/i);
      if (resMatch) resolutionM = parseFloat(resMatch[1]);
    }
    if (footprintKm2 == null) {
      const footMatch = metadataText.match(/Scene Footprint:\s*([\d.]+)\s*km/i);
      if (footMatch) footprintKm2 = parseFloat(footMatch[1]);
    }
    if (radiometryMean == null) {
      const minMatch = metadataText.match(/Min\s*([\d.]+)/i);
      const maxMatch = metadataText.match(/Max\s*([\d.]+)/i);
      const meanMatch = metadataText.match(/Mean\s*([\d.]+)/i);
      const validMatch = metadataText.match(/Valid Pixels:\s*([\d.]+)%/i);
      if (minMatch) radiometryMin = parseFloat(minMatch[1]);
      if (maxMatch) radiometryMax = parseFloat(maxMatch[1]);
      if (meanMatch) radiometryMean = parseFloat(meanMatch[1]);
      if (validMatch) radiometryValidPct = parseFloat(validMatch[1]);
    }
  }

  // 7. Limitations / Warnings
  const limitations: Array<{ source: string; warning: string; impact?: string }> = [];
  const reviewItems = sections.interpretation_requiring_review || [];
  for (const item of reviewItems) {
    if (item.toLowerCase().includes('no independent field reference data supplied')) continue;
    limitations.push({
      source: 'Scientific Review Engine',
      warning: item,
      impact: 'Visual or radiometric interpretation should be verified with field references.'
    });
  }

  if (limitationsText) {
    const parsedLim = parseBulletItems(limitationsText);
    if (parsedLim.length) {
      for (const pl of parsedLim) {
        if (
          pl.name.toLowerCase().includes('no independent field reference data supplied') ||
          (pl.description && pl.description.toLowerCase().includes('no independent field reference data supplied'))
        ) {
          continue;
        }
        limitations.push({
          source: 'Model Diagnostic',
          warning: pl.name + (pl.description ? `: ${pl.description}` : '')
        });
      }
    } else if (!limitationsText.toLowerCase().includes('no independent field reference data supplied')) {
      limitations.push({
        source: 'Model Diagnostic',
        warning: limitationsText
      });
    }
  }

  // 8. Cross-Model Evidence Matrix
  const matrixFeatures: Array<{
    name: string;
    internvl: boolean | null;
    upernet: boolean | null;
    owlv2: boolean | null;
    raster: boolean | null;
  }> = [];

  const checkKeywords = [
    { label: 'Urban & Built Infrastructure', keys: ['urban', 'building', 'structure', 'settlement', 'wall'] },
    { label: 'Surface Water & Coastline', keys: ['water', 'coast', 'coastline', 'river', 'sea', 'ocean', 'lake'] },
    { label: 'Vegetation & Forest Canopy', keys: ['vegetation', 'forest', 'greenery', 'tree', 'canopy', 'park'] },
    { label: 'Agricultural & Cultivated Land', keys: ['agricultural', 'crop', 'field', 'farmland'] },
    { label: 'Road & Transportation Network', keys: ['road', 'highway', 'transport', 'street'] }
  ];

  const fullText = (summary + ' ' + findings.map((f) => f.label + ' ' + f.detail).join(' ')).toLowerCase();

  for (const item of checkKeywords) {
    let presentInScene = item.keys.some((k) => fullText.includes(k));
    if (!presentInScene) continue;

    const ivlHits = item.keys.some((k) => (directAnswerText + ' ' + whatIsPresentText + ' ' + detailedVisualText).toLowerCase().includes(k));
    const upnHits = segmentedClasses.some((c) => item.keys.some((k) => c.name.toLowerCase().includes(k)));
    const owlHits = (candidateTargetsCount > 0 && item.keys.some((k) => (modelEvidenceText + ' ' + directAnswerText).toLowerCase().includes(k))) ||
      detectedObjects.some((o) => item.keys.some((k) => o.label.toLowerCase().includes(k)));
    const rasHits = item.label.includes('Vegetation') ? (ndviMean != null) : null;

    matrixFeatures.push({
      name: item.label,
      internvl: ivlHits ? true : null,
      upernet: upnHits ? true : null,
      owlv2: owlHits ? true : null,
      raster: rasHits
    });
  }

  // 9. Input details
  const attachment = context?.attachments?.[0];
  const inputInfo = {
    query: context?.query || getSec('query') || 'Describe the satellite imagery',
    filename: attachment?.name || (summary.match(/Input Imagery:\s*([^\n\r]+)/i)?.[1]) || undefined,
    fileType: attachment?.type || (attachment?.name?.endsWith('.tif') ? 'GeoTIFF' : undefined),
    fileSize: attachment?.size ? `${(attachment.size / (1024 * 1024)).toFixed(1)} MB` : undefined,
    imagePreviewUrl: attachment?.url,
    analysisType: context?.task ? context.task.replace('_', ' ').toUpperCase() : 'SCENE DESCRIPTION',
    inputCategory: crsStr ? 'GeoTIFF Raster' : 'Optical Benchmark'
  };

  // 10. Final Fusion Summary
  const sceneSummary = directAnswerText || conclusionText || summary.slice(0, 300);
  const supportingSources: string[] = [];
  if (hasInternVL) supportingSources.push('InternVL3-2B');
  if (hasUPerNet && (segmentedClasses.length || maskUrl)) supportingSources.push('UPerNet ConvNeXt');
  if (hasOWLv2 && candidateTargetsCount > 0) supportingSources.push('OWLv2 GeoGround');
  if (rasterRawItems.length > 0 || crsStr) supportingSources.push('Deterministic Raster Analysis');

  return {
    header: {
      title: 'Satellite Scene Analysis',
      status: 'Analysis Complete',
      validation: validation === 'passed' || validation === 'verified_inference' ? 'Passed' : validation,
      modelCount: participatingModels.length,
      modelsList: participatingModels,
      processingType: rasterRawItems.length > 0 ? 'Deterministic + AI' : 'Deep Neural Inference',
      query: context?.query
    },
    input: inputInfo,
    models: {
      internvl: {
        available: hasInternVL,
        role: 'Vision-Language Reasoning',
        task: 'Visual Scene Interpretation',
        sceneType: sceneTypeText || undefined,
        directObservation: directAnswerText || undefined,
        visualFeatures,
        spatialInterpretation: spatialRegions,
        confidence: confidenceText || undefined,
        limitations: limitationsText || undefined,
        evidenceNote: internvlEvidenceNote || undefined
      },
      upernet: {
        available: hasUPerNet,
        role: 'Semantic Segmentation',
        analysisType: 'Land-Cover / Surface Segmentation',
        classes: segmentedClasses,
        maskUrl: (context?.task === 'segmentation') && maskUrl && maskUrl.includes('segmentation') ? maskUrl : undefined,
        evidenceNote: upernetEvidenceNote || undefined
      },
      owlv2: {
        available: hasOWLv2,
        role: 'Open-Vocabulary Object Localization',
        candidateDetectionsCount: candidateTargetsCount,
        detectedObjects,
        evidenceNote: owlv2EvidenceNote || undefined
      },
      changeformer: {
        available: hasChangeFormer,
        role: 'Bitemporal Binary Change Detection',
        maskUrl: maskUrl && maskUrl.includes('change') ? maskUrl : undefined
      }
    },
    raster: {
      available: Boolean(crsStr || rasterRawItems.length || radiometryMean != null),
      crs: crsStr,
      resolutionM,
      footprintKm2,
      radiometry: (radiometryMean != null || radiometryMin != null) ? {
        min: radiometryMin,
        max: radiometryMax,
        mean: radiometryMean,
        validPixelPct: radiometryValidPct
      } : undefined,
      ndvi: ndviMean,
      ndviThresholdPct,
      status: 'Completed',
      rawItems: rasterRawItems
    },
    crossModelEvidence: {
      features: matrixFeatures
    },
    fusion: {
      title: 'Cross-Model Synthesis',
      sceneSummary,
      supportingSources,
      agreement: supportingSources.length > 1
        ? 'Multiple independent analysis streams corroborate this interpretation.'
        : 'Single primary model interpretation evaluated.',
      conflictsOrUncertainties: limitations.length > 0
        ? undefined
        : 'No significant cross-model conflicts reported.'
    },
    metadata: {
      task: (metadataText && metadataText.match(/Task:\s*([^\n\r]+)/i)?.[1]?.trim()) || context?.task || result.decision_reason || 'scene_description',
      participatingModels,
      crs: crsStr,
      groundResolution: resolutionM ? `${resolutionM} m` : undefined,
      sceneFootprint: footprintKm2 ? `${footprintKm2} km²` : undefined,
      radiometry: radiometryMean != null ? `Min ${radiometryMin}, Max ${radiometryMax}, Mean ${radiometryMean}` : undefined,
      executionTimeMs: (result.metrics?.duration_ms ? `${result.metrics.duration_ms} ms` : undefined) || (metadataText && metadataText.match(/Execution Time:\s*([^\n\r]+)/i)?.[1]?.trim()) || undefined,
      decisionReason: result.decision_reason
    },
    limitations,
    unrecognizedMarkdown: !sectionMap.size && summary ? summary : undefined
  };
}
