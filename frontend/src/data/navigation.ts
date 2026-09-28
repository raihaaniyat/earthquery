import {
  SparklesIcon,
  GlobeIcon,
  ImageIcon,
  CrosshairIcon,
  LayersIcon,
  Clock3Icon,
  ApertureIcon,
  ArrowLeftRightIcon,
  RulerIcon,
  FlameIcon,
  WavesIcon,
  HistoryIcon,
  FileTextIcon,
  type LucideIcon
} from 'lucide-react';
import type { AdvancedToolId, PageId } from '../types/app';

export interface NavItem {
  page: PageId;
  label: string;
  icon: LucideIcon;
}

export interface ToolNavItem {
  tool: AdvancedToolId;
  label: string;
  icon: LucideIcon;
}

export const workspaceNav: NavItem[] = [
  { page: 'home', label: 'AI Analyst', icon: SparklesIcon },
  { page: 'geotiff', label: 'GeoTIFF viewer', icon: GlobeIcon },
  { page: 'analyze', label: 'Imagery', icon: ImageIcon },
  { page: 'map', label: 'Map & AOI', icon: CrosshairIcon },
  { page: 'advanced', label: 'Advanced analysis', icon: LayersIcon },
  { page: 'temporal', label: 'Temporal', icon: Clock3Icon }
];

export const toolNav: ToolNavItem[] = [
  { tool: 'spectral', label: 'Spectral', icon: ApertureIcon },
  { tool: 'change', label: 'Change detection', icon: ArrowLeftRightIcon },
  { tool: 'measure', label: 'Measurement', icon: RulerIcon },
  { tool: 'fire', label: 'Fire / hotspots', icon: FlameIcon },
  { tool: 'water', label: 'Water / ocean', icon: WavesIcon }
];

export const bottomNav: NavItem[] = [
  { page: 'history', label: 'History', icon: HistoryIcon },
  { page: 'reports', label: 'Reports', icon: FileTextIcon }
];

export const PAGE_LABELS: Record<PageId, string> = {
  home: 'AI Analyst',
  chat: 'AI Analyst',
  geotiff: 'GeoTIFF viewer',
  analyze: 'Imagery workspace',
  advanced: 'Advanced analysis',
  temporal: 'Temporal analysis',
  map: 'Map & AOI',
  comparison: 'Multi-image comparison',
  history: 'History',
  reports: 'Reports'
};