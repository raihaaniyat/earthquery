import React from 'react';
import { ArrowRightIcon, FocusIcon, Trash2Icon, CopyIcon } from 'lucide-react';
import { StateNotice } from '../StateNotice';
import { aoiToGeoJson, formatArea, formatBbox, formatDistance, formatLatLng, validateAoi } from '../../utils/geo';
import type { Aoi } from '../../types/app';

interface AoiPanelProps {
  aoi: Aoi | null;
  question: string;
  setQuestion: (q: string) => void;
  onAsk: () => void;
  onZoom: () => void;
  onClear: () => void;
  onCopy: (text: string) => void;
  onDraw: () => void;
}

export function AoiPanel({ aoi, question, setQuestion, onAsk, onZoom, onClear, onCopy, onDraw }: AoiPanelProps) {
  const aoiError = validateAoi(aoi);
  return (
    <div className="panel panel-pad">
      <div className="panel-title">Selected area → AI question</div>
      <div className="aoi-msg">
        <textarea
          className="field"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask something specifically about the selected region..."
          aria-label="Question about the selected area" />
        
        <button className="btn green" onClick={onAsk} disabled={!aoi || Boolean(aoiError)}>
          Ask AI <ArrowRightIcon size={14} />
        </button>
      </div>

      {!aoi ?
      <StateNotice state={{ status: 'idle' }} idleText="No AOI selected. Use Rectangle, Polygon or Point in the toolbar, then click on the map." /> :

      <>
          {aoiError && <StateNotice state={{ status: 'invalid', message: aoiError }} />}
          <dl className="aoi-details">
            <div>
              <dt>Geometry</dt>
              <dd style={{ textTransform: 'capitalize' }}>{aoi.type}{aoi.type === 'polygon' ? ` · ${aoi.coordinates.length} vertices` : ''}</dd>
            </div>
            <div>
              <dt>Area / perimeter</dt>
              <dd>{aoi.type === 'point' ? '—' : `${formatArea(aoi.areaKm2)} · ${formatDistance(aoi.perimeterKm)}`}</dd>
            </div>
            <div>
              <dt>Centroid</dt>
              <dd>{formatLatLng(aoi.centroid)}</dd>
            </div>
            <div>
              <dt>Bounding box (W, S, E, N)</dt>
              <dd>{formatBbox(aoi.bbox)}</dd>
            </div>
          </dl>
        </>
      }
      <div className="actions-row">
        {aoi ?
        <>
            <button className="btn small" onClick={onZoom}><FocusIcon size={12} /> Zoom to AOI</button>
            <button className="btn small" onClick={() => onCopy(JSON.stringify(aoiToGeoJson(aoi)))}><CopyIcon size={12} /> Copy GeoJSON</button>
            <button className="btn small" onClick={() => onCopy(formatBbox(aoi.bbox))}><CopyIcon size={12} /> Copy bbox</button>
            <button className="btn small danger-text" onClick={onClear}><Trash2Icon size={12} /> Clear AOI</button>
          </> :

        <button className="btn small" onClick={onDraw}>Draw rectangle AOI</button>
        }
      </div>
    </div>);

}