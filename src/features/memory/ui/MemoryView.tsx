/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Memory View Component
 *
 * Comprehensive view of all memory systems in a workflow:
 * - Short-term: Conversation state & checkpoints (LangGraph Checkpointer)
 * - Long-term: Workflow-scoped persistent memory (LangGraph Store)
 * - Agent Settings: Memory configuration per agent
 * - Knowledge: RAG/vector store integration
 */

import React, { useState, useEffect } from 'react';
import { Database, Brain, FileText, Settings, Plus, Trash2, RefreshCw, Info, Link as LinkIcon } from 'lucide-react';
import apiClient from "../../../lib/api-client";

interface MemoryViewProps {
  workflowId: number;
  nodes: any[];
}

interface StoreItem {
  namespace: string[];
  key: string;
  value: any;
  created_at?: string;
  updated_at?: string;
}

export const MemoryView: React.FC<MemoryViewProps> = ({ workflowId, nodes }) => {
  const [activeSection, setActiveSection] = useState<'long-term' | 'agent-settings' | 'knowledge'>('long-term');
  const [longTermMemory, setLongTermMemory] = useState<StoreItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');

  useEffect(() => {
    if (activeSection === 'long-term') {
      loadLongTermMemory();
    }
  }, [activeSection, workflowId]);

  const loadLongTermMemory = async () => {
    setLoading(true);
    try {
      const response = await apiClient.getWorkflowMemory(workflowId);
      setLongTermMemory(response.data || []);
    } catch (err) {
      console.error('Error loading memory:', err);
    } finally {
      setLoading(false);
    }
  };

  const addMemoryItem = async () => {
    if (!newKey.trim()) return;

    let parsedValue: any;
    try {
      parsedValue = JSON.parse(newValue);
    } catch {
      parsedValue = newValue;
    }

    try {
      await apiClient.addWorkflowMemoryItem(workflowId, {
        namespace: ['workflow', String(workflowId)],
        key: newKey,
        value: parsedValue,
      });

      setNewKey('');
      setNewValue('');
      setShowAddForm(false);
      await loadLongTermMemory();
    } catch (err) {
      console.error('Error adding memory:', err);
    }
  };

  const deleteMemoryItem = async (key: string) => {
    if (!confirm(`Delete memory item "${key}"?`)) return;

    try {
      await apiClient.deleteWorkflowMemoryItem(workflowId, key);
      await loadLongTermMemory();
    } catch (err) {
      console.error('Error deleting memory:', err);
    }
  };

  const agentsWithMemory = nodes.filter(node =>
    node.data?.config?.enable_memory || node.data?.config?.guardrails?.long_term_memory
  );

  const agentsWithRAG = nodes.filter(node =>
    node.data?.config?.enable_rag
  );

  return (
    <div className="w-full h-full flex flex-col overflow-hidden" style={{ color: 'var(--color-text-primary)' }}>
      {/* Header */}
      <div className="p-6 border-b" style={{ borderColor: 'var(--color-border-dark)' }}>
        <div className="max-w-5xl mx-auto">
          <h2 className="text-2xl font-bold mb-2" style={{ fontFamily: 'var(--font-family-display)' }}>
            Workflow Memory
          </h2>
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            Manage how your workflow remembers and learns across executions
          </p>
        </div>
      </div>

      {/* Section Tabs */}
      <div className="border-b" style={{ borderColor: 'var(--color-border-dark)' }}>
        <div className="max-w-5xl mx-auto flex">
          <button
            onClick={() => setActiveSection('long-term')}
            className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${activeSection === 'long-term'
              ? 'border-primary text-primary'
              : 'border-transparent hover:text-primary'
              }`}
            style={activeSection !== 'long-term' ? { color: 'var(--color-text-muted)' } : {}}
          >
            <Database className="w-4 h-4 inline mr-2" />
            Long-Term Memory
          </button>
          <button
            onClick={() => setActiveSection('agent-settings')}
            className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${activeSection === 'agent-settings'
              ? 'border-primary text-primary'
              : 'border-transparent hover:text-primary'
              }`}
            style={activeSection !== 'agent-settings' ? { color: 'var(--color-text-muted)' } : {}}
          >
            <Settings className="w-4 h-4 inline mr-2" />
            Agent Settings
          </button>
          <button
            onClick={() => setActiveSection('knowledge')}
            className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${activeSection === 'knowledge'
              ? 'border-primary text-primary'
              : 'border-transparent hover:text-primary'
              }`}
            style={activeSection !== 'knowledge' ? { color: 'var(--color-text-muted)' } : {}}
          >
            <FileText className="w-4 h-4 inline mr-2" />
            Knowledge Base
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto p-6">
          {/* Long-Term Memory Section */}
          {activeSection === 'long-term' && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">Workflow-Scoped Memory</h3>
                <div className="flex items-center gap-2">
                  <button
                    onClick={loadLongTermMemory}
                    disabled={loading}
                    className="p-2 hover:bg-gray-100 dark:hover:bg-white/10 rounded-lg transition-colors"
                    title="Refresh"
                  >
                    <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} style={{ color: 'var(--color-text-muted)' }} />
                  </button>
                </div>
              </div>

              <p className="text-sm mb-4" style={{ color: 'var(--color-text-muted)' }}>
                Persistent memory that agents can access via <code className="px-1 py-0.5 bg-white dark:bg-panel-dark border border-gray-200 dark:border-border-dark rounded text-xs">runtime.store</code> API.
                Stored items persist across workflow executions.
              </p>

              {/* Add Memory Button */}
              {!showAddForm && (
                <button
                  onClick={() => setShowAddForm(true)}
                  className="w-full mb-4 p-4 border-2 border-dashed rounded-lg hover:border-primary transition-colors flex items-center justify-center gap-2"
                  style={{ borderColor: 'var(--color-border-dark)', color: 'var(--color-text-muted)' }}
                >
                  <Plus className="w-4 h-4" />
                  <span>Add Memory Item</span>
                </button>
              )}

              {/* Add Memory Form */}
              {showAddForm && (
                <div className="mb-4 p-4 border border-primary rounded-lg bg-white dark:bg-panel-dark">
                  <h4 className="font-semibold mb-3">Add Memory Item</h4>
                  <div className="space-y-3">
                    <div>
                      <label className="block text-sm font-medium mb-1">Key</label>
                      <input
                        type="text"
                        value={newKey}
                        onChange={(e) => setNewKey(e.target.value)}
                        placeholder="e.g., user_preferences, api_config"
                        className="w-full px-3 py-2 border border-gray-300 dark:border-border-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                        style={{
                          backgroundColor: 'var(--color-input-background)',
                          color: 'var(--color-text-primary)'
                        }}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-1">Value (JSON or text)</label>
                      <textarea
                        value={newValue}
                        onChange={(e) => setNewValue(e.target.value)}
                        placeholder='{"key": "value"} or plain text'
                        rows={4}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-border-dark rounded-lg font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                        style={{
                          backgroundColor: 'var(--color-input-background)',
                          color: 'var(--color-text-primary)'
                        }}
                      />
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={addMemoryItem}
                        className="px-4 py-2 bg-primary text-white rounded-lg hover:opacity-90 transition-all font-semibold"
                      >
                        Add
                      </button>
                      <button
                        onClick={() => {
                          setShowAddForm(false);
                          setNewKey('');
                          setNewValue('');
                        }}
                        className="px-4 py-2 bg-white dark:bg-background-dark border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors font-medium text-text-primary dark:text-text-primary"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Memory Items */}
              {longTermMemory.length === 0 && !loading && (
                <div className="py-8">
                  <div className="text-center mb-6" style={{ color: 'var(--color-text-muted)' }}>
                    <Database className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <p>No memory items yet</p>
                    <p className="text-sm mt-1">Add items to provide persistent context to your workflow</p>
                  </div>

                  {/* Memory System Explanation - shown when empty */}
                  <div className="max-w-2xl mx-auto p-4 rounded-lg bg-white dark:bg-panel-dark border border-gray-200 dark:border-border-dark">
                    <div className="flex items-start gap-3">
                      <Info className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                      <div className="text-sm text-text-primary dark:text-text-primary">
                        <p className="font-semibold mb-2">How Memory Works:</p>
                        <ul className="space-y-1 text-xs" style={{ color: 'var(--color-text-primary)' }}>
                          <li><strong>Short-term:</strong> Conversation state saved automatically (checkpoints) - enables pause/resume</li>
                          <li><strong>Long-term:</strong> Persistent workflow memory across sessions - agents can store/retrieve context</li>
                          <li><strong>Knowledge:</strong> Project RAG database - semantic search over documents</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {longTermMemory.map((item, index) => (
                <div
                  key={index}
                  className="mb-3 p-4 border rounded-lg hover:border-primary transition-colors"
                  style={{ borderColor: 'var(--color-border-dark)' }}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <div className="font-mono text-sm font-semibold text-primary mb-1">
                        {item.key}
                      </div>
                      {item.created_at && (
                        <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                          {new Date(item.created_at).toLocaleString()}
                        </div>
                      )}
                    </div>
                    <button
                      onClick={() => deleteMemoryItem(item.key)}
                      className="p-2 hover:bg-red-100 dark:hover:bg-red-900/30 rounded-lg transition-colors"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4 text-red-600 dark:text-red-400" />
                    </button>
                  </div>
                  <div className="mt-2 p-3 rounded-lg bg-white dark:bg-panel-dark border border-gray-200 dark:border-border-dark">
                    <pre className="text-xs overflow-x-auto whitespace-pre-wrap" style={{ color: 'var(--color-text-primary)' }}>
                      {JSON.stringify(item.value, null, 2)}
                    </pre>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Agent Settings Section */}
          {activeSection === 'agent-settings' && (
            <div>
              <h3 className="text-lg font-semibold mb-4">Agent Memory Configuration</h3>
              <p className="text-sm mb-6" style={{ color: 'var(--color-text-muted)' }}>
                View which agents in this workflow have memory features enabled. Configure memory settings in the Studio tab.
              </p>

              {nodes.length === 0 && (
                <div className="text-center py-12" style={{ color: 'var(--color-text-muted)' }}>
                  <Brain className="w-12 h-12 mx-auto mb-3 opacity-30" />
                  <p>No agents in workflow</p>
                </div>
              )}

              {nodes.map((node) => (
                <div
                  key={node.id}
                  className="mb-3 p-4 border rounded-lg"
                  style={{ borderColor: 'var(--color-border-dark)' }}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <h4 className="font-semibold">{node.data?.label || node.id}</h4>
                      <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                        {node.data?.config?.model || 'No model configured'}
                      </p>
                    </div>
                  </div>

                  <div className="space-y-2 text-sm">
                    <div className="flex items-center justify-between">
                      <span style={{ color: 'var(--color-text-muted)' }}>Project Memory (RAG Tools)</span>
                      <span className={node.data?.config?.enable_memory ? 'text-green-600 dark:text-green-400' : 'text-gray-400'}>
                        {node.data?.config?.enable_memory ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span style={{ color: 'var(--color-text-muted)' }}>Long-Term Memory (Store API)</span>
                      <span className={node.data?.config?.guardrails?.long_term_memory ? 'text-green-600 dark:text-green-400' : 'text-gray-400'}>
                        {node.data?.config?.guardrails?.long_term_memory ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span style={{ color: 'var(--color-text-muted)' }}>Codebase Search (RAG)</span>
                      <span className={node.data?.config?.enable_rag ? 'text-green-600 dark:text-green-400' : 'text-gray-400'}>
                        {node.data?.config?.enable_rag ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Knowledge Base Section */}
          {activeSection === 'knowledge' && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">Project Knowledge Base</h3>
                <a
                  href="#knowledge"
                  className="flex items-center gap-2 text-sm text-primary hover:underline"
                >
                  <LinkIcon className="w-4 h-4" />
                  Manage in Knowledge Tab
                </a>
              </div>

              <p className="text-sm mb-6" style={{ color: 'var(--color-text-muted)' }}>
                RAG (Retrieval-Augmented Generation) allows agents to search your project documents and codebase.
                The Knowledge page is the central hub for managing project-specific knowledge.
              </p>

              <div className="space-y-4">
                {/* RAG Summary */}
                <div className="p-4 border rounded-lg" style={{ borderColor: 'var(--color-border-dark)' }}>
                  <h4 className="font-semibold mb-3">Agents with Codebase Search</h4>
                  {agentsWithRAG.length === 0 ? (
                    <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                      No agents have RAG enabled. Enable in agent configuration.
                    </p>
                  ) : (
                    <ul className="space-y-2">
                      {agentsWithRAG.map(node => (
                        <li key={node.id} className="text-sm">
                          • {node.data?.label || node.id}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {/* Memory Tools Summary */}
                <div className="p-4 border rounded-lg" style={{ borderColor: 'var(--color-border-dark)' }}>
                  <h4 className="font-semibold mb-3">Agents with Memory Tools</h4>
                  {agentsWithMemory.length === 0 ? (
                    <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                      No agents have memory tools enabled. Enable in agent configuration.
                    </p>
                  ) : (
                    <ul className="space-y-2">
                      {agentsWithMemory.map(node => (
                        <li key={node.id} className="text-sm">
                          • {node.data?.label || node.id}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {/* Knowledge Management Link */}
                <div className="p-4 rounded-lg bg-white dark:bg-panel-dark border border-gray-200 dark:border-border-dark">
                  <div className="flex items-start gap-3">
                    <Info className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                    <div className="text-sm text-text-primary dark:text-text-primary">
                      <p className="font-semibold mb-1">Knowledge Base is King</p>
                      <p className="text-xs" style={{ color: 'var(--color-text-primary)' }}>
                        Use the Knowledge tab to upload documents, manage embeddings, and configure RAG settings.
                        This Memory view provides quick access to memory-related settings within your workflow.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
