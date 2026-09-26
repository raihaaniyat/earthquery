import React from 'react';
import { useApp } from '../contexts/AppContext';
import { Topbar } from './Topbar';
import { Sidebar } from './Sidebar';
import { ModelDrawer } from './ModelDrawer';
import { Toast } from './Toast';
import { Home } from '../pages/Home';
import { Chat } from '../pages/Chat';
import { Imagery } from '../pages/Imagery';
import { Advanced } from '../pages/Advanced';
import { Temporal } from '../pages/Temporal';
import { MapAoi } from '../pages/MapAoi';
import { Comparison } from '../pages/Comparison';
import { History } from '../pages/History';
import { Reports } from '../pages/Reports';
import type { PageId } from '../types/app';

const PAGES: Record<PageId, () => JSX.Element> = {
  home: Home,
  chat: Chat,
  analyze: Imagery,
  advanced: Advanced,
  temporal: Temporal,
  map: MapAoi,
  comparison: Comparison,
  history: History,
  reports: Reports
};

export function AppShell() {
  const { page, sidebarCollapsed, mobileNavOpen, closeMobileNav } = useApp();
  const Page = PAGES[page];
  return (
    <>
      <Topbar />
      <Sidebar />
      {mobileNavOpen && <div className="nav-scrim" onClick={closeMobileNav} aria-hidden="true" />}
      <main className={`main${sidebarCollapsed ? ' collapsed' : ''}${page === 'home' ? ' is-home' : ''}`}>
        <Page />
      </main>
      <ModelDrawer />
      <Toast />
    </>);

}