/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo } from 'react';
import { Trash2, Copy, Brain, Database, Settings, FileText as FileIcon } from 'lucide-react';

interface NodeData {
  label: string;
  executionStatus?: {
    tokenCost?: {
      costString: string;
    };
  };
  [key: string]: any;
}

interface NodeContextMenuProps {
  x: number;
  y: number;
  nodeId: string;
  nodeData: NodeData;
  onClose: () => void;
  onChatWithAgent: (nodeId: string, nodeData: NodeData) => void;
  onSaveToLibrary: (nodeId: string, nodeData: NodeData) => void;
  onCopyLangChainCode: (nodeId: string, nodeData: NodeData) => void;
  onDuplicateNode: (nodeId: string, nodeData: NodeData) => void;
  onConfigureNode: (nodeId: string) => void;
  onDeleteNode: (nodeId: string) => void;
}

/**
 * Context menu that appears when right-clicking a node in the workflow canvas
 */
const NodeContextMenu = memo(function NodeContextMenu({
  x,
  y,
  nodeId,
  nodeData,
  onClose,
  onChatWithAgent,
  onSaveToLibrary,
  onCopyLangChainCode,
  onDuplicateNode,
  onConfigureNode,
  onDeleteNode,
}: NodeContextMenuProps) {
  const menuButtonStyle = {
    color: 'var(--color-text-primary)',
    backgroundColor: '#ffffff',
  };

  const handleMouseEnter = (e: React.MouseEvent<HTMLButtonElement>, isDelete = false) => {
    e.currentTarget.style.backgroundColor = isDelete ? '#dc2626' : 'var(--color-primary)';
    e.currentTarget.style.color = '#ffffff';
    const icon = e.currentTarget.querySelector('svg');
    if (icon) (icon as unknown as HTMLElement).style.color = '#ffffff';
  };

  const handleMouseLeave = (e: React.MouseEvent<HTMLButtonElement>, isDelete = false) => {
    e.currentTarget.style.backgroundColor = '#ffffff';
    e.currentTarget.style.color = isDelete ? '#dc2626' : 'var(--color-text-primary)';
    const icon = e.currentTarget.querySelector('svg');
    if (icon && !isDelete) (icon as unknown as HTMLElement).style.color = 'var(--color-primary)';
  };

  return (
    <>
      {/* Backdrop to catch clicks */}
      <div
        className="fixed inset-0 z-[9998]"
        onClick={onClose}
      />
      <div
        className="fixed z-[9999] border rounded-lg shadow-2xl py-1 min-w-[200px]"
        style={{
          left: `${x}px`,
          top: `${y}px`,
          backgroundColor: '#ffffff',
          borderColor: 'var(--color-border-dark)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Chat with Agent */}
        <button
          onClick={() => onChatWithAgent(nodeId, nodeData)}
          className="w-full text-left px-4 py-2.5 text-sm transition-all flex items-center gap-3 rounded-t-lg"
          style={menuButtonStyle}
          onMouseEnter={(e) => handleMouseEnter(e)}
          onMouseLeave={(e) => handleMouseLeave(e)}
        >
          <Brain className="w-4 h-4 transition-colors" style={{ color: 'var(--color-primary)' }} />
          <div>
            <div className="font-medium">Chat with Agent</div>
            <div className="text-xs opacity-60">Open chat interface for this agent</div>
          </div>
        </button>

        {/* Divider */}
        <div className="h-px my-1" style={{ backgroundColor: 'var(--color-border-dark)' }} />

        {/* Save to Agent Library */}
        <button
          onClick={() => onSaveToLibrary(nodeId, nodeData)}
          className="w-full text-left px-4 py-2.5 text-sm transition-all flex items-center gap-3"
          style={menuButtonStyle}
          onMouseEnter={(e) => handleMouseEnter(e)}
          onMouseLeave={(e) => handleMouseLeave(e)}
        >
          <Database className="w-4 h-4 transition-colors" style={{ color: 'var(--color-primary)' }} />
          <div>
            <div className="font-medium">Save to Library</div>
            <div className="text-xs opacity-60">Reuse this agent in other workflows</div>
          </div>
        </button>

        {/* Divider */}
        <div className="h-px my-1" style={{ backgroundColor: 'var(--color-border-dark)' }} />

        {/* Copy LangChain Code */}
        <button
          onClick={() => onCopyLangChainCode(nodeId, nodeData)}
          className="w-full text-left px-4 py-2 text-sm transition-all flex items-center gap-2"
          style={menuButtonStyle}
          onMouseEnter={(e) => handleMouseEnter(e)}
          onMouseLeave={(e) => handleMouseLeave(e)}
        >
          <FileIcon className="w-4 h-4" />
          Copy LangChain Code
        </button>

        {/* Duplicate Node */}
        <button
          onClick={() => onDuplicateNode(nodeId, nodeData)}
          className="w-full text-left px-4 py-2 text-sm transition-all flex items-center gap-2"
          style={menuButtonStyle}
          onMouseEnter={(e) => handleMouseEnter(e)}
          onMouseLeave={(e) => handleMouseLeave(e)}
        >
          <Copy className="w-4 h-4" />
          Duplicate Node
        </button>

        {/* Configure Node */}
        <button
          onClick={() => onConfigureNode(nodeId)}
          className="w-full text-left px-4 py-2 text-sm transition-all flex items-center gap-2"
          style={menuButtonStyle}
          onMouseEnter={(e) => handleMouseEnter(e)}
          onMouseLeave={(e) => handleMouseLeave(e)}
        >
          <Settings className="w-4 h-4" />
          Configure
        </button>

        {/* View Metrics - only show if token cost exists */}
        {nodeData.executionStatus?.tokenCost && (
          <button
            onClick={() => onConfigureNode(nodeId)}
            className="w-full text-left px-4 py-2 text-sm transition-all flex items-center gap-2"
            style={menuButtonStyle}
            onMouseEnter={(e) => handleMouseEnter(e)}
            onMouseLeave={(e) => handleMouseLeave(e)}
          >
            <Brain className="w-4 h-4" />
            <div className="flex-1 flex items-center justify-between">
              <span>View Metrics</span>
              <span className="text-xs font-mono">
                {nodeData.executionStatus.tokenCost.costString}
              </span>
            </div>
          </button>
        )}

        {/* Divider */}
        <div className="h-px my-1" style={{ backgroundColor: 'var(--color-border-dark)' }} />

        {/* Delete Node */}
        <button
          onClick={() => onDeleteNode(nodeId)}
          className="w-full text-left px-4 py-2 text-sm transition-all flex items-center gap-2"
          style={{ color: '#dc2626', backgroundColor: '#ffffff' }}
          onMouseEnter={(e) => handleMouseEnter(e, true)}
          onMouseLeave={(e) => handleMouseLeave(e, true)}
        >
          <Trash2 className="w-4 h-4" />
          Delete Node
        </button>
      </div>
    </>
  );
});

export default NodeContextMenu;
