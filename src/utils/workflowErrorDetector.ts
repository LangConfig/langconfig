/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Workflow Error Detector
 *
 * Utility functions to analyze workflow execution events and detect common error patterns.
 * Helps provide actionable feedback to users when workflows fail or behave unexpectedly.
 */

import { WorkflowEvent } from '../types/events';

export interface ErrorDiagnosis {
  type: 'question_ending' | 'recursion_limit' | 'tool_access_issue' | 'tool_not_found' | 'loop_detected';
  severity: 'warning' | 'error';
  message: string;
  suggestion: string;
  nodeId?: string;
  toolName?: string;
  details?: any;
}

/**
 * Detect if agent output ends with a question, suggesting it's waiting for user input
 */
export function detectQuestionEnding(text: string): boolean {
  if (!text || typeof text !== 'string') return false;

  const trimmedText = text.trim();

  const questionPatterns = [
    /\?\s*$/,  // Ends with question mark
    /what would you like/i,
    /could you clarify/i,
    /could you provide/i,
    /please provide/i,
    /please specify/i,
    /can you tell me/i,
    /can you provide/i,
    /which option/i,
    /do you want/i,
    /should I/i,
    /would you prefer/i,
    /let me know/i,
  ];

  return questionPatterns.some(pattern => pattern.test(trimmedText));
}

/**
 * Detect if error message indicates recursion limit was hit
 */
export function detectRecursionLimit(error: string): boolean {
  if (!error || typeof error !== 'string') return false;

  return error.includes('Recursion limit') ||
    error.includes('GraphRecursionError') ||
    error.includes('recursion_limit') ||
    error.includes('maximum recursion depth');
}

/**
 * Analyze events to detect tool access issues
 * Returns details about which tools agents are trying to use vs what's configured
 */
export function detectToolAccessIssue(events: WorkflowEvent[]): ErrorDiagnosis | null {
  // Look for on_tool_start events that resulted in errors
  const toolErrors: Array<{ tool: string; agent: string; error?: string }> = [];
  const toolAttempts = new Map<string, number>();

  for (const event of events) {
    if (event.type === 'on_tool_start') {
      const toolName = event.data?.tool_name || event.data?.name;
      if (toolName) {
        toolAttempts.set(toolName, (toolAttempts.get(toolName) || 0) + 1);
      }
    }

    if (event.type === 'error') {
      const errorMsg = event.data?.error || event.data?.message || '';
      if (errorMsg.includes('tool') || errorMsg.includes('Tool')) {
        toolErrors.push({
          tool: event.data?.tool_name || 'unknown',
          agent: event.data?.agent_label || event.data?.node_id || 'unknown',
          error: errorMsg
        });
      }
    }
  }

  // Detect repeated failures with the same tool
  for (const [toolName, attempts] of toolAttempts.entries()) {
    if (attempts > 3) {
      return {
        type: 'tool_access_issue',
        severity: 'warning',
        message: `Agent attempting to use "${toolName}" repeatedly without success`,
        suggestion: 'Check if the tool is properly configured and accessible to this agent. Verify tool permissions and configuration.',
        toolName: toolName,
        details: { attempts }
      };
    }
  }

  if (toolErrors.length > 0) {
    const firstError = toolErrors[0];
    return {
      type: 'tool_not_found',
      severity: 'error',
      message: `Tool "${firstError.tool}" not available or misconfigured`,
      suggestion: 'Add this tool to the agent\'s configuration or check if the tool exists in your MCP servers.',
      nodeId: firstError.agent,
      toolName: firstError.tool,
      details: { error: firstError.error }
    };
  }

  return null;
}

/**
 * Detect if workflow is stuck in a loop (same tool called repeatedly with similar inputs)
 */
