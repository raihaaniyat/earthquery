import React, { useRef } from 'react';
import { PlusIcon, CrosshairIcon, ChevronDownIcon, ArrowRightIcon, SparklesIcon, XIcon, FileImageIcon, MapPinIcon } from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import { useWorkspace } from '../contexts/WorkspaceContext';
import { suggestions } from '../data/advancedTools';
import { describeAoi } from '../utils/geo';

export function Home() {
  const { openDrawer, modelSettings, navigate, toast } = useApp();
  const { query, setQuery, attachments, addFiles, removeAttachment, aoi, setAoi, startAnalysis, setMapTool } = useWorkspace();
  const fileRef = useRef<HTMLInputElement>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);

  return (
    <section className="page page-home">
      <div className="hero-premium">
        <div className="hero-copy">
          <div className="hero-kicker">SATQUERY AI · EARTH INTELLIGENCE</div>
          <h1>
            AI satellite analysis,
            <br />
            <span>without the complexity.</span>
          </h1>
          <p>
            Ask a question, attach imagery, draw an area, or select a map region. SatQuery reveals only the controls needed for that task.
          </p>
        </div>

        <div className="composer">
          <div className="composer-inner">
            <textarea
              ref={textRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) startAnalysis();
              }}
              placeholder="Ask about the whole image, a selected area, or multiple dates..."
              aria-label="Analysis question" />
            
            {(attachments.length > 0 || aoi) &&
            <div className="composer-files">
                {attachments.map((a) =>
              <span className="file-chip" key={a.id}>
                    {a.previewable ? <img src={a.url} alt="" /> : <span className="file-ph"><FileImageIcon size={14} /></span>}
                    <span className="file-name">{a.name}</span>
                    <button onClick={() => removeAttachment(a.id)} aria-label={`Remove ${a.name}`}>
                      <XIcon size={12} />
                    </button>
                  </span>
              )}
                {aoi &&
              <span className="file-chip">
                    <span className="file-ph"><MapPinIcon size={14} /></span>
                    <span className="file-name">AOI · {describeAoi(aoi)}</span>
                    <button onClick={() => setAoi(null)} aria-label="Remove AOI">
                      <XIcon size={12} />
                    </button>
                  </span>
              }
              </div>
            }
            <div className="composer-bottom">
              <button className="btn" onClick={() => fileRef.current?.click()}>
                <PlusIcon size={14} /> Attach imagery
              </button>
              <input
                ref={fileRef}
                type="file"
                multiple
                accept="image/*,.tif,.tiff"
                hidden
                onChange={(e) => {
                  if (e.target.files) void addFiles(e.target.files);
                  e.target.value = '';
                }} />
              
              <button
                className="btn"
                onClick={() => {
                  setMapTool('rectangle');
                  navigate('map');
                  toast('Draw an AOI on the map');
                }}>
                
                <CrosshairIcon size={14} /> {aoi ? 'Edit AOI' : 'Select AOI'}
              </button>
              <button className="btn" onClick={openDrawer}>
                Model: <b>{modelSettings.model}</b> <ChevronDownIcon size={14} />
              </button>
              <span className="spacer" />
              <button className="btn primary" onClick={() => startAnalysis()}>
                Analyze <ArrowRightIcon size={14} />
              </button>
            </div>
          </div>
        </div>

        <div className="suggestions">
          {suggestions.map((s) =>
          <button
            key={s.label}
            className="suggestion"
            onClick={() => {
              setQuery(s.query);
              textRef.current?.focus();
            }}>
            
              <SparklesIcon size={12} /> {s.label}
            </button>
          )}
        </div>
      </div>
    </section>);

}