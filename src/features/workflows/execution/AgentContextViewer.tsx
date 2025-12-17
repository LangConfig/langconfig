/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * AgentContextViewer Component
 *
 * Shows what context an agent had access to during execution.
 * Helps debug issues like missing images, wrong system prompts, etc.
 */

import React, { useState } from 'react';
import { ChevronDown, ChevronRight, FileText, Image, Wrench, Settings, MessageSquare, Copy, Check } from 'lucide-react';

interface AgentContext {
  agent_label: string;
  node_id: string;
  timestamp: string;
  system_prompt: {
    preview: string;
    length: number;
  };
  tools: string[];
  attachments: Array<{
    name: string;
    mimeType: string;
    hasData: boolean;
    dataSize?: number;
  }>;
  messages: Array<{
    type: string;
    content: any;
  }>;
  model_config: {
    model: string;
    temperature: number;
    max_tokens?: number;
    enable_memory?: boolean;
    enable_rag?: boolean;
  };
  metadata?: Record<string, any>;
}

interface AgentContextViewerProps {
  context: AgentContext;
  isExpanded?: boolean;
}

export function AgentContextViewer({ context, isExpanded = false }: AgentContextViewerProps) {
  const [expanded, setExpanded] = useState(isExpanded);
  const [copiedSection, setCopiedSection] = useState<string | null>(null);

  const handleCopy = async (text: string, section: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedSection(section);
      setTimeout(() => setCopiedSection(null), 2000);
    } catch (e) {
      console.error('Failed to copy:', e);
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="border border-purple-300/30 dark:border-purple-700/30 rounded-lg bg-purple-50/50 dark:bg-purple-900/20 mt-2 mb-2">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium text-purple-700 dark:text-purple-300 hover:bg-purple-100/50 dark:hover:bg-purple-800/30 rounded-t-lg transition-colors"
      >
        {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        <Settings className="w-4 h-4" />
        <span>Agent Context</span>
        <span className="text-xs text-purple-500 dark:text-purple-400 ml-auto">
          {context.tools.length} tools • {context.attachments.length} attachments
        </span>
      </button>

      {/* Expandable Content */}
      {expanded && (
        <div className="px-3 pb-3 space-y-3">
          {/* Model Config */}
          <div className="bg-white/50 dark:bg-gray-800/50 rounded p-2">
            <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1 flex items-center gap-1">
              <Settings className="w-3 h-3" /> Model
            </div>
            <div className="text-sm text-gray-800 dark:text-gray-200 flex flex-wrap gap-2">
              <span className="bg-blue-100 dark:bg-blue-900/40 px-2 py-0.5 rounded text-xs">{context.model_config.model}</span>
              <span className="bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded text-xs">temp: {context.model_config.temperature}</span>
              {context.model_config.enable_memory && (
                <span className="bg-green-100 dark:bg-green-900/40 px-2 py-0.5 rounded text-xs">Memory</span>
              )}
              {context.model_config.enable_rag && (
                <span className="bg-green-100 dark:bg-green-900/40 px-2 py-0.5 rounded text-xs">RAG</span>
              )}
            </div>
          </div>

          {/* System Prompt */}
          <div className="bg-white/50 dark:bg-gray-800/50 rounded p-2">
            <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1 flex items-center gap-1 justify-between">
              <span className="flex items-center gap-1">
                <FileText className="w-3 h-3" /> System Prompt ({context.system_prompt.length} chars)
              </span>
              <button
                onClick={() => handleCopy(context.system_prompt.preview, 'prompt')}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                {copiedSection === 'prompt' ? <Check className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
              </button>
            </div>
            <pre className="text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-mono max-h-32 overflow-y-auto bg-gray-50 dark:bg-gray-900/50 p-2 rounded">
              {context.system_prompt.preview}
            </pre>
          </div>

          {/* Tools */}
          {context.tools.length > 0 && (
            <div className="bg-white/50 dark:bg-gray-800/50 rounded p-2">
              <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1 flex items-center gap-1">
                <Wrench className="w-3 h-3" /> Tools ({context.tools.length})
              </div>
              <div className="flex flex-wrap gap-1">
                {context.tools.map((tool, i) => (
                  <span key={i} className="bg-orange-100 dark:bg-orange-900/40 text-orange-800 dark:text-orange-200 px-2 py-0.5 rounded text-xs">
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Attachments */}
          {context.attachments.length > 0 && (
            <div className="bg-white/50 dark:bg-gray-800/50 rounded p-2">
              <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1 flex items-center gap-1">
                <Image className="w-3 h-3" /> Attachments ({context.attachments.length})
              </div>
              <div className="space-y-1">
                {context.attachments.map((att, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs bg-gray-50 dark:bg-gray-900/50 px-2 py-1 rounded">
                    <span className={att.hasData ? 'text-green-600 dark:text-green-400' : 'text-red-500'}>
                      {att.hasData ? '✓' : '✗'}
                    </span>
                    <span className="text-gray-700 dark:text-gray-300">{att.name}</span>
                    <span className="text-gray-500">{att.mimeType}</span>
                    {att.dataSize && <span className="text-gray-400">{formatBytes(att.dataSize)}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Messages Preview */}
          {context.messages.length > 0 && (
            <div className="bg-white/50 dark:bg-gray-800/50 rounded p-2">
              <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1 flex items-center gap-1">
                <MessageSquare className="w-3 h-3" /> Input Messages ({context.messages.length})
              </div>
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {context.messages.map((msg, i) => (
                  <div key={i} className="text-xs bg-gray-50 dark:bg-gray-900/50 px-2 py-1 rounded">
                    <span className="font-medium text-gray-600 dark:text-gray-400">{msg.type}: </span>
                    <span className="text-gray-700 dark:text-gray-300">
                      {typeof msg.content === 'string'
                        ? msg.content.substring(0, 100) + (msg.content.length > 100 ? '...' : '')
                        : typeof msg.content === 'object' && msg.content?.preview
                          ? msg.content.preview.substring(0, 100) + '...'
                          : JSON.stringify(msg.content).substring(0, 100)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default AgentContextViewer;
