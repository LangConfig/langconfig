/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState } from 'react';

interface Project {
  id: number;
  name: string;
  description?: string;
  status: string;
  indexed_nodes_count?: number;
}

interface EmptyStateContentProps {
  activeProject: Project | null;
  onCreateWorkflow: () => void;
  onImportWorkflow?: () => void;
  onViewSettings?: () => void;
}

export default function EmptyStateContent({
  activeProject,
  onCreateWorkflow,
  onImportWorkflow,
  onViewSettings
}: EmptyStateContentProps) {
  const [expandedSection, setExpandedSection] = useState<string | null>('getting-started');

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  return (
    <div className="h-full flex items-center justify-center p-6 overflow-y-auto">
      <div className="space-y-6 max-w-5xl w-full">
      {/* Welcome Header */}
      <div className="text-center py-8">
        <div className="w-20 h-20 mx-auto mb-4 rounded-2xl bg-primary/10 flex items-center justify-center">
          <span className="material-symbols-outlined text-4xl text-primary">account_tree</span>
        </div>
        <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--color-text-primary)' }}>
          Welcome to Workflow Library
        </h1>
        <p className="text-base" style={{ color: 'var(--color-text-muted)' }}>
          Build powerful multi-agent workflows with LangGraph
        </p>
      </div>

      {/* Project Info Card (if project selected) */}
      {activeProject && (
        <div className="p-4 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
              <span className="material-symbols-outlined text-2xl text-primary">folder</span>
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  {activeProject.name}
                </h3>
                {activeProject.status === 'active' && (
                  <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 dark:bg-green-500/20 text-green-700 dark:text-green-400">
                    Active
                  </span>
                )}
              </div>
              {activeProject.description && (
                <p className="text-sm mb-2" style={{ color: 'var(--color-text-muted)' }}>
                  {activeProject.description}
                </p>
              )}
              <div className="flex items-center gap-4 text-sm">
                <div className="flex items-center gap-1">
                  <span className="material-symbols-outlined text-base" style={{ color: 'var(--color-text-muted)' }}>
                    description
                  </span>
                  <span style={{ color: 'var(--color-text-muted)' }}>
                    {activeProject.indexed_nodes_count || 0} indexed docs
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Quick Actions Panel */}
      <div className="p-6 rounded-lg border border-gray-200 dark:border-border-dark bg-gradient-to-br from-primary/5 to-transparent">
        <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--color-text-primary)' }}>
          Quick Actions
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <button
            onClick={onCreateWorkflow}
            className="flex items-center gap-3 p-4 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark hover:border-primary transition-colors group"
          >
            <div className="w-10 h-10 rounded-lg bg-primary/10 group-hover:bg-primary/20 flex items-center justify-center transition-colors">
              <span className="material-symbols-outlined text-xl text-primary">add_circle</span>
            </div>
            <div className="text-left">
              <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                Create Workflow
              </p>
              <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                Start building a new workflow
              </p>
            </div>
          </button>

          {onImportWorkflow && (
            <button
              onClick={onImportWorkflow}
              className="flex items-center gap-3 p-4 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark hover:border-primary transition-colors group"
            >
              <div className="w-10 h-10 rounded-lg bg-blue-500/10 group-hover:bg-blue-500/20 flex items-center justify-center transition-colors">
                <span className="material-symbols-outlined text-xl text-blue-600 dark:text-blue-400">upload_file</span>
              </div>
              <div className="text-left">
                <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  Import Workflow
                </p>
                <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  Load from file or template
                </p>
              </div>
            </button>
          )}

          {onViewSettings && (
            <button
              onClick={onViewSettings}
              className="flex items-center gap-3 p-4 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark hover:border-primary transition-colors group"
            >
              <div className="w-10 h-10 rounded-lg bg-purple-500/10 group-hover:bg-purple-500/20 flex items-center justify-center transition-colors">
                <span className="material-symbols-outlined text-xl text-purple-600 dark:text-purple-400">settings</span>
              </div>
              <div className="text-left">
                <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  Project Settings
                </p>
                <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  Configure project options
                </p>
              </div>
            </button>
          )}
        </div>
      </div>

      {/* Tutorial Sections */}
      <div>
        <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--color-text-primary)' }}>
          Getting Started Guide
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">

        {/* Section 1: Understanding Workflows */}
        <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
          <button
            onClick={() => toggleSection('understanding')}
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
          >
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-primary">lightbulb</span>
              <span className="font-medium" style={{ color: 'var(--color-text-primary)' }}>
                Understanding Workflows
              </span>
            </div>
            <span
              className={`material-symbols-outlined transition-transform ${
                expandedSection === 'understanding' ? 'rotate-180' : ''
              }`}
              style={{ color: 'var(--color-text-muted)' }}
            >
              expand_more
            </span>
          </button>
          {expandedSection === 'understanding' && (
            <div className="px-4 pb-4 space-y-3 text-sm" style={{ color: 'var(--color-text-muted)' }}>
              <p>
                Workflows are visual representations of multi-agent systems built with LangGraph. Each workflow consists of:
              </p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li><strong>Nodes (Agents):</strong> Individual AI agents with specific tasks and capabilities</li>
                <li><strong>Edges (Connections):</strong> Define how information flows between agents</li>
                <li><strong>Configuration:</strong> Model settings, temperature, tools, and memory</li>
              </ul>
              <p>
                Every workflow you build here is a real LangGraph state graph that can be exported as production-ready Python code.
              </p>
            </div>
          )}
        </div>

        {/* Section 2: Creating Your First Agent */}
        <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
          <button
            onClick={() => toggleSection('creating')}
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
          >
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-primary">smart_toy</span>
              <span className="font-medium" style={{ color: 'var(--color-text-primary)' }}>
                Creating Your First Agent
              </span>
            </div>
            <span
              className={`material-symbols-outlined transition-transform ${
                expandedSection === 'creating' ? 'rotate-180' : ''
              }`}
              style={{ color: 'var(--color-text-muted)' }}
            >
              expand_more
            </span>
          </button>
          {expandedSection === 'creating' && (
            <div className="px-4 pb-4 space-y-3 text-sm" style={{ color: 'var(--color-text-muted)' }}>
              <ol className="list-decimal list-inside space-y-2 ml-2">
                <li>Click "Create Workflow" to open the workflow studio</li>
                <li>Drag an agent node from the left panel onto the canvas</li>
                <li>Configure the agent: Choose a model (GPT-4, Claude, etc.), set temperature, and write a system prompt</li>
                <li>Add tools to give your agent capabilities (web search, code execution, RAG, etc.)</li>
                <li>Save your workflow and test it with sample inputs</li>
              </ol>
            </div>
          )}
        </div>

        {/* Section 3: Connecting Nodes */}
        <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
          <button
            onClick={() => toggleSection('connecting')}
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
          >
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-primary">hub</span>
              <span className="font-medium" style={{ color: 'var(--color-text-primary)' }}>
                Connecting Nodes
              </span>
            </div>
            <span
              className={`material-symbols-outlined transition-transform ${
                expandedSection === 'connecting' ? 'rotate-180' : ''
              }`}
              style={{ color: 'var(--color-text-muted)' }}
            >
              expand_more
            </span>
          </button>
          {expandedSection === 'connecting' && (
            <div className="px-4 pb-4 space-y-3 text-sm" style={{ color: 'var(--color-text-muted)' }}>
              <p>
                Connect agents to create complex workflows:
              </p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>Click and drag from one agent's output handle to another's input handle</li>
                <li>Use <strong>conditional edges</strong> to route based on agent outputs</li>
                <li>Create <strong>parallel execution</strong> by connecting multiple agents to the same input</li>
                <li>Add <strong>human-in-the-loop</strong> nodes for review and approval steps</li>
              </ul>
            </div>
          )}
        </div>

        {/* Section 4: Running Workflows */}
        <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
          <button
            onClick={() => toggleSection('running')}
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
          >
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-primary">play_circle</span>
              <span className="font-medium" style={{ color: 'var(--color-text-primary)' }}>
                Running Workflows
              </span>
            </div>
            <span
              className={`material-symbols-outlined transition-transform ${
                expandedSection === 'running' ? 'rotate-180' : ''
              }`}
              style={{ color: 'var(--color-text-muted)' }}
            >
              expand_more
            </span>
          </button>
          {expandedSection === 'running' && (
            <div className="px-4 pb-4 space-y-3 text-sm" style={{ color: 'var(--color-text-muted)' }}>
              <p>
                Execute your workflows and view results:
              </p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>Click the "Run" button in the workflow studio</li>
                <li>Provide input data in the prompt panel</li>
                <li>Watch real-time execution with streaming outputs</li>
                <li>View detailed results including token usage, costs, and execution time</li>
                <li>Export results or LangGraph code for production use</li>
              </ul>
            </div>
          )}
        </div>
        </div>
      </div>

      {/* Tips & Best Practices */}
      <div className="p-4 rounded-lg border border-blue-200 dark:border-blue-500/30 bg-blue-50 dark:bg-blue-500/10">
        <div className="flex gap-3">
          <span className="material-symbols-outlined text-blue-600 dark:text-blue-400 flex-shrink-0">tips_and_updates</span>
          <div>
            <h4 className="text-sm font-semibold mb-2 text-blue-800 dark:text-blue-400">
              Tips & Best Practices
            </h4>
            <ul className="text-xs space-y-1 text-blue-700 dark:text-blue-400/80">
              <li>• Start simple: Build basic workflows before adding complexity</li>
              <li>• Use descriptive names: Name your agents and workflows clearly</li>
              <li>• Test frequently: Run your workflows early and often during development</li>
              <li>• Version control: Save versions before making major changes</li>
              <li>• Monitor costs: Check token usage to optimize performance and expenses</li>
            </ul>
          </div>
        </div>
      </div>
      </div>
    </div>
  );
}
