import type { ModelId } from '../types/app';

/**
 * Model options available in the frontend model-selector drawer.
 * These map to the actual models deployed and verified in the SatQuery backend:
 *   internvl3, geoground (OWLv2), changeformer, upernet, croma,
 *   change_vqa, optical_sar_head
 */
export const models: {id: ModelId; title: string; description: string;}[] = [
  { id: 'Auto',             title: 'Auto routing',      description: 'SatQuery identifies the task and chooses a compatible model via LangGraph.' },
  { id: 'InternVL3',        title: 'InternVL3-2B',      description: 'Vision-language VQA specialist — single-image reasoning and captioning (4 GB VRAM).' },
  { id: 'GeoGround',        title: 'OWLv2 GeoGround',   description: 'Open-vocabulary zero-shot object detection and visual grounding (1.2 GB VRAM).' },
  { id: 'ChangeFormerV6',   title: 'ChangeFormerV6',     description: 'Siamese transformer for bitemporal binary change detection (CPU).' },
  { id: 'UPerNet',          title: 'UPerNet ConvNeXt',   description: 'Semantic segmentation for land-cover classification (2 GB VRAM).' },
  { id: 'CROMA',            title: 'CROMA-Base',         description: 'Dual ViT-B optical/SAR feature extraction backbone (2.5 GB VRAM).' },
  { id: 'ChangeVQA',        title: 'Change VQA',         description: 'Paired-image change reasoning with natural language answers (1.8 GB VRAM).' },
  { id: 'OpticalSAR',       title: 'Optical-SAR Head',   description: 'Multilabel land classification from optical+SAR using CROMA features (2.5 GB VRAM).' },
];