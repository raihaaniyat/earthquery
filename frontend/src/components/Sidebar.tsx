import React, { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { PlusIcon, ChevronDownIcon } from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import { useWorkspace } from '../contexts/WorkspaceContext';
import { bottomNav, toolNav, workspaceNav, type NavItem } from '../data/navigation';
import type { AdvancedToolId, PageId } from '../types/app';

export function Sidebar() {
  const { page, navigate, sidebarCollapsed, mobileNavOpen } = useApp();
  const { newAnalysis, setActiveTool, setMapTool, activeTool } = useWorkspace();
  const [toolsOpen, setToolsOpen] = useState(true);

  const isActive = (p: PageId) => p === page || p === 'home' && page === 'chat';

  const openTool = (tool: AdvancedToolId) => {
    if (tool === 'change') return navigate('comparison');
    if (tool === 'measure') {
      setMapTool('measure');
      return navigate('map');
    }
    setActiveTool(tool);
    navigate('advanced');
  };

  const toolActive = (tool: AdvancedToolId) =>
  tool === 'change' && page === 'comparison' || page === 'advanced' && activeTool === tool;

  const renderItem = (item: NavItem) => {
    const Icon = item.icon;
    return (
      <button
        key={item.page}
        className={`side-item${isActive(item.page) ? ' active' : ''}`}
        onClick={() => navigate(item.page)}
        title={sidebarCollapsed ? item.label : undefined}
        aria-current={isActive(item.page) ? 'page' : undefined}>
        
        <Icon size={16} />
        <span className="side-text">{item.label}</span>
      </button>);

  };

  return (
    <aside
      className={`sidebar${sidebarCollapsed ? ' collapsed' : ''}${mobileNavOpen ? ' mobile-open' : ''}`}
      aria-label="Workspace navigation">
      
      <div className="side-section">
        <button className="side-new" onClick={newAnalysis} title={sidebarCollapsed ? 'New analysis' : undefined}>
          <PlusIcon size={15} />
          <span className="side-text">New analysis</span>
        </button>
      </div>
      <nav className="side-section">
        <div className="side-label">Workspace</div>
        {workspaceNav.map(renderItem)}
      </nav>
      <div className="side-section">
        <button className="side-tools-head" onClick={() => setToolsOpen((o) => !o)} aria-expanded={toolsOpen}>
          <span className="side-label">Tools</span>
          <ChevronDownIcon className="chev" size={14} />
        </button>
        <AnimatePresence initial={false}>
          {toolsOpen &&
          <motion.div
            className="tools-list"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: [0.23, 1, 0.32, 1] }}>
            
              {toolNav.map((t) => {
              const Icon = t.icon;
              return (
                <button
                  key={t.tool}
                  className={`side-item${toolActive(t.tool) ? ' active' : ''}`}
                  onClick={() => openTool(t.tool)}
                  title={sidebarCollapsed ? t.label : undefined}>
                  
                    <Icon size={16} />
                    <span className="side-text">{t.label}</span>
                  </button>);

            })}
            </motion.div>
          }
        </AnimatePresence>
      </div>
      <nav className="side-section side-bottom">{bottomNav.map(renderItem)}</nav>
    </aside>);

}