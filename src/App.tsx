/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect, useRef } from 'react';
import { HashRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import ModernHeader from './components/layout/ModernHeader';
import ModernAgentLibrary from './features/agents/components/ModernAgentLibrary';
import WorkflowCanvas, { WorkflowCanvasRef, WorkflowRecipe } from './features/workflows/components/Canvas/WorkflowCanvas';
import WorkflowLibraryView from './features/workflows/components/Library/WorkflowLibraryView';
import NodeConfigPanel from './features/workflows/components/NodeConfig/NodeConfigPanel';
import SettingsView from './pages/SettingsPage';
import KnowledgeBaseView from './features/knowledge/components/KnowledgeBaseView';
import AgentLoadouts from './features/agents/components/AgentLoadouts';
import HomePage from './pages/HomePage';
import CommunityPage from './pages/CommunityPage';
import { initializeTheme } from './lib/themes';
import { ProjectProvider } from './contexts/ProjectContext';
import { ToastProvider, ToastContainer } from './hooks/useToast';
import { ChatProvider } from './features/chat/context/ChatContext';
import GlobalChatModal from './features/chat/components/GlobalChatModal';
import apiClient from './lib/api-client';

type View = 'studio' | 'library' | 'settings' | 'knowledge' | 'agents' | 'home' | 'community';
type WorkflowStatus = 'draft' | 'saved' | 'running' | 'completed' | 'failed';

interface Agent {
  id: string;
  name: string;
  description: string;
  icon: string;
  model: string;
  fallback_models?: string[];
  temperature: number;
  max_tokens?: number;
  system_prompt: string;
  native_tools: string[];
  cli_tools?: string[];
  timeout_seconds: number;
  max_retries: number;
  enable_model_routing: boolean;
  enable_parallel_tools: boolean;
  enable_memory: boolean;
  enable_rag?: boolean;
  requires_human_approval?: boolean;
  tags?: string[];
}

interface NodeConfig {
  id: string;
  agentType: string;
  model: string;
  system_prompt: string;
  temperature: number;
  tools: string[];
  native_tools: string[];
}

interface SelectedNodeData {
  id: string;
  label: string;
  name?: string;
  agentType: string;
  model: string;
  system_prompt?: string;
  temperature?: number;
  max_tokens?: number;
  max_retries?: number;
  recursion_limit?: number;
  tools?: string[];
  native_tools?: string[];
  custom_tools?: string[];
  middleware?: any[];
  condition?: string;
  max_iterations?: number;
  exit_condition?: string;
  config: {
    model: string;
    fallback_models?: string[];
    temperature: number;
    max_tokens?: number;
    max_retries?: number;
    recursion_limit?: number;
    system_prompt: string;
    tools: string[];
    native_tools: string[];
    cli_tools?: string[];
    custom_tools?: string[];
    middleware?: any[];
    timeout_seconds: number;
    enable_model_routing: boolean;
    enable_parallel_tools: boolean;
    enable_memory: boolean;
    enable_rag?: boolean;
    requires_human_approval?: boolean;
    condition?: string;
    max_iterations?: number;
    exit_condition?: string;
    name?: string;
  };
}

function AppContent() {
  const navigate = useNavigate();
  const location = useLocation();
  const workflowCanvasRef = useRef<WorkflowCanvasRef>(null);
  const saveWorkflowTimeoutRef = useRef<number | null>(null);

  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [selectedRecipe, setSelectedRecipe] = useState<WorkflowRecipe | null>(null);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<number | null>(null);
  const [workflowName, setWorkflowName] = useState('Untitled Workflow');
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatus>('draft');
  const [executing, setExecuting] = useState(false);
  const [workflowTab, setWorkflowTab] = useState<'studio' | 'results'>('studio');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedNodeData, setSelectedNodeData] = useState<SelectedNodeData | null>(null);

  // Close node config panel when chat opens
  useEffect(() => {
    const handleChatOpened = () => {
      setSelectedNodeId(null);
      setSelectedNodeData(null);
    };

    window.addEventListener('chat:opened', handleChatOpened);
    return () => window.removeEventListener('chat:opened', handleChatOpened);
  }, []);
  const [nodeConfigs, setNodeConfigs] = useState<Record<string, NodeConfig>>({});
  const [tokenCostInfo, setTokenCostInfo] = useState<{
    totalTokens: number;
    promptTokens: number;
    completionTokens: number;
    costString: string;
  } | null>(null);

  // Sync workflowTab with current route
  useEffect(() => {
    if (location.pathname === '/results') {
      setWorkflowTab('results');
    } else if (location.pathname === '/studio') {
      setWorkflowTab('studio');
    }
  }, [location.pathname]);

  // Map routes to views
  const currentView: View = (() => {
    const path = location.pathname;
    if (path === '/' || path === '/home') return 'home';
    if (path === '/studio' || path === '/results') return 'studio';
    if (path === '/library') return 'library';
    if (path === '/agents' || path === '/deepagents') return 'agents';
    if (path === '/knowledge') return 'knowledge';
    if (path === '/community') return 'community';
    if (path === '/settings') return 'settings';
    return 'home';
  })();

  // Handle tab changes within studio view
  const handleTabChange = (tab: 'studio' | 'results') => {
    setWorkflowTab(tab);
    navigate(tab === 'results' ? '/results' : '/studio');
  };

  const handleViewChange = (view: View) => {
    // Check for unsaved workflow changes before navigating
    if (currentView === 'studio' && workflowCanvasRef.current) {
      const hasUnsaved = workflowCanvasRef.current.hasUnsavedChanges();
      if (hasUnsaved) {
        const confirmLeave = window.confirm(
          'You have unsaved workflow changes. Do you want to save before leaving?\n\n' +
          'Click OK to stay and save your changes.\n' +
          'Click Cancel to leave without saving.'
        );
        if (confirmLeave) {
          // User wants to stay and save
          return;
        }
        // User chose to leave without saving, proceed with navigation
      }
    }

    const routes: Record<View, string> = {
      home: '/home',
      studio: '/studio',
      library: '/library',
      agents: '/agents',
      knowledge: '/knowledge',
      community: '/community',
      settings: '/settings'
    };
    navigate(routes[view]);
  };

  // Initialize theme on app load
  useEffect(() => {
    initializeTheme();
  }, []);

  const handleSave = () => {
    setWorkflowStatus('saved');
  };

  const handleWorkflowNameChange = (name: string) => {
    setWorkflowName(name);

    // Save workflow name to backend if we have a selected workflow
    if (selectedWorkflowId) {
      // Debounce could be added here, but for now direct update is fine
      apiClient.updateWorkflow(selectedWorkflowId, { name })
        .catch((err: any) => console.error("Failed to save workflow name:", err));
    }
  };

  const handleExecutionStart = () => {
    setExecuting(true);
    setWorkflowStatus('running');
  };

  const handleNodeSelect = (nodeId: string | null, nodeData?: any) => {
    setSelectedNodeId(nodeId);
    if (nodeId && nodeData) {

      // Normalize data structure: flatten nested config if it exists
      // Some nodes (e.g., created by Claude Code agent) have config nested under nodeData.config
      // NodeConfigPanel expects a flat structure with model, systemPrompt, etc. at top level
      let normalizedData;
      if (nodeData.config && typeof nodeData.config === 'object') {
        // Flatten nested config while preserving top-level fields
        normalizedData = {
          id: nodeId,
          ...nodeData,
          ...nodeData.config,  // Spread config fields to top level
          // Preserve arrays from both levels
          tools: nodeData.config.tools || nodeData.tools || [],
          native_tools: nodeData.config.native_tools || nodeData.config.mcp_tools || nodeData.native_tools || [],
          custom_tools: nodeData.config.custom_tools || nodeData.custom_tools || [],
        };
      } else {
        // Already flat structure
        normalizedData = {
          id: nodeId,
          ...nodeData,
          tools: nodeData.tools || [],
          native_tools: nodeData.native_tools || [],
          custom_tools: nodeData.custom_tools || [],
        };
      }

      setSelectedNodeData(normalizedData);
    } else {
      setSelectedNodeData(null);
    }
  };

  const handleAgentAdded = () => {
    // Clear selected agent after it's been added to the canvas
    setSelectedAgent(null);
  };

  const handleNodeConfigSave = (nodeId: string, fullConfig: any) => {

    // Store config in state
    setNodeConfigs(prev => ({
      ...prev,
      [nodeId]: fullConfig
    }));

    // Update the actual node in ReactFlow
    if (workflowCanvasRef.current) {
      workflowCanvasRef.current.updateNodeConfig(nodeId, fullConfig);
    }

    // Update selectedNodeData to reflect changes in real-time (keeps panel in sync)
    if (selectedNodeId === nodeId && selectedNodeData) {
      setSelectedNodeData({
        ...selectedNodeData,
        ...fullConfig,
        config: fullConfig,  // Also store in nested config for compatibility
        label: fullConfig.label || fullConfig.name || selectedNodeData.label,
        name: fullConfig.name || selectedNodeData.name
      });
    }

    // Auto-save workflow to database after node config changes
    // Clear any pending save to debounce rapid changes
    if (saveWorkflowTimeoutRef.current !== null) {
      clearTimeout(saveWorkflowTimeoutRef.current);
    }

    // Schedule save for 800ms after last change
    saveWorkflowTimeoutRef.current = window.setTimeout(() => {
      if (workflowCanvasRef.current) {
        workflowCanvasRef.current.saveWorkflow(true);  // silent = true (no success popup)
      }
    }, 800);
  };

  const handleNodeDelete = (nodeId: string) => {
    // Delete node from ReactFlow
    if (workflowCanvasRef.current) {
      workflowCanvasRef.current.deleteNode(nodeId);
    }

    // Clear selection
    setSelectedNodeId(null);
    setSelectedNodeData(null);

    // Remove from node configs
    setNodeConfigs(prev => {
      const newConfigs = { ...prev };
      delete newConfigs[nodeId];
      return newConfigs;
    });

  };

  const handleWorkflowOpen = (workflowId: number) => {
    setSelectedWorkflowId(workflowId);
    navigate('/studio');
    // Load the workflow (it's already been created in the database)
    setWorkflowName(`Workflow ${workflowId}`);
    setWorkflowStatus('saved');
  };

  const selectedNodeConfig = selectedNodeId ? nodeConfigs[selectedNodeId] : null;

  return (
    <div className="relative flex h-screen w-full flex-col bg-background-light dark:bg-background-dark overflow-hidden">
      {/* Modern Header */}
      <ModernHeader
        currentView={currentView}
        onViewChange={handleViewChange}
      />

      {/* Main Content */}
      <main className="flex flex-row flex-1 overflow-x-auto overflow-y-hidden">
        {/* Left Panel - Agent Library (only in studio view AND studio tab) */}
        {currentView === 'studio' && workflowTab === 'studio' && (
          <ModernAgentLibrary
            onSelectAgent={setSelectedAgent}
            onSelectRecipe={setSelectedRecipe}
          />
        )}

        {/* Center Panel - Dynamic Content */}
        <div className="flex-1 min-w-0 flex flex-col overflow-hidden" style={{ minWidth: '650px' }}>
          {currentView === 'home' && <HomePage />}
          {currentView === 'studio' && (
            <WorkflowCanvas
              ref={workflowCanvasRef}
              selectedAgent={selectedAgent}
              selectedRecipe={selectedRecipe}
              onWorkflowSelect={setSelectedWorkflowId}
              onNodeSelect={handleNodeSelect}
              onNodeDelete={handleNodeDelete}
              onExecutionStart={handleExecutionStart}
              onAgentAdded={handleAgentAdded}
              onRecipeInserted={() => setSelectedRecipe(null)}
              workflowId={selectedWorkflowId}
              onTabChange={handleTabChange}
              initialTab={workflowTab}
              onTokenCostUpdate={setTokenCostInfo}
            />
          )}
          {currentView === 'library' && (
            <WorkflowLibraryView
              onWorkflowSelect={setSelectedWorkflowId}
              onWorkflowOpen={handleWorkflowOpen}
            />
          )}
          {currentView === 'agents' && <AgentLoadouts />}
          {currentView === 'knowledge' && <KnowledgeBaseView />}
          {currentView === 'community' && <CommunityPage />}
          {currentView === 'settings' && <SettingsView />}
        </div>

        {/* Right Panel - Node Config (only in studio view on studio tab with selected node) */}
        {currentView === 'studio' && workflowTab === 'studio' && selectedNodeId && selectedNodeData && (
          <NodeConfigPanel
            selectedNode={{
              id: selectedNodeId,
              name: selectedNodeData.label || selectedNodeData.name || selectedNodeData.config?.name || selectedNodeId,
              agentType: selectedNodeData.agentType,
              model: selectedNodeData.model || selectedNodeData.config?.model,
              system_prompt: selectedNodeData.system_prompt || selectedNodeData.config?.system_prompt || '',
              temperature: selectedNodeData.temperature ?? selectedNodeData.config?.temperature ?? 0.7,
              max_tokens: selectedNodeData.max_tokens || selectedNodeData.config?.max_tokens || 4000,
              max_retries: selectedNodeData.max_retries || selectedNodeData.config?.max_retries || 3,
              recursion_limit: selectedNodeData.recursion_limit || selectedNodeData.config?.recursion_limit || 300,
              tools: selectedNodeData.tools || selectedNodeData.config?.tools || [],
              native_tools: selectedNodeData.native_tools || selectedNodeData.config?.native_tools || [],
              custom_tools: selectedNodeData.custom_tools || selectedNodeData.config?.custom_tools || [],
              middleware: selectedNodeData.middleware || selectedNodeData.config?.middleware || [],
              condition: selectedNodeData.condition || selectedNodeData.config?.condition,
              max_iterations: selectedNodeData.max_iterations || selectedNodeData.config?.max_iterations,
              exit_condition: selectedNodeData.exit_condition || selectedNodeData.config?.exit_condition
            }}
            onClose={() => {
              setSelectedNodeId(null);
              setSelectedNodeData(null);
            }}
            onSave={handleNodeConfigSave}
            onDelete={handleNodeDelete}
            tokenCostInfo={tokenCostInfo || undefined}
          />
        )}
      </main>
    </div>
  );
}

function App() {
  return (
    <ToastProvider>
      <HashRouter>
        <ProjectProvider>
          <ChatProvider>
            <AppContent />
            <GlobalChatModal />
          </ChatProvider>
        </ProjectProvider>
      </HashRouter>
      <ToastContainer />
    </ToastProvider>
  );
}

export default App;