export function detectLoop(events: WorkflowEvent[]): ErrorDiagnosis | null {
  const recentToolCalls: Array<{ tool: string; agent: string; timestamp: string }> = [];

  // Get last 20 tool calls
  for (let i = events.length - 1; i >= 0 && recentToolCalls.length < 20; i--) {
    const event = events[i];
    if (event.type === 'on_tool_start') {
      recentToolCalls.unshift({
        tool: event.data?.tool_name || '',
        agent: event.data?.agent_label || event.data?.node_id || '',
        timestamp: event.timestamp || ''
      });
    }
  }

  if (recentToolCalls.length < 10) return null;

  // Check if same tool is being called >5 times in sequence
  const toolCounts = new Map<string, number>();
  let maxConsecutive = 0;
  let currentTool = '';
  let consecutiveCount = 0;
  let loopTool = '';

  for (const call of recentToolCalls) {
    toolCounts.set(call.tool, (toolCounts.get(call.tool) || 0) + 1);

    if (call.tool === currentTool) {
      consecutiveCount++;
      if (consecutiveCount > maxConsecutive) {
        maxConsecutive = consecutiveCount;
        loopTool = call.tool;
      }
    } else {
      currentTool = call.tool;
      consecutiveCount = 1;
    }
  }

  if (maxConsecutive >= 5) {
    return {
      type: 'loop_detected',
      severity: 'warning',
      message: `Possible loop detected: "${loopTool}" called ${maxConsecutive} times in sequence`,
      suggestion: 'The agent may be stuck. Check the system prompt for proper stop conditions or tool usage instructions.',
      toolName: loopTool,
      details: { consecutiveCalls: maxConsecutive }
    };
  }

  return null;
}

/**
 * Analyze all events and return a comprehensive diagnosis
 */
export function analyzeWorkflowEvents(events: WorkflowEvent[]): ErrorDiagnosis[] {
  const diagnoses: ErrorDiagnosis[] = [];

  // Check for tool access issues
  const toolIssue = detectToolAccessIssue(events);
  if (toolIssue) {
    diagnoses.push(toolIssue);
  }

  // Check for loops
  const loopIssue = detectLoop(events);
  if (loopIssue) {
    diagnoses.push(loopIssue);
  }

  // Check final output for question endings
  const completeEvents = events.filter(e => e.type === 'complete' || e.type === 'on_agent_finish');
  if (completeEvents.length > 0) {
    const lastComplete = completeEvents[completeEvents.length - 1];
    const output = lastComplete.data?.output || lastComplete.data?.result || '';

    if (detectQuestionEnding(output)) {
      diagnoses.push({
        type: 'question_ending',
        severity: 'warning',
        message: 'Workflow ended with agent asking a question',
        suggestion: 'The agent may be waiting for user input. Review your system prompt to ensure the agent knows how to complete tasks independently.',
        details: { output: output.substring(0, 200) }
      });
    }
  }

  // Check for recursion errors
  const errorEvents = events.filter(e => e.type === 'error');
  for (const errorEvent of errorEvents) {
    const errorMsg = errorEvent.data?.error || errorEvent.data?.message || '';
    if (detectRecursionLimit(errorMsg)) {
      diagnoses.push({
        type: 'recursion_limit',
        severity: 'error',
        message: 'Recursion limit reached without hitting stop condition',
        suggestion: 'The workflow exceeded its iteration limit. Consider: 1) Adding clear completion criteria to system prompts, 2) Increasing recursion limit, or 3) Reviewing workflow logic.',
        nodeId: errorEvent.data?.node_id || errorEvent.data?.agent_label,
        details: { error: errorMsg }
      });
    }
  }

  return diagnoses;
}

/**
 * Get real-time diagnosis as events stream in (for live panel)
 */
export function getLiveDiagnosis(latestEvent: WorkflowEvent, allEvents: WorkflowEvent[]): ErrorDiagnosis | null {
  // Check for immediate errors
  if (latestEvent.type === 'error') {
    const errorMsg = latestEvent.data?.error || latestEvent.data?.message || '';

    if (detectRecursionLimit(errorMsg)) {
      return {
        type: 'recursion_limit',
        severity: 'error',
        message: 'Recursion limit reached',
        suggestion: 'Workflow exceeded iteration limit. Review stop conditions or increase limit.',
        nodeId: latestEvent.data?.node_id,
        details: { error: errorMsg }
      };
    }
  }

  // Check for loop patterns every 10 events
  if (allEvents.length % 10 === 0) {
    return detectLoop(allEvents);
  }

  return null;
}
