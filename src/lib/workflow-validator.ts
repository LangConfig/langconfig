/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { Node, Edge } from 'reactflow';

export interface ValidationError {
  type: 'error' | 'warning';
  message: string;
  nodeId?: string;
  edgeId?: string;
}

export interface ValidationResult {
  isValid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
}

/**
 * Validates a workflow before saving or executing
 */
export function validateWorkflow(
  nodes: Node[],
  edges: Edge[]
): ValidationResult {
  const errors: ValidationError[] = [];
  const warnings: ValidationError[] = [];

  // Rule 1: Must have at least one node
  if (nodes.length === 0) {
    errors.push({
      type: 'error',
      message: 'Workflow must contain at least one node',
    });
    return { isValid: false, errors, warnings };
  }

  // Rule 2: All nodes must have required config
  nodes.forEach((node) => {
    const config = node.data?.config;
    if (!config) {
      errors.push({
        type: 'error',
        message: `Node "${node.data?.label || node.id}" is missing configuration`,
        nodeId: node.id,
      });
    }

    if (!config?.model) {
      errors.push({
        type: 'error',
        message: `Node "${node.data?.label || node.id}" is missing model configuration`,
        nodeId: node.id,
      });
    }

    if (!config?.system_prompt || config.system_prompt.trim() === '') {
      warnings.push({
        type: 'warning',
        message: `Node "${node.data?.label || node.id}" has empty system prompt`,
        nodeId: node.id,
      });
    }
  });

  // Rule 3: Check for disconnected nodes (optional warning)
  if (nodes.length > 1 && edges.length === 0) {
    warnings.push({
      type: 'warning',
      message: 'Workflow has multiple nodes but no connections',
    });
  }

  // Rule 4: Check for orphaned nodes (nodes with no incoming or outgoing edges)
  if (edges.length > 0) {
    const connectedNodeIds = new Set<string>();
    edges.forEach((edge) => {
      connectedNodeIds.add(edge.source);
      connectedNodeIds.add(edge.target);
    });

    nodes.forEach((node) => {
      if (!connectedNodeIds.has(node.id)) {
        warnings.push({
          type: 'warning',
          message: `Node "${node.data?.label || node.id}" is not connected to the workflow`,
          nodeId: node.id,
        });
      }
    });
  }

  // Rule 5: Check for cycles (optional - LangGraph can handle cycles)
  const hasCycle = detectCycle(nodes, edges);
  if (hasCycle) {
    warnings.push({
      type: 'warning',
      message: 'Workflow contains a cycle. Ensure this is intentional.',
    });
  }

  return {
    isValid: errors.length === 0,
    errors,
    warnings,
  };
}

/**
 * Simple cycle detection using DFS
 */
function detectCycle(nodes: Node[], edges: Edge[]): boolean {
  const adjacency = new Map<string, string[]>();

  // Build adjacency list
  nodes.forEach((node) => adjacency.set(node.id, []));
  edges.forEach((edge) => {
    const targets = adjacency.get(edge.source) || [];
    targets.push(edge.target);
    adjacency.set(edge.source, targets);
  });

  const visited = new Set<string>();
  const recursionStack = new Set<string>();

  function dfs(nodeId: string): boolean {
    visited.add(nodeId);
    recursionStack.add(nodeId);

    const neighbors = adjacency.get(nodeId) || [];
    for (const neighbor of neighbors) {
      if (!visited.has(neighbor)) {
        if (dfs(neighbor)) return true;
      } else if (recursionStack.has(neighbor)) {
        return true; // Cycle detected
      }
    }

    recursionStack.delete(nodeId);
    return false;
  }

  for (const node of nodes) {
    if (!visited.has(node.id)) {
      if (dfs(node.id)) return true;
    }
  }

  return false;
}

/**
 * Get entry nodes (nodes with no incoming edges)
 */
export function getEntryNodes(nodes: Node[], edges: Edge[]): Node[] {
  const targetIds = new Set(edges.map((e) => e.target));
  return nodes.filter((node) => !targetIds.has(node.id));
}

/**
 * Get leaf nodes (nodes with no outgoing edges)
 */
export function getLeafNodes(nodes: Node[], edges: Edge[]): Node[] {
  const sourceIds = new Set(edges.map((e) => e.source));
  return nodes.filter((node) => !sourceIds.has(node.id));
}
