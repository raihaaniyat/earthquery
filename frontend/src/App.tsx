import React from 'react';
import { AppProvider } from './contexts/AppContext';
import { WorkspaceProvider } from './contexts/WorkspaceContext';
import { AppShell } from './components/AppShell';

export function App() {
  return (
    <AppProvider>
      <WorkspaceProvider>
        <AppShell />
      </WorkspaceProvider>
    </AppProvider>);

}