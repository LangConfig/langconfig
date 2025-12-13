/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo } from 'react';
import { X } from 'lucide-react';

interface DebugNodeInfo {
  node_id: string;
  type: string;
  model?: string;
  native_tools: string[];
  custom_tools: string[];
  has_image_generation?: boolean;
}

interface CustomToolInfo {
  tool_id: string;
  name: string;
}

interface DebugData {
  workflow_name: string;
  nodes: DebugNodeInfo[];
  available_custom_tools: CustomToolInfo[];
  raw_configuration: any;
}

interface DebugWorkflowDialogProps {
  isOpen: boolean;
  onClose: () => void;
  debugData: DebugData | null;
  onCopyJson: () => void;
}

/**
 * Modal for displaying workflow debug information
 */
const DebugWorkflowDialog = memo(function DebugWorkflowDialog({
  isOpen,
  onClose,
  debugData,
  onCopyJson,
}: DebugWorkflowDialogProps) {
  if (!isOpen || !debugData) return null;

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="rounded-lg shadow-xl p-6 max-w-4xl w-full mx-4 max-h-[80vh] overflow-y-auto"
        style={{
          backgroundColor: 'var(--color-panel-dark)',
          border: '1px solid var(--color-border-dark)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            Workflow Debug Info: {debugData.workflow_name}
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-gray-700"
          >
            <X size={20} style={{ color: 'var(--color-text-muted)' }} />
          </button>
        </div>

        {/* Node Analysis */}
        <div className="mb-6">
          <h3 className="text-lg font-semibold mb-3" style={{ color: 'var(--color-primary)' }}>
            Node Tool Assignments
          </h3>
          {debugData.nodes.map((node) => (
            <div
              key={node.node_id}
              className="mb-3 p-3 rounded border"
              style={{
                backgroundColor: 'var(--color-background-dark)',
                borderColor: node.has_image_generation ? '#f59e0b' : 'var(--color-border-dark)',
                borderWidth: node.has_image_generation ? '2px' : '1px'
              }}
            >
              <div className="font-semibold mb-1" style={{ color: 'var(--color-text-primary)' }}>
                {node.node_id} ({node.type})
              </div>
              <div className="text-sm mb-1" style={{ color: 'var(--color-text-muted)' }}>
                Model: {node.model || 'Not set'}
              </div>
              <div className="text-sm mb-1">
                <span style={{ color: 'var(--color-text-muted)' }}>Native Tools: </span>
                <span style={{ color: 'var(--color-text-primary)' }}>
                  {node.native_tools && node.native_tools.length > 0 ? node.native_tools.join(', ') : 'None'}
                </span>
              </div>
              <div className="text-sm">
                <span style={{ color: 'var(--color-text-muted)' }}>Custom Tools: </span>
                <span style={{ color: node.custom_tools.length > 0 ? '#f59e0b' : 'var(--color-text-primary)', fontWeight: node.custom_tools.length > 0 ? 'bold' : 'normal' }}>
                  {node.custom_tools.length > 0 ? node.custom_tools.join(', ') : 'None'}
                </span>
                {node.has_image_generation && (
                  <span className="ml-2 text-xs px-2 py-1 rounded" style={{ backgroundColor: '#f59e0b', color: 'white' }}>
                    ✓ image_generation
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Available Custom Tools */}
        <div className="mb-6">
          <h3 className="text-lg font-semibold mb-3" style={{ color: 'var(--color-primary)' }}>
            Available Custom Tools
          </h3>
          <div className="grid grid-cols-2 gap-2">
            {debugData.available_custom_tools.map((tool) => (
              <div
                key={tool.tool_id}
                className="p-2 rounded border"
                style={{
                  backgroundColor: 'var(--color-background-dark)',
                  borderColor: 'var(--color-border-dark)'
                }}
              >
                <div className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  {tool.name}
                </div>
                <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  ID: {tool.tool_id}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Raw JSON */}
        <div>
          <h3 className="text-lg font-semibold mb-3" style={{ color: 'var(--color-primary)' }}>
            Raw Configuration JSON
          </h3>
          <pre
            className="text-xs p-3 rounded overflow-x-auto"
            style={{
              backgroundColor: 'var(--color-background-dark)',
              color: 'var(--color-text-primary)',
              maxHeight: '300px'
            }}
          >
            {JSON.stringify(debugData.raw_configuration, null, 2)}
          </pre>
        </div>

        <div className="mt-4 flex justify-end">
          <button
            onClick={onCopyJson}
            className="px-4 py-2 rounded-lg transition-colors"
            style={{
              backgroundColor: 'var(--color-primary)',
              color: 'white'
            }}
          >
            Copy JSON
          </button>
        </div>
      </div>
    </div>
  );
});

export default DebugWorkflowDialog;
