import React from 'react';
import ReactDOM from 'react-dom/client';
import { ProjectProvider } from '../../src/contexts/ProjectContext';
import HermesWorkspace from '../../src/features/hermes/ui/HermesWorkspace';

declare global {
  interface Window {
    unmountHermesFixture: () => void;
  }
}

const root = ReactDOM.createRoot(document.getElementById('root')!);
root.render(
  <ProjectProvider>
    <HermesWorkspace />
  </ProjectProvider>,
);
window.unmountHermesFixture = () => root.unmount();
