import React from 'react';
import { MenuIcon, SunIcon, MoonIcon, ChevronDownIcon } from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import { PAGE_LABELS } from '../data/navigation';

export function Topbar() {
  const { page, theme, toggleTheme, openDrawer, toggleSidebar, modelSettings } = useApp();
  return (
    <header className="topbar">
      <button className="side-toggle" onClick={toggleSidebar} aria-label="Toggle navigation">
        <MenuIcon size={16} />
      </button>
      <div className="brand">
        <div className="logo" aria-hidden="true">S</div>
        <span>SatQuery AI</span>
      </div>
      <div className="crumb">{PAGE_LABELS[page]}</div>
      <div className="topright">
        <button
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}>
          
          {theme === 'dark' ? <SunIcon size={14} /> : <MoonIcon size={14} />}
          <span>{theme === 'dark' ? 'Light' : 'Dark'}</span>
        </button>
        <button className="btn" onClick={openDrawer} aria-label="Open analysis model settings">
          <span className="hide-sm">Analyst ·</span> {modelSettings.model}
          <ChevronDownIcon size={14} />
        </button>
      </div>
    </header>);

}