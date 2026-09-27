import React, { useState } from 'react';
import { useApp } from '../../contexts/AppContext';
import { useWorkspace } from '../../contexts/WorkspaceContext';
import { StateNotice } from '../StateNotice';
import { AnalysisResult } from '../AnalysisResult';
import { CurtainViewer } from '../CurtainViewer';
import type { ChatSession } from '../../types/app';

import { AnalysisPipelineLoading } from '../analysis/AnalysisPipelineLoading';

export function ChatResult({ chat, onRetry }: {chat: ChatSession;onRetry: () => void;}) {
  const { navigate } = useApp();
  const { setComparisonPair, createReport } = useWorkspace();
  const [reported, setReported] = useState(false);
  const run = chat.run;
  if (run.status === 'idle') return null;

  const previewable = chat.attachments.filter((a) => a.previewable);
  const hasPair = previewable.length >= 2;
  const [before, after] = previewable;

  return (
    <div className="msg">
      <div className="avatar ai">AI</div>
      <div className="msgbody">
        <div className="who">SatQuery AI</div>
        <div className="bubble">
          {run.status === 'loading' ? (
            <AnalysisPipelineLoading message={run.message} />
          ) : (

          <>
              <b>{run.status === 'success' ? 'Analysis complete.' : 'Model analysis did not complete.'}</b>
              <div className={hasPair ? 'result-grid' : undefined} style={{ marginTop: 10 }}>
                {hasPair &&
              <div>
                    <CurtainViewer
                  beforeUrl={before.url}
                  afterUrl={after.url}
                  beforeLabel={before.name}
                  afterLabel={after.name}
                  mode="curtain"
                  emptyText=""
                  height={340} />
                
                    <p className="muted" style={{ fontSize: 12, margin: '8px 0 0' }}>
                      Visual evidence from your attached images. Drag to compare.
                    </p>
                  </div>
              }
                <div>
                  {run.status === 'success' ? (
                    <AnalysisResult 
                      result={run.data} 
                      query={chat.query}
                      attachments={chat.attachments}
                      task={chat.task}
                    />
                  ) : (
                    <StateNotice state={run} onRetry={onRetry} />
                  )}
                  <div className="actions-row">
                    {hasPair &&
                  <button
                    className="btn"
                    onClick={() => {
                      setComparisonPair({ before, after }, true);
                      navigate('comparison');
                    }}>
                    
                        Compute pixel difference
                      </button>
                  }
                    <button className="btn" onClick={() => navigate('advanced')}>Open advanced analysis</button>
                    {chat.historyId &&
                  <button
                    className="btn"
                    disabled={reported}
                    onClick={() => {
                      createReport(chat.historyId as string);
                      setReported(true);
                    }}>
                    
                        {reported ? 'Report generated' : 'Generate report'}
                      </button>
                  }
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>);

}