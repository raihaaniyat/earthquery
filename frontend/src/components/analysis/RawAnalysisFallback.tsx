import React, { useState } from 'react';
import { FileTextIcon, ChevronDownIcon, ChevronUpIcon } from 'lucide-react';
import { markdownToHtml } from '../../utils/report';

interface RawAnalysisFallbackProps {
  content?: string;
  title?: string;
  defaultExpanded?: boolean;
}

export const RawAnalysisFallback: React.FC<RawAnalysisFallbackProps> = ({ 
  content, 
  title = 'Additional Analysis Output',
  defaultExpanded = false
}) => {
  const [isOpen, setIsOpen] = useState(defaultExpanded);

  if (!content || !content.trim()) {
    return null;
  }

  const html = markdownToHtml(content);

  return (
    <section 
      className="rounded-2xl border border-[var(--line)] bg-[var(--panel-solid)] shadow-md backdrop-blur-sm overflow-hidden"
    >
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 sm:p-5 text-left hover:bg-[var(--surface-1)] transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--surface-2)] text-[var(--muted)] border border-[var(--line)]">
            <FileTextIcon className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--muted)] font-semibold">
                Raw Telemetry Fallback
              </span>
            </div>
            <h3 className="text-sm font-semibold text-[var(--ink)] flex items-center gap-2">
              {title}
            </h3>
          </div>
        </div>

        <span className="text-xs text-[var(--muted)] font-mono flex items-center gap-1">
          {isOpen ? 'Hide raw narrative' : 'View raw narrative'}
          {isOpen ? <ChevronUpIcon className="h-4 w-4" /> : <ChevronDownIcon className="h-4 w-4" />}
        </span>
      </button>

      {isOpen && (
        <div className="p-5 border-t border-[var(--line)] bg-[var(--surface-1)]/40">
          <div
            className="prose prose-invert max-w-none text-xs text-[var(--ink)] space-y-2 leading-relaxed font-sans"
            dangerouslySetInnerHTML={{ __html: html }}
          />
        </div>
      )}
    </section>
  );
};
