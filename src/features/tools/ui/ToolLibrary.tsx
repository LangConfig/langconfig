/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect } from 'react';
import { Search, Plus, Edit, Play, Trash2, Copy, Download, Upload, AlertCircle, X } from 'lucide-react';
import apiClient from '../../../lib/api-client';
import CustomToolBuilder from './CustomToolBuilder';
import type { CustomTool } from '@/types/customTools';
import type { ChangeEvent } from 'react';

const ToolLibrary = () => {
  const [tools, setTools] = useState<CustomTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedTool, setSelectedTool] = useState<CustomTool | null>(null);
  const [showBuilder, setShowBuilder] = useState(false);
  const [editingTool, setEditingTool] = useState<string | null>(null);
  const [showTestModal, setShowTestModal] = useState(false);
  const [testingTool, setTestingTool] = useState<CustomTool | null>(null);
  const [testInput, setTestInput] = useState('{}');
  const [testResult, setTestResult] = useState<any>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  // Category configuration
  const categories = [
    { id: 'all', name: 'All Tools', color: '#6b7280' },
    { id: 'Communication', name: 'Communication', color: '#8b5cf6' },
    { id: 'Content Generation', name: 'Content Generation', color: '#ec4899' },
    { id: 'Data Processing', name: 'Data Processing', color: '#10b981' },
    { id: 'Integration', name: 'Integration', color: '#3b82f6' },
    { id: 'Utilities', name: 'Utilities', color: '#f59e0b' },
  ];

  // Tool type icons
  const getToolIcon = (toolType: string) => {
    const icons: { [key: string]: string } = {
      notification: '📧',
      api: '🔗',
      image_video: '🎨',
      database: '🗄️',
      data_transform: '🔄',
    };
    return icons[toolType] || '🔧';
  };

  // Load tools
  const loadTools = async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const response = await apiClient.listCustomTools({ signal });
      setTools(response.data || []);
    } catch (error) {
      // Ignore abort errors
      if (error instanceof Error && (error.name === 'AbortError' || error.name === 'CanceledError')) {
        return;
      }
      console.error('Failed to load tools:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const abortController = new AbortController();

    loadTools(abortController.signal);

    return () => {
      abortController.abort();
    };
  }, []);

  // Filter tools
  const filteredTools = tools.filter((tool) => {
    const matchesSearch =
      tool.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      tool.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      tool.tags.some((tag: string) => tag.toLowerCase().includes(searchQuery.toLowerCase()));

    const matchesCategory =
      selectedCategory === 'all' || tool.category === selectedCategory;

    return matchesSearch && matchesCategory;
  });

  // Handle tool deletion
  const handleDelete = async (toolId: string) => {
    try {
      await apiClient.deleteCustomTool(toolId);
      await loadTools();
      setDeleteConfirm(null);
    } catch (error) {
      console.error('Failed to delete tool:', error);
      alert('Failed to delete tool');
    }
  };

  // Handle tool duplication
  const handleDuplicate = async (tool: CustomTool) => {
    const newToolId = `${tool.tool_id}_copy_${Date.now()}`;
    try {
      await apiClient.duplicateCustomTool(tool.tool_id, newToolId);
      await loadTools();
    } catch (error) {
      console.error('Failed to duplicate tool:', error);
      alert('Failed to duplicate tool');
    }
  };

  // Handle tool export
  const handleExport = async (toolId: string, toolName: string) => {
    try {
      const response = await apiClient.exportCustomTool(toolId);
      const blob = new Blob([response.data], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${toolName}_export.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Failed to export tool:', error);
      alert('Failed to export tool');
    }
  };

  // Handle tool import
  const handleImport = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      await apiClient.importCustomTool(file);
      await loadTools();
      alert('Tool imported successfully!');
    } catch (error) {
      console.error('Failed to import tool:', error);
      alert('Failed to import tool');
    }
  };

  // Handle tool test
  const handleTest = async () => {
    if (!testingTool) return;

    setTestLoading(true);
    setTestResult(null);

    try {
      const inputData = JSON.parse(testInput);
      const response = await apiClient.testCustomTool(testingTool.tool_id, inputData);
      setTestResult(response.data);
    } catch (error: any) {
      setTestResult({
        success: false,
        error: error.message || 'Test failed',
      });
    } finally {
      setTestLoading(false);
    }
  };

  // Stats
  const stats = {
    total: tools.length,
    byCategory: categories
      .filter((cat) => cat.id !== 'all')
      .map((cat) => ({
        name: cat.name,
        count: tools.filter((t) => t.category === cat.id).length,
        color: cat.color,
      })),
    totalUsage: tools.reduce((sum, tool) => sum + tool.usage_count, 0),
    errorRate: tools.reduce((sum, tool) => sum + tool.error_count, 0),
  };

  return (
    <div className="h-screen flex flex-col" style={{ backgroundColor: 'var(--color-background-light)' }}>
      {/* Header */}
      <div className="border-b px-6 py-4" style={{ backgroundColor: 'var(--color-panel-dark)', borderBottomColor: 'var(--color-border-dark)' }}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
              <span className="material-symbols-outlined text-3xl">construction</span>
              Custom Tools
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--color-text-muted)' }}>
              Create and manage reusable tools for your workflows
            </p>
          </div>
          <div className="flex items-center gap-3">
            {/* Import */}
            <label className="cursor-pointer px-4 py-2 border rounded-lg flex items-center gap-2 text-sm transition-colors" style={{ borderColor: 'var(--color-border-dark)', color: 'var(--color-text-primary)' }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--color-background-dark)'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}>
              <Upload size={16} />
              Import
              <input
                type="file"
                accept=".json"
                onChange={handleImport}
                className="hidden"
              />
            </label>
            {/* Create New */}
            <button
              onClick={() => {
                setEditingTool(null);
                setShowBuilder(true);
              }}
              className="px-4 py-2 text-white rounded-lg flex items-center gap-2 transition-colors"
              style={{ backgroundColor: 'var(--color-primary)' }}
              onMouseEnter={(e) => e.currentTarget.style.opacity = '0.9'}
              onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
            >
              <Plus size={20} />
              Create Tool
            </button>
          </div>
        </div>

        {/* Stats Row */}
        <div className="mt-4 flex gap-4">
          <div className="rounded-lg px-4 py-2 border" style={{ backgroundColor: 'var(--color-background-dark)', borderColor: 'var(--color-border-dark)' }}>
            <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Total Tools</div>
            <div className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>{stats.total}</div>
          </div>
          <div className="rounded-lg px-4 py-2 border" style={{ backgroundColor: 'var(--color-background-dark)', borderColor: 'var(--color-border-dark)' }}>
            <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Total Usage</div>
            <div className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>{stats.totalUsage}</div>
          </div>
          {stats.byCategory.map((cat) => (
            <div
              key={cat.name}
              className="rounded-lg px-4 py-2 border"
              style={{ backgroundColor: 'var(--color-background-dark)', borderColor: 'var(--color-border-dark)' }}
            >
              <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{cat.name}</div>
              <div className="text-2xl font-bold" style={{ color: cat.color }}>
                {cat.count}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Search and Filter Bar */}
      <div className="border-b px-6 py-3" style={{ backgroundColor: 'var(--color-panel-dark)', borderBottomColor: 'var(--color-border-dark)' }}>
        <div className="flex gap-4 items-center">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2" size={18} style={{ color: 'var(--color-text-muted)' }} />
            <input
              type="text"
              placeholder="Search tools by name, description, or tags..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:border-transparent"
              style={{
                backgroundColor: 'var(--color-input-background)',
                borderColor: 'var(--color-border-dark)',
                color: 'var(--color-text-primary)',
                outlineColor: 'var(--color-primary)'
              }}
            />
          </div>

          {/* Category Filter */}
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="px-4 py-2 border rounded-lg focus:ring-2"
            style={{
              backgroundColor: 'var(--color-input-background)',
              borderColor: 'var(--color-border-dark)',
              color: 'var(--color-text-primary)',
              outlineColor: 'var(--color-primary)'
            }}
          >
            {categories.map((cat) => (
              <option key={cat.id} value={cat.id}>
                {cat.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Tools Grid */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div style={{ color: 'var(--color-text-muted)' }}>Loading tools...</div>
          </div>
        ) : filteredTools.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-center">
            <AlertCircle size={48} style={{ color: 'var(--color-text-muted)' }} className="mb-4" />
            <h3 className="text-xl font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
              {searchQuery || selectedCategory !== 'all' ? 'No tools found' : 'No tools yet'}
            </h3>
            <p className="mb-4" style={{ color: 'var(--color-text-muted)' }}>
              {searchQuery || selectedCategory !== 'all'
                ? 'Try adjusting your search or filter'
                : 'Create your first custom tool to get started'}
            </p>
            {!searchQuery && selectedCategory === 'all' && (
              <button
                onClick={() => {
                  setEditingTool(null);
                  setShowBuilder(true);
                }}
                className="px-6 py-3 text-white rounded-lg flex items-center gap-2 transition-opacity"
                style={{ backgroundColor: 'var(--color-primary)' }}
                onMouseEnter={(e) => e.currentTarget.style.opacity = '0.9'}
                onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
              >
                <Plus size={20} />
                Create Your First Tool
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredTools.map((tool) => (
              <div
                key={tool.id}
                className="rounded-lg border transition-colors p-5 relative"
                style={{
                  backgroundColor: 'var(--color-panel-dark)',
                  borderColor: 'var(--color-border-dark)',
                  borderLeft: `3px solid ${categories.find(c => c.id === tool.category)?.color || '#6b7280'}`
                }}
                onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
              >
                {/* Delete Confirmation Overlay */}
                {deleteConfirm === tool.tool_id && (
                  <div className="absolute inset-0 bg-red-500 bg-opacity-95 rounded-lg flex flex-col items-center justify-center z-10 p-4">
                    <AlertCircle size={32} className="text-white mb-2" />
                    <p className="text-white font-semibold mb-4 text-center">Delete this tool?</p>
                    <div className="flex gap-3">
                      <button
                        onClick={() => handleDelete(tool.tool_id)}
                        className="px-4 py-2 bg-white text-red-600 rounded-lg hover:bg-gray-100 font-medium"
                      >
                        Delete
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(null)}
                        className="px-4 py-2 bg-red-700 text-white rounded-lg hover:bg-red-800"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                {/* Tool Header */}
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-2xl">{getToolIcon(tool.tool_type)}</span>
                    <div>
                      <h3 className="font-semibold" style={{ color: 'var(--color-text-primary)' }}>{tool.name}</h3>
                      <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{tool.tool_id}</div>
                    </div>
                  </div>
                  {tool.is_template_based && (
                    <span className="px-2 py-1 bg-purple-100 dark:bg-purple-900 text-purple-700 dark:text-purple-300 text-xs rounded-full">
                      Template
                    </span>
                  )}
                </div>

                {/* Description */}
                <p className="text-sm mb-3 line-clamp-2" style={{ color: 'var(--color-text-muted)' }}>
                  {tool.description}
                </p>

                {/* Tags */}
                {tool.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-3">
                    {tool.tags.map((tag: string, idx: number) => (
                      <span
                        key={idx}
                        className="px-2 py-1 text-xs rounded"
                        style={{
                          backgroundColor: 'var(--color-background-dark)',
                          color: 'var(--color-text-muted)'
                        }}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}

                {/* Stats */}
                <div className="flex items-center gap-4 text-xs mb-4" style={{ color: 'var(--color-text-muted)' }}>
                  <span>Used {tool.usage_count}x</span>
                  {tool.error_count > 0 && (
                    <span className="text-red-500">{tool.error_count} errors</span>
                  )}
                  {tool.last_used_at && (
                    <span>Last: {new Date(tool.last_used_at).toLocaleDateString()}</span>
                  )}
                </div>

                {/* Actions */}
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      setEditingTool(tool.tool_id);
                      setShowBuilder(true);
                    }}
                    className="flex-1 px-3 py-2 rounded flex items-center justify-center gap-1 text-sm transition-opacity"
                    style={{ backgroundColor: 'var(--color-primary)', color: 'white' }}
                    title="Edit"
                    onMouseEnter={(e) => e.currentTarget.style.opacity = '0.8'}
                    onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
                  >
                    <Edit size={14} />
                    Edit
                  </button>
                  <button
                    onClick={() => {
                      setTestingTool(tool);
                      setShowTestModal(true);
                      setTestInput(JSON.stringify(tool.input_schema, null, 2));
                      setTestResult(null);
                    }}
                    className="flex-1 px-3 py-2 bg-green-50 dark:bg-green-900 text-green-600 dark:text-green-300 rounded hover:bg-green-100 dark:hover:bg-green-800 flex items-center justify-center gap-1 text-sm"
                    title="Test"
                  >
                    <Play size={14} />
                    Test
                  </button>
                  <button
                    onClick={() => handleDuplicate(tool)}
                    className="px-3 py-2 rounded transition-opacity"
                    style={{ backgroundColor: 'var(--color-background-dark)', color: 'var(--color-text-muted)' }}
                    title="Duplicate"
                    onMouseEnter={(e) => e.currentTarget.style.opacity = '0.7'}
                    onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
                  >
                    <Copy size={14} />
                  </button>
                  <button
                    onClick={() => handleExport(tool.tool_id, tool.name)}
                    className="px-3 py-2 rounded transition-opacity"
                    style={{ backgroundColor: 'var(--color-background-dark)', color: 'var(--color-text-muted)' }}
                    title="Export"
                    onMouseEnter={(e) => e.currentTarget.style.opacity = '0.7'}
                    onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
                  >
                    <Download size={14} />
                  </button>
                  <button
                    onClick={() => setDeleteConfirm(tool.tool_id)}
                    className="px-3 py-2 bg-red-50 dark:bg-red-900 text-red-600 dark:text-red-300 rounded hover:bg-red-100 dark:hover:bg-red-800"
                    title="Delete"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Tool Builder Modal */}
      {showBuilder && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="w-full h-full max-w-7xl rounded-lg shadow-2xl overflow-hidden" style={{ backgroundColor: 'var(--color-panel-dark)' }}>
            <CustomToolBuilder
              existingToolId={editingTool || undefined}
              onClose={() => {
                setShowBuilder(false);
                setEditingTool(null);
                loadTools();
              }}
            />
          </div>
        </div>
      )}

      {/* Test Modal */}
      {showTestModal && testingTool && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="rounded-lg shadow-2xl max-w-3xl w-full max-h-[80vh] overflow-hidden flex flex-col" style={{ backgroundColor: 'var(--color-panel-dark)' }}>
            {/* Header */}
            <div className="border-b px-6 py-4 flex items-center justify-between" style={{ borderBottomColor: 'var(--color-border-dark)' }}>
              <div>
                <h2 className="text-xl font-semibold flex items-center gap-2" style={{ color: 'var(--color-text-primary)' }}>
                  <Play size={20} />
                  Test Tool: {testingTool.name}
                </h2>
                <p className="text-sm mt-1" style={{ color: 'var(--color-text-muted)' }}>
                  Enter test input and run to see the output
                </p>
              </div>
              <button
                onClick={() => {
                  setShowTestModal(false);
                  setTestingTool(null);
                  setTestResult(null);
                }}
                style={{ color: 'var(--color-text-muted)' }}
                className="transition-opacity"
                onMouseEnter={(e) => e.currentTarget.style.opacity = '0.7'}
                onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
              >
                <X size={24} />
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto px-6 py-4">
              {/* Input */}
              <div className="mb-4">
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                  Test Input (JSON)
                </label>
                <textarea
                  value={testInput}
                  onChange={(e) => setTestInput(e.target.value)}
                  className="w-full h-32 px-3 py-2 border rounded-lg font-mono text-sm focus:ring-2"
                  style={{
                    backgroundColor: 'var(--color-input-background)',
                    borderColor: 'var(--color-border-dark)',
                    color: 'var(--color-text-primary)',
                    outlineColor: 'var(--color-primary)'
                  }}
                  placeholder='{"key": "value"}'
                />
              </div>

              {/* Run Button */}
              <button
                onClick={handleTest}
                disabled={testLoading}
                className="w-full px-4 py-3 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-opacity"
                style={{ backgroundColor: 'var(--color-primary)' }}
                onMouseEnter={(e) => !testLoading && (e.currentTarget.style.opacity = '0.9')}
                onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
              >
                {testLoading ? (
                  <>
                    <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent" />
                    Running Test...
                  </>
                ) : (
                  <>
                    <Play size={20} />
                    Run Test
                  </>
                )}
              </button>

              {/* Result */}
              {testResult && (
                <div className="mt-4">
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Result
                  </label>
                  <div
                    className={`p-4 rounded-lg border ${
                      testResult.success
                        ? 'bg-green-50 dark:bg-green-900 border-green-200 dark:border-green-700'
                        : 'bg-red-50 dark:bg-red-900 border-red-200 dark:border-red-700'
                    }`}
                  >
                    <div className="flex items-start gap-2 mb-2">
                      {testResult.success ? (
                        <span className="text-green-600 dark:text-green-300 font-semibold">✓ Success</span>
                      ) : (
                        <span className="text-red-600 dark:text-red-300 font-semibold">✗ Error</span>
                      )}
                      {testResult.execution_time_ms && (
                        <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                          ({testResult.execution_time_ms}ms)
                        </span>
                      )}
                    </div>
                    <pre className="text-sm p-3 rounded border overflow-x-auto" style={{
                      backgroundColor: 'var(--color-input-background)',
                      borderColor: 'var(--color-border-dark)',
                      color: 'var(--color-text-primary)'
                    }}>
                      {JSON.stringify(testResult.result || testResult.error, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ToolLibrary;
