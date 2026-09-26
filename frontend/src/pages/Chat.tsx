import React from 'react';
import { PlusIcon, MessageSquareIcon, MapPinIcon, FileImageIcon } from 'lucide-react';
import { useWorkspace } from '../contexts/WorkspaceContext';
import { ChatConfigCard } from '../components/chat/ChatConfigCard';
import { ChatResult } from '../components/chat/ChatResult';
import { EmptyState } from '../components/EmptyState';
import { TASK_LABELS, describeAoi } from '../utils/geo';
import { formatBytes } from '../utils/files';

export function Chat() {
  const { chat, rerunChat, newAnalysis } = useWorkspace();

  return (
    <section className="page">
      <div className="chat-layout">
        <div className="section-head">
          <div>
            <h2>AI Analyst</h2>
            <p>Task-aware satellite analysis workspace</p>
          </div>
          <button className="btn" onClick={newAnalysis}>
            <PlusIcon size={14} /> New analysis
          </button>
        </div>

        {!chat ?
        <div className="panel">
            <EmptyState
            icon={MessageSquareIcon}
            title="No active analysis"
            text="Ask a question, attach imagery or select an AOI to start an analysis."
            action={<button className="btn primary" onClick={newAnalysis}>Start a new analysis</button>} />
          
          </div> :

        <div className="chat-thread">
            <div className="msg">
              <div className="avatar user">U</div>
              <div className="msgbody">
                <div className="who">You</div>
                <div className="bubble">{chat.query}</div>
                {(chat.attachments.length > 0 || chat.aoi) &&
              <div className="attachments">
                    {chat.attachments.map((a) =>
                <div className="attachment" key={a.id}>
                        <div className="thumb">
                          {a.previewable ? <img src={a.url} alt={a.name} /> : <FileImageIcon size={20} />}
                        </div>
                        <b>{a.name}</b>
                        <small>{a.previewable ? `${a.width}×${a.height}` : 'Backend-only format'} · {formatBytes(a.size)}</small>
                      </div>
                )}
                    {chat.aoi &&
                <div className="attachment">
                        <div className="thumb"><MapPinIcon size={20} /></div>
                        <b>Selected AOI</b>
                        <small>{describeAoi(chat.aoi)}</small>
                      </div>
                }
                  </div>
              }
              </div>
            </div>

            <div className="msg">
              <div className="avatar ai">AI</div>
              <div className="msgbody">
                <div className="who">SatQuery AI</div>
                <div className="bubble">
                  <b>{TASK_LABELS[chat.task]} task identified.</b>
                  <p>
                    {chat.attachments.length >= 2 ?
                  `${chat.attachments.length} images received, so the request can be analyzed as a comparison.` :
                  chat.aoi ?
                  'The selected AOI and imagery date range will be sent with the request.' :
                  chat.attachments.length === 1 ?
                  'One image received for single-scene analysis.' :
                  'No imagery attached — the backend will resolve imagery from your query if supported.'}
                  </p>
                  <ChatConfigCard chat={chat} onRun={rerunChat} />
                </div>
              </div>
            </div>

            <ChatResult key={chat.historyId ?? chat.id} chat={chat} onRetry={rerunChat} />
          </div>
        }
      </div>
    </section>);

}