import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ModelSettings, PageId, Theme } from '../types/app';

export interface ToastState {
  id: number;
  message: string;
  tone: 'default' | 'success' | 'error';
}

interface AppContextValue {
  page: PageId;
  navigate: (page: PageId) => void;
  theme: Theme;
  toggleTheme: () => void;
  toast: (message: string, tone?: ToastState['tone']) => void;
  toastState: ToastState | null;
  drawerOpen: boolean;
  openDrawer: () => void;
  closeDrawer: () => void;
  modelSettings: ModelSettings;
  updateModelSettings: (patch: Partial<ModelSettings>) => void;
  sidebarCollapsed: boolean;
  mobileNavOpen: boolean;
  toggleSidebar: () => void;
  closeMobileNav: () => void;
}

const AppContext = createContext<AppContextValue | null>(null);

const DEFAULT_MODEL: ModelSettings = {
  model: 'Auto',
  routing: 'auto',
  validation: true,
  comparisonMode: 'before-after',
  output: 'visual'
};

export function AppProvider({ children }: {children: React.ReactNode;}) {
  const [page, setPage] = useState<PageId>('home');
  const [theme, setTheme] = useState<Theme>(() =>
  document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark'
  );
  const [toastState, setToastState] = useState<ToastState | null>(null);
  const toastTimer = useRef<number | undefined>(undefined);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [modelSettings, setModelSettings] = useState<ModelSettings>(DEFAULT_MODEL);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem('satquery-theme', theme);
    } catch {

      /* ignore */}
  }, [theme]);

  const toast = useCallback((message: string, tone: ToastState['tone'] = 'default') => {
    window.clearTimeout(toastTimer.current);
    setToastState({ id: Date.now(), message, tone });
    toastTimer.current = window.setTimeout(() => setToastState(null), 2400);
  }, []);

  const navigate = useCallback((next: PageId) => {
    setPage(next);
    setMobileNavOpen(false);
    window.scrollTo({ top: 0 });
  }, []);

  const toggleSidebar = useCallback(() => {
    if (window.innerWidth <= 850) setMobileNavOpen((o) => !o);else
    setSidebarCollapsed((c) => !c);
  }, []);

  const value = useMemo<AppContextValue>(
    () => ({
      page,
      navigate,
      theme,
      toggleTheme: () => setTheme((t) => t === 'dark' ? 'light' : 'dark'),
      toast,
      toastState,
      drawerOpen,
      openDrawer: () => setDrawerOpen(true),
      closeDrawer: () => setDrawerOpen(false),
      modelSettings,
      updateModelSettings: (patch) => setModelSettings((m) => ({ ...m, ...patch })),
      sidebarCollapsed,
      mobileNavOpen,
      toggleSidebar,
      closeMobileNav: () => setMobileNavOpen(false)
    }),
    [page, navigate, theme, toast, toastState, drawerOpen, modelSettings, sidebarCollapsed, mobileNavOpen, toggleSidebar]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used inside AppProvider');
  return ctx;
}