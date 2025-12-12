/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo } from 'react';
import { Node } from 'reactflow';
import ThinkingToast from '../../../../../components/ui/ThinkingToast';
import { NodeExecutionStatus } from '../../../../../hooks/useNodeExecutionStatus';

interface ThinkingToastRendererProps {
  nodes: Node[];
  nodeExecutionStatuses: Record<string, NodeExecutionStatus>;
  reactFlowInstance: any;
  showThinkingStream: boolean;
  currentZoom: number;
}

/**
 * Renders thinking toast notifications for nodes during execution
 */
const ThinkingToastRenderer = memo(function ThinkingToastRenderer({
  nodes,
  nodeExecutionStatuses,
  reactFlowInstance,
  showThinkingStream,
  currentZoom,
}: ThinkingToastRendererProps) {
  if (!reactFlowInstance || !showThinkingStream) return null;

  return (
    <>
      {nodes.map((node) => {
        // Skip ping nodes entirely
        if (node.data.label === 'ping' || node.data.label?.toLowerCase().includes('ping')) {
          return null;
        }

        const status = nodeExecutionStatuses[node.data.label];

        // Skip if no status
        if (!status) {
          return null;
        }

        // Show for running/thinking nodes with content, or recently completed
        const hasThinkingContent = status.thinking && status.thinking.trim().length > 0;
        const hasToolActivity = status.activeTool ||
          (status.toolCompleted && status.toolCompletedTime &&
            (Date.now() - status.toolCompletedTime < 2000));

        const isActive = (status.state === 'running' || status.state === 'thinking') &&
          (hasThinkingContent || hasToolActivity);

        const isRecentlyCompleted = status.state === 'completed' && status.endTime &&
          (Date.now() - new Date(status.endTime).getTime() < 3000) &&
          (hasThinkingContent || hasToolActivity);

        if (!isActive && !isRecentlyCompleted) {
          return null;
        }

        // Validate node position (must be valid numbers, not NaN/undefined)
        if (
          typeof node.position.x !== 'number' ||
          typeof node.position.y !== 'number' ||
          isNaN(node.position.x) ||
          isNaN(node.position.y)
        ) {
          return null;
        }

        // Calculate position in flow coordinates
        const flowX = node.position.x + (node.width || 200) / 2;
        const flowY = node.position.y + (node.height || 100) + 20; // 20px below node

        // Convert flow coordinates to screen coordinates
        let screenPosition;
        try {
          screenPosition = reactFlowInstance.flowToScreenPosition({
            x: flowX,
            y: flowY
          });
        } catch (error) {
          console.warn('[ThinkingToastRenderer] flowToScreenPosition failed:', error);
          return null;
        }

        // Skip if screen position is invalid (can happen during initial render)
        if (!screenPosition ||
          typeof screenPosition.x !== 'number' ||
          typeof screenPosition.y !== 'number' ||
          isNaN(screenPosition.x) ||
          isNaN(screenPosition.y)) {
          console.warn('[ThinkingToastRenderer] Invalid screen position:', screenPosition, 'for node:', node.data.label);
          return null;
        }

        // Determine what to display
        let displayText = status.thinking;
        let showToolStatus = false;

        // Check for recently completed tool (show for 2 seconds)
        if (status.toolCompleted && status.toolCompletedTime &&
          (Date.now() - status.toolCompletedTime < 2000)) {
          showToolStatus = true;
        }

        // Check for active tool
        if (status.activeTool) {
          showToolStatus = true;
        }

        // Only show toast if there's something to display
        if (!displayText && !showToolStatus) {
          return null;
        }

        return (
          <ThinkingToast
            key={`thinking-${node.id}`}
            text={displayText}
            nodePosition={screenPosition}
            isVisible={true}
            agentName={node.data.label}
            executionState={status.state === 'idle' ? undefined : status.state}
            activeTool={status.activeTool}
            toolCompleted={status.toolCompleted && status.toolCompletedTime &&
              (Date.now() - status.toolCompletedTime < 2000) ? status.toolCompleted : undefined}
            zoom={currentZoom}
            nodeWidth={node.width || 200}
          />
        );
      })}
    </>
  );
});

export default ThinkingToastRenderer;
