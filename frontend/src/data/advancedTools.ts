import type { AdvancedToolId } from '../types/app';

export const advancedTools: {id: AdvancedToolId;number: string;title: string;description: string;}[] = [
{ id: 'temporal', number: '01', title: 'Temporal', description: 'Compare multiple dates, detect trends, events and seasonal change.' },
{ id: 'spectral', number: '02', title: 'Spectral', description: 'Band combinations, spectral indices and pixel-level inspection.' },
{ id: 'change', number: '03', title: 'Change Detection', description: 'Before/after comparison, change masks and evidence review.' },
{ id: 'measure', number: '04', title: 'Measurement', description: 'Measure area, distance, perimeter and coordinates on the map.' },
{ id: 'fire', number: '05', title: 'Fire', description: 'Explore fire-related imagery, hotspots and burn-area analysis.' },
{ id: 'water', number: '06', title: 'Ocean / Water', description: 'Water extent, shoreline and surface-change analysis.' }];


export const suggestions: {label: string;query: string;}[] = [
{ label: 'Detect change', query: 'What changed between these two images?' },
{ label: 'Temporal analysis', query: 'Analyze vegetation change over time' },
{ label: 'Analyze selected AOI', query: 'Analyze this selected area' },
{ label: 'Find buildings', query: 'Find buildings in this image' }];