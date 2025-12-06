/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useCallback, useState, useEffect, useRef, useMemo, memo, forwardRef, useImperativeHandle, createContext, useContext } from 'react';
import { calculateAndFormatCost } from '../../../../utils/modelPricing';
import { useAvailableModels } from '../../../../hooks/useAvailableModels';
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  BackgroundVariant,
  NodeProps,
  Panel,
  Handle,
  Position,
  MiniMap,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Save, Play, Download, Trash2, History as HistoryIcon, Copy, Check, Eye, EyeOff, List, StopCircle, Brain, Database, ChevronRight, X, Settings, FileText as FileIcon, FolderOpen, MessageSquare } from 'lucide-react';
import apiClient from '../../../../lib/api-client';
import { ConflictErrorClass } from '../../../../lib/api-client';
import ConflictDialog from '../ConflictDialog';
import ThinkingToast from '../../../../components/ui/ThinkingToast';
import LiveExecutionPanel from '../Execution/LiveExecutionPanel';
import { MemoryView } from '../../../memory/components/MemoryView';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeHighlight from 'rehype-highlight';
import rehypeKatex from 'rehype-katex';
import 'highlight.js/styles/github-dark.css';
import 'katex/dist/katex.min.css';
import { getModelDisplayName } from '../../../../lib/model-utils';
import { validateWorkflow } from '../../../../lib/workflow-validator';
import { validateNodePosition } from '../../../../utils/validation';
import { useWorkflowStream } from '../../../../hooks/useWorkflowStream';
import { useNodeExecutionStatus, NodeExecutionStatus } from '../../../../hooks/useNodeExecutionStatus';
import { useProject } from '../../../../contexts/ProjectContext';
import { useNotification } from '../../../../hooks/useNotification';
import { analyzeWorkflowEvents } from '../../../../utils/workflowErrorDetector';
import { exportToPDF } from '../../../../utils/exportHelpers';
import { useChat } from '../../../chat/context/ChatContext';

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
  custom_tools?: string[];
  timeout_seconds: number;
  max_retries: number;
  enable_model_routing: boolean;
  enable_parallel_tools: boolean;
  enable_memory: boolean;
  enable_rag?: boolean;
  requires_human_approval?: boolean;
  tags?: string[];
}

interface NodeData {
  label: string;
  agentType: string;
  model: string;
  config: {
    model: string;
    fallback_models?: string[];
    temperature: number;
    max_tokens?: number;
    system_prompt: string;
    tools: string[];
    native_tools: string[];
    cli_tools?: string[];
    custom_tools?: string[];
    timeout_seconds: number;
    max_retries: number;
    enable_model_routing: boolean;
    enable_parallel_tools: boolean;
    enable_memory: boolean;
    enable_rag?: boolean;
    requires_human_approval?: boolean;
    // Conversation context fields
    enable_conversation_context?: boolean;
    deep_agent_template_id?: number | null;
    context_mode?: 'recent' | 'smart' | 'full';
    context_window_size?: number;
    banked_message_ids?: string[];
  };
  executionStatus?: NodeExecutionStatus;
}

interface WorkflowExecutionContext {
  directive: string;
  query: string;
  task: string;
  classification: 'GENERAL' | 'BACKEND' | 'FRONTEND' | 'DEVOPS_IAC' | 'DATABASE' | 'API' | 'TESTING' | 'DOCUMENTATION' | 'CONFIGURATION';
  executor_type: 'default' | 'devops' | 'frontend' | 'database' | 'testing';
  max_retries: number;
}

// Ref interface for exposing methods to parent components
export interface WorkflowCanvasRef {
  updateNodeConfig: (nodeId: string, fullConfig: any) => void;
  deleteNode: (nodeId: string) => void;
  saveWorkflow: (silent?: boolean) => Promise<void>;
  hasUnsavedChanges: () => boolean;
  clearCanvas: () => void;
}

// Recipe type for multi-node workflow templates
export interface WorkflowRecipe {
  recipe_id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  tags: string[];
  nodes: any[];
  edges: any[];
  node_count: number;
  edge_count: number;
}

interface WorkflowCanvasProps {
  selectedAgent: Agent | null;
  selectedRecipe?: WorkflowRecipe | null;
  onWorkflowSelect?: (workflowId: number) => void;
  onNodeSelect?: (nodeId: string | null, nodeData?: NodeData | null) => void;
  onNodeDelete?: (nodeId: string) => void;
  onExecutionStart?: () => void;
  onAgentAdded?: () => void;
  onRecipeInserted?: () => void;
  workflowId?: number | null;
  onTabChange?: (tab: 'studio' | 'results') => void;
  initialTab?: 'studio' | 'results';
  onTokenCostUpdate?: (tokenInfo: { totalTokens: number; promptTokens: number; completionTokens: number; costString: string; }) => void;
}

const initialNodes: Node[] = [];
const initialEdges: Edge[] = [];

// Context for sharing updateNodeConfig with nested components
interface WorkflowCanvasContextValue {
  updateNodeConfig: (nodeId: string, config: any) => void;
  openNodeContextMenu: (nodeId: string, nodeData: NodeData, x: number, y: number) => void;
}

const WorkflowCanvasContext = createContext<WorkflowCanvasContextValue | null>(null);

// Hook to use the workflow canvas context
const useWorkflowCanvasContext = () => {
  const context = useContext(WorkflowCanvasContext);
  if (!context) {
    throw new Error('useWorkflowCanvasContext must be used within WorkflowCanvasContext.Provider');
  }
  return context;
};

// Custom Node Component with enhanced visuals and execution status - Memoized for performance
const CustomNode = memo(function CustomNode({ id, data, selected }: NodeProps) {
  // Always prefer data.config.model over data.model for display
  const modelName = data.config?.model || data.model;
  const agentType = data.agentType || 'default';
  const executionStatus = data.executionStatus;

  // Refs
  const nodeRef = useRef<HTMLDivElement>(null);
  const prevStatusRef = useRef<NodeExecutionStatus | undefined>(executionStatus);

  // Minimal state for model dropdown
  const [showModelDropdown, setShowModelDropdown] = useState(false);

  // Get functions from context
  const { updateNodeConfig, openNodeContextMenu } = useWorkflowCanvasContext();

  // Fetch available models for dropdown
  const { cloudModels, localModels } = useAvailableModels({
    includeLocal: true,
    onlyValidated: true
  });

  // State for expandable panel
  const [isPanelExpanded, setIsPanelExpanded] = useState(false);

  // Middleware state
  const [pauseBefore, setPauseBefore] = useState(data.config?.pauseBefore || false);
  const [pauseAfter, setPauseAfter] = useState(data.config?.pauseAfter || false);

  // Advanced settings state
  const [maxTokens, setMaxTokens] = useState(data.config?.max_tokens || 4000);
  const [maxRetries, setMaxRetries] = useState(data.config?.max_retries || 3);
  const [temperature, setTemperature] = useState(data.config?.temperature ?? 0.7);
  const [reasoningEffort, setReasoningEffort] = useState(data.config?.reasoning_effort || 'low');

  // Token cost info (from execution status or config)
  const tokenCost = data.tokenCost || executionStatus?.tokenCost;

  // Detect if this is a control node
  const isControlNode = ['START_NODE', 'END_NODE', 'CHECKPOINT_NODE', 'OUTPUT_NODE', 'CONDITIONAL_NODE', 'APPROVAL_NODE', 'TOOL_NODE'].includes(agentType);

  // Control node styling configuration - using theme colors
  const controlNodeStyles: Record<string, { icon: string; opacity: number }> = {
    START_NODE: { icon: 'play_circle', opacity: 0.7 },
    END_NODE: { icon: 'stop_circle', opacity: 0.5 },
    CHECKPOINT_NODE: { icon: 'bookmark', opacity: 0.6 },
    OUTPUT_NODE: { icon: 'output', opacity: 0.8 },
    CONDITIONAL_NODE: { icon: 'call_split', opacity: 0.65 },
    APPROVAL_NODE: { icon: 'how_to_reg', opacity: 0.75 },
    TOOL_NODE: { icon: 'construction', opacity: 0.8 },
  };

  const controlStyle = isControlNode ? controlNodeStyles[agentType] : null;

  // Determine border color based on execution state - MEMOIZED
  const borderColor = useMemo(() => {
    if (selected) return '#10b981'; // green-500 for selected
    if (!executionStatus || executionStatus.state === 'idle') return 'var(--color-primary)';

    switch (executionStatus.state) {
      case 'running':
      case 'thinking':
        return '#3b82f6'; // blue-500 for active
      case 'completed':
        return '#10b981'; // green-500 for success
      case 'error':
        return '#ef4444'; // red-500 for error
      default:
        return 'var(--color-primary)';
    }
  }, [selected, executionStatus]);

  // Simple CSS-based animations only (no heavy anime.js effects)
  // Just track previous status for conditional styling
  useEffect(() => {
    prevStatusRef.current = executionStatus;
  }, [executionStatus]);

  // Determine if we're in a dark theme (check if background is dark) - MEMOIZED
  const isDarkTheme = useMemo(() => {
    if (typeof document === 'undefined') return false;
    const theme = document.documentElement.getAttribute('data-theme');
    return theme ? ['dark', 'midnight', 'ocean', 'forest', 'botanical', 'godspeed'].includes(theme) : false;
  }, []); // Empty deps - theme doesn't change during node drag

  return (
    <div
      ref={nodeRef}
      className={`group px-5 py-6 shadow-xl ${agentType === 'TOOL_NODE' ? 'rounded-lg' : 'rounded-xl'
        } relative min-w-[220px] max-w-[220px] border-2 ${selected ? '' : 'hover:border-primary/50 hover:shadow-2xl'
        }`}
      style={{
        background: isDarkTheme
          ? `linear-gradient(135deg, var(--color-panel-dark) 0%, var(--color-background-dark) 100%)`
          : 'var(--color-primary)',
        backgroundColor: isDarkTheme ? 'var(--color-panel-dark)' : 'var(--color-primary)',
        borderColor: borderColor,
        opacity: (isControlNode && agentType !== 'TOOL_NODE') ? controlStyle?.opacity : 1,
        boxShadow: selected
          ? '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
          : '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
      }}
      onContextMenu={(e) => {
        e.preventDefault();
        openNodeContextMenu(id, data, e.clientX, e.clientY);
      }}
    >
      {/* Simple decorative overlay - no animation */}
      {!isControlNode && (
        <div
          className="absolute inset-0 rounded-xl pointer-events-none"
          style={{
            background: isDarkTheme
              ? 'linear-gradient(135deg, var(--color-primary) 0%, transparent 100%)'
              : 'linear-gradient(135deg, rgba(0, 0, 0, 0.1) 0%, transparent 100%)',
            opacity: isDarkTheme ? 0.05 : 0.03,
          }}
        />
      )}

      {/* Conversation Context Badge - Top Left */}
      {!isControlNode && data.config?.enable_conversation_context && (
        <div
          className="absolute top-2 left-2 flex items-center justify-center w-6 h-6 rounded-full"
          style={{
            backgroundColor: 'rgba(59, 130, 246, 0.2)',
            border: '1.5px solid #3b82f6',
            filter: 'drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3))',
          }}
          title="Conversation context enabled"
        >
          <MessageSquare
            className="w-3.5 h-3.5"
            style={{
              color: '#3b82f6',
              strokeWidth: 2.5
            }}
          />
        </div>
      )}

      {/* Tool Count Badge - Top Right */}
      {!isControlNode && (() => {
        const nativeToolCount = data.config?.native_tools?.length || 0;
        const builtInToolCount = data.config?.tools?.length || 0;
        const customToolCount = data.config?.custom_tools?.length || 0;  // ADDED: Count custom tools
        const toolCount = nativeToolCount + builtInToolCount + customToolCount;

        if (toolCount === 0) return null;

        return (
          <div
            className="absolute top-2 right-2 flex items-center gap-1"
            style={{
              filter: 'drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3))',
            }}
            title={`Tools: ${nativeToolCount} Native${customToolCount > 0 ? `, ${customToolCount} Custom` : ''}`}  // ADDED: Show breakdown in tooltip
          >
            <span
              className="material-symbols-outlined"
              style={{
                fontSize: '16px',
                color: customToolCount > 0 ? '#f59e0b' : (isDarkTheme ? 'var(--color-primary)' : 'var(--color-background-light)'),  // ADDED: Orange if has custom tools
                fontWeight: 600
              }}
            >
              construction
            </span>
            <span
              className="text-sm font-bold"
              style={{
                color: customToolCount > 0 ? '#f59e0b' : (isDarkTheme ? 'var(--color-primary)' : 'var(--color-background-light)')  // ADDED: Orange if has custom tools
              }}
            >
              {toolCount}
            </span>
          </div>
        );
      })()}

      {/* Warning Badge - Top Left */}
      {!isControlNode && executionStatus?.warnings && executionStatus.warnings.length > 0 && (
        <div
          className="absolute top-2 left-2 flex items-center gap-1 px-2 py-1 rounded-full cursor-help"
          style={{
            backgroundColor: executionStatus.warnings.some((w: { severity: string }) => w.severity === 'error') ? '#ef4444' : '#f59e0b',
            filter: 'drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3))',
          }}
          title={executionStatus.warnings.map((w: { message: string }) => w.message).join('\n')}
        >
          <span
            className="material-symbols-outlined"
            style={{
              fontSize: '14px',
              color: 'white',
              fontWeight: 600
            }}
          >
            {executionStatus.warnings.some((w: { severity: string }) => w.severity === 'error') ? 'error' : 'warning'}
          </span>
          <span className="text-xs font-bold text-white">
            {executionStatus.warnings.length}
          </span>
        </div>
      )}

      {/* Input Handle (Left) - Hidden for START nodes */}
      {agentType !== 'START_NODE' && (
        <Handle
          type="target"
          position={Position.Left}
          style={{
            width: '14px',
            height: '14px',
            backgroundColor: 'var(--color-primary)',
            border: '3px solid var(--color-primary)',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          }}
          className="transition-transform hover:scale-125"
          id="input"
        />
      )}

      {/* Node Header - Center aligned for better visual balance */}
      <div className="flex flex-col items-center text-center gap-2 relative z-10 w-full">
        {/* Optional icon from agent data */}
        {!isControlNode && data.icon && (
          <div className="flex-shrink-0">
            <span className="material-symbols-outlined" style={{
              fontSize: '28px',
              color: isDarkTheme ? 'var(--color-primary)' : 'var(--color-background-light)'
            }}>
              {data.icon}
            </span>
          </div>
        )}

        {/* Agent Name - Larger and bold */}
        <div className="font-bold text-lg leading-tight px-2" style={{
          color: isDarkTheme ? 'var(--color-text-primary)' : 'var(--color-background-light)'
        }}>
          {agentType === 'TOOL_NODE' && data.config?.tool_id
            ? data.config.tool_id
            : data.label}
        </div>

        {/* Model Name - Clickable to change model */}
        {modelName && modelName !== 'none' && (
          <div className="relative" style={{ zIndex: 9999 }}>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowModelDropdown(!showModelDropdown);
              }}
              className="text-xs font-medium px-3 py-1 rounded-full nodrag"
              style={{
                color: isDarkTheme ? 'var(--color-text-muted)' : 'var(--color-background-light)',
                backgroundColor: isDarkTheme
                  ? 'rgba(var(--color-primary-rgb, 99, 102, 241), 0.15)'
                  : 'rgba(255, 255, 255, 0.25)',
              }}
            >
              {getModelDisplayName(modelName)}
            </button>

            {/* Model Dropdown */}
            {showModelDropdown && (
              <div
                className="absolute bottom-full mb-2 left-1/2 transform -translate-x-1/2 rounded-lg shadow-xl nodrag nopan"
                style={{
                  backgroundColor: 'var(--color-background-dark)',
                  border: '2px solid var(--color-border-dark)',
                  minWidth: '220px',
                  maxHeight: '280px',
                  overflowY: 'auto',
                  zIndex: 9999,
                }}
                onClick={(e) => e.stopPropagation()}
                onWheel={(e) => e.stopPropagation()}
                onMouseDown={(e) => e.stopPropagation()}
              >
                {/* Cloud Models */}
                {cloudModels.length > 0 && (
                  <div>
                    <div
                      className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wide sticky top-0"
                      style={{
                        backgroundColor: 'var(--color-background-dark)',
                        color: 'var(--color-text-muted)',
                        borderBottom: '1px solid var(--color-border-dark)',
                      }}
                    >
                      Cloud Models
                    </div>
                    {cloudModels.map((model) => (
                      <button
                        key={model.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          const newConfig = {
                            ...data.config,
                            model: model.id
                          };
                          updateNodeConfig(id, newConfig);
                          setShowModelDropdown(false);
                        }}
                        className="w-full text-left px-3 py-2 text-sm transition-all"
                        style={{
                          color: data.config?.model === model.id ? '#ffffff' : 'var(--color-text-primary)',
                          backgroundColor: data.config?.model === model.id ? 'var(--color-primary)' : 'transparent',
                        }}
                        onMouseEnter={(e) => {
                          if (data.config?.model !== model.id) {
                            e.currentTarget.style.backgroundColor = 'var(--color-primary)';
                            e.currentTarget.style.color = '#ffffff';
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (data.config?.model !== model.id) {
                            e.currentTarget.style.backgroundColor = 'transparent';
                            e.currentTarget.style.color = 'var(--color-text-primary)';
                          }
                        }}
                      >
                        {model.name}
                      </button>
                    ))}
                  </div>
                )}

                {/* Local Models */}
                {localModels.length > 0 && (
                  <div>
                    <div
                      className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wide sticky top-0"
                      style={{
                        backgroundColor: 'var(--color-background-dark)',
                        color: 'var(--color-text-muted)',
                        borderBottom: '1px solid var(--color-border-dark)',
                      }}
                    >
                      Local Models
                    </div>
                    {localModels.map((model) => (
                      <button
                        key={model.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          const newConfig = {
                            ...data.config,
                            model: model.id
                          };
                          updateNodeConfig(id, newConfig);
                          setShowModelDropdown(false);
                        }}
                        className="w-full text-left px-3 py-2 text-sm transition-all"
                        style={{
                          color: data.config?.model === model.id ? '#ffffff' : 'var(--color-text-primary)',
                          backgroundColor: data.config?.model === model.id ? 'var(--color-primary)' : 'transparent',
                        }}
                        onMouseEnter={(e) => {
                          if (data.config?.model !== model.id) {
                            e.currentTarget.style.backgroundColor = 'var(--color-primary)';
                            e.currentTarget.style.color = '#ffffff';
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (data.config?.model !== model.id) {
                            e.currentTarget.style.backgroundColor = 'transparent';
                            e.currentTarget.style.color = 'var(--color-text-primary)';
                          }
                        }}
                      >
                        {model.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Control Node Label */}
        {isControlNode && (
          <div className="text-xs font-medium italic opacity-70" style={{ color: 'var(--color-text-muted)' }}>
            Control Node
          </div>
        )}
      </div>

      {/* Output Handle (Right) - Hidden for END nodes */}
      {agentType !== 'END_NODE' && (
        <Handle
          type="source"
          position={Position.Right}
          style={{
            width: '14px',
            height: '14px',
            backgroundColor: 'var(--color-primary)',
            border: '3px solid var(--color-primary)',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          }}
          className="transition-transform hover:scale-125"
          id="output"
        />
      )}

      {/* Selection indicator */}
      {selected && !isControlNode && (
        <div className="absolute -inset-1 bg-primary/10 rounded-xl -z-10 animate-pulse" />
      )}

      {/* Expand/Collapse Button - Only for regular agent nodes */}
      {!isControlNode && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            setIsPanelExpanded(!isPanelExpanded);
          }}
          className="absolute -bottom-3 left-1/2 transform -translate-x-1/2 nodrag nopan z-20 transition-all hover:scale-110"
          style={{
            width: '24px',
            height: '24px',
            borderRadius: '50%',
            backgroundColor: 'var(--color-primary)',
            border: '2px solid var(--color-background-dark)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
          }}
        >
          <span
            className="material-symbols-outlined"
            style={{
              fontSize: '16px',
              color: 'white',
              transform: isPanelExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
              transition: 'transform 0.2s'
            }}
          >
            expand_more
          </span>
        </button>
      )}

      {/* Expandable Panel - Positioned below node */}
      {!isControlNode && isPanelExpanded && (
        <div
          className="absolute top-full mt-4 left-1/2 transform -translate-x-1/2 nodrag nopan z-30 rounded-lg shadow-2xl border-2 overflow-hidden"
          style={{
            backgroundColor: 'var(--color-panel-dark)',
            borderColor: 'var(--color-border-dark)',
            minWidth: '240px',
            maxWidth: '260px',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Panel Content */}
          <div className="p-3 space-y-2.5">
            {/* Quick Settings Row 1 - Pause Options */}
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-1.5 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={pauseBefore}
                  onChange={(e) => {
                    const newValue = e.target.checked;
                    setPauseBefore(newValue);
                    const newConfig = {
                      ...data.config,
                      pauseBefore: newValue
                    };
                    updateNodeConfig(id, newConfig);
                  }}
                  className="w-3.5 h-3.5 text-primary rounded focus:ring-2 focus:ring-primary cursor-pointer"
                />
                <div className="text-[11px] font-medium whitespace-nowrap" style={{ color: 'var(--color-text-primary)' }}>
                  Pause Before
                </div>
              </label>

              <label className="flex items-center gap-1.5 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={pauseAfter}
                  onChange={(e) => {
                    const newValue = e.target.checked;
                    setPauseAfter(newValue);
                    const newConfig = {
                      ...data.config,
                      pauseAfter: newValue
                    };
                    updateNodeConfig(id, newConfig);
                  }}
                  className="w-3.5 h-3.5 text-primary rounded focus:ring-2 focus:ring-primary cursor-pointer"
                />
                <div className="text-[11px] font-medium whitespace-nowrap" style={{ color: 'var(--color-text-primary)' }}>
                  Pause After
                </div>
              </label>
            </div>

            {/* Quick Settings Row 2 - Temperature Slider */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-[10px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
                  Temperature
                </label>
                <span className="text-[10px] font-mono font-medium px-1.5 py-0.5 rounded" style={{
                  color: 'var(--color-text-primary)',
                  backgroundColor: 'var(--color-background-dark)'
                }}>
                  {temperature.toFixed(1)}
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={temperature}
                onChange={(e) => {
                  const newValue = parseFloat(e.target.value);
                  setTemperature(newValue);
                  const newConfig = {
                    ...data.config,
                    temperature: newValue
                  };
                  updateNodeConfig(id, newConfig);
                }}
                className="w-full h-1.5 rounded-lg appearance-none cursor-pointer"
                style={{
                  backgroundColor: 'var(--color-border-dark)',
                  accentColor: 'var(--color-primary)'
                }}
              />
            </div>

            {/* Quick Settings Row 3 - Compact Number Inputs */}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] font-medium block mb-1" style={{ color: 'var(--color-text-muted)' }}>
                  Max Tokens
                </label>
                <input
                  type="number"
                  value={maxTokens}
                  onChange={(e) => {
                    const newValue = parseInt(e.target.value) || 4000;
                    setMaxTokens(newValue);
                    const newConfig = {
                      ...data.config,
                      max_tokens: newValue
                    };
                    updateNodeConfig(id, newConfig);
                  }}
                  min="100"
                  max="16000"
                  step="100"
                  className="w-full px-1.5 py-0.5 text-[11px] border rounded focus:outline-none focus:ring-1 focus:ring-primary"
                  style={{
                    backgroundColor: 'var(--color-background-light)',
                    borderColor: 'var(--color-border-dark)',
                    color: 'var(--color-text-primary)'
                  }}
                />
              </div>

              <div>
                <label className="text-[10px] font-medium block mb-1" style={{ color: 'var(--color-text-muted)' }}>
                  Retries
                </label>
                <input
                  type="number"
                  value={maxRetries}
                  onChange={(e) => {
                    const newValue = parseInt(e.target.value) || 3;
                    setMaxRetries(newValue);
                    const newConfig = {
                      ...data.config,
                      max_retries: newValue
                    };
                    updateNodeConfig(id, newConfig);
                  }}
                  min="0"
                  max="10"
                  className="w-full px-1.5 py-0.5 text-[11px] border rounded focus:outline-none focus:ring-1 focus:ring-primary"
                  style={{
                    backgroundColor: 'var(--color-background-light)',
                    borderColor: 'var(--color-border-dark)',
                    color: 'var(--color-text-primary)'
                  }}
                />
              </div>
            </div>

            {/* Reasoning Effort Dropdown - For Gemini models */}
            {modelName && modelName.startsWith('gemini') && (
              <div>
                <label className="text-[10px] font-medium block mb-1" style={{ color: 'var(--color-text-muted)' }}>
                  Reasoning Effort
                </label>
                <select
                  value={reasoningEffort}
                  onChange={(e) => {
                    const newValue = e.target.value;
                    setReasoningEffort(newValue);
                    const newConfig = {
                      ...data.config,
                      reasoning_effort: newValue
                    };
                    updateNodeConfig(id, newConfig);
                  }}
                  className="w-full px-1.5 py-1 text-[11px] border rounded focus:outline-none focus:ring-1 focus:ring-primary"
                  style={{
                    backgroundColor: 'var(--color-background-light)',
                    borderColor: 'var(--color-border-dark)',
                    color: 'var(--color-text-primary)'
                  }}
                >
                  <option value="none">None (96% cheaper)</option>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
                <div className="text-[9px] mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                  {reasoningEffort === 'none' && 'Maximum cost savings'}
                  {reasoningEffort === 'low' && 'Balanced performance'}
                  {reasoningEffort === 'medium' && 'Enhanced reasoning'}
                  {reasoningEffort === 'high' && 'Maximum reasoning depth'}
                </div>
              </div>
            )}

            {/* Divider */}
            <div className="border-t" style={{ borderColor: 'var(--color-border-dark)' }} />

            {/* Token Statistics - Bottom */}
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span style={{ color: 'var(--color-text-muted)' }}>Prompt Tokens</span>
                <span className="font-mono font-medium" style={{ color: 'var(--color-text-primary)' }}>
                  {tokenCost?.promptTokens?.toLocaleString() || '0'}
                </span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: 'var(--color-text-muted)' }}>Completion</span>
                <span className="font-mono font-medium" style={{ color: 'var(--color-text-primary)' }}>
                  {tokenCost?.completionTokens?.toLocaleString() || '0'}
                </span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: 'var(--color-text-muted)' }}>Total Tokens</span>
                <span className="font-mono font-medium" style={{ color: 'var(--color-text-primary)' }}>
                  {tokenCost?.totalTokens?.toLocaleString() || '0'}
                </span>
              </div>
              <div className="pt-1 border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
                <div className="flex justify-between">
                  <span className="font-medium" style={{ color: 'var(--color-text-muted)' }}>Cost</span>
                  <span className="font-mono font-bold" style={{ color: 'var(--color-primary)' }}>
                    {tokenCost?.costString || '$0.00'}
                  </span>
                </div>
                {tokenCost && tokenCost.totalTokens > 0 && (
                  <div className="text-[10px] mt-1" style={{ color: 'var(--color-text-muted)' }}>
                    Priced for {getModelDisplayName(modelName)}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
});

// nodeTypes will be memoized inside the component

interface TaskFile {
  filename: string;
  path: string;
  size_bytes: number;
  size_human: string;
  modified_at: string;
  extension: string;
}

const WorkflowCanvas = forwardRef<WorkflowCanvasRef, WorkflowCanvasProps>(({
  selectedAgent,
  selectedRecipe,
  onNodeSelect,
  onNodeDelete,
  onExecutionStart,
  onAgentAdded,
  onRecipeInserted,
  workflowId,
  onTabChange,
  initialTab,
  onTokenCostUpdate
}, ref) => {
  const { showSuccess, logError, showWarning, NotificationModal } = useNotification();
  const { openChat } = useChat();
  const [nodes, setNodes, onNodesChangeBase] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Wrap onNodesChange with position validation
  const onNodesChange = useCallback((changes: any[]) => {
    const validatedChanges = changes.map((change) => {
      // Validate position changes
      if (change.type === 'position' && change.position) {
        const validation = validateNodePosition(change.position.x, change.position.y);
        if (!validation.isValid) {
          console.warn(`Invalid position change for node ${change.id}: ${validation.error}. Ignoring change.`);
          return null; // Skip this change
        }
      }
      return change;
    }).filter(Boolean); // Remove null changes

    onNodesChangeBase(validatedChanges);
  }, [onNodesChangeBase]);

  const [nodeIdCounter, setNodeIdCounter] = useState(1);
  const [currentWorkflowId, setCurrentWorkflowId] = useState<number | null>(workflowId || null);
  const [currentTaskId, setCurrentTaskId] = useState<number | null>(() => {
    // Restore task ID from localStorage on load
    const savedTaskId = localStorage.getItem('langconfig-current-task-id');
    return savedTaskId ? parseInt(savedTaskId, 10) : null;
  });

  // Optimistic Locking
  const [currentLockVersion, setCurrentLockVersion] = useState<number>(1);
  const [showConflictDialog, setShowConflictDialog] = useState(false);
  const [conflictData, setConflictData] = useState<{
    localData: any;
    remoteData: any;
  } | null>(null);
  const [reactFlowInstance, setReactFlowInstance] = useState<any>(null);
  const [currentZoom, setCurrentZoom] = useState(1); // Track zoom level for toasts
  const [activeTab, setActiveTab] = useState<'studio' | 'results'>(() => {
    // Initialize from URL hash if present
    const hash = window.location.hash.replace('#', '');
    if (hash === 'results') return 'results';
    return 'studio';
  });
  const [taskHistory, setTaskHistory] = useState<any[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [executionStatus, setExecutionStatus] = useState({
    state: 'idle' as 'idle' | 'running' | 'completed' | 'failed',
    currentNode: undefined as string | undefined,
    progress: 0,
    startTime: undefined as string | undefined,
    duration: undefined as string | undefined,
  });
  const [showExecutionDialog, setShowExecutionDialog] = useState(false);
  const [showAdvancedOptions, setShowAdvancedOptions] = useState(false);
  const [executionConfig, setExecutionConfig] = useState<WorkflowExecutionContext>({
    directive: '',
    query: '',
    task: '',
    classification: 'GENERAL',
    executor_type: 'default',
    max_retries: 3,
  });
  const [contextDocuments, setContextDocuments] = useState<number[]>([]);
  const [availableDocuments, setAvailableDocuments] = useState<any[]>([]);
  const [additionalContext, setAdditionalContext] = useState('');
  const hasLoadedRef = useRef(false);
  const isDraggingRef = useRef(false); // Track if user is currently dragging a node
  const [workflowName, setWorkflowName] = useState('Untitled Workflow');
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState(workflowName);
  const [showWorkflowDropdown, setShowWorkflowDropdown] = useState(false);
  const [workflowSearchQuery, setWorkflowSearchQuery] = useState('');

  // Results view state
  const [copiedToClipboard, setCopiedToClipboard] = useState(false);
  const [showRawOutput, setShowRawOutput] = useState(false);
  const [resultsSubTab, setResultsSubTab] = useState<'output' | 'memory' | 'files'>('output'); // Results subtabs
  const [files, setFiles] = useState<TaskFile[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [filesError, setFilesError] = useState<string | null>(null);
  const [showThinkingStream, setShowThinkingStream] = useState(false); // Toggle for thinking toast notifications on canvas
  const [showLiveExecutionPanel, setShowLiveExecutionPanel] = useState(false); // Toggle for live execution panel
  const [showAnimatedReveal, setShowAnimatedReveal] = useState(true);
  const [showReplayPanel, setShowReplayPanel] = useState(false); // Toggle for execution log replay
  const [replayTaskId, setReplayTaskId] = useState<number | null>(null); // Task ID for replay panel

  // Workflow Settings
  const [checkpointerEnabled, setCheckpointerEnabled] = useState(false);
  const [globalRecursionLimit, setGlobalRecursionLimit] = useState(300);
  const [showSettingsModal, setShowSettingsModal] = useState(false);

  // Per-node token costs stored by node label (persists across node deletions/recreations)
  const [nodeTokenCosts, setNodeTokenCosts] = useState<Record<string, {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
    costString: string;
  }>>(() => {
    // Load from localStorage on mount
    if (currentWorkflowId) {
      const saved = localStorage.getItem(`workflow-${currentWorkflowId}-token-costs`);
      if (saved) {
        try {
          return JSON.parse(saved);
        } catch (e) {
          console.error('Failed to parse saved token costs:', e);
        }
      }
    }
    return {};
  });
  const [selectedHistoryTask, setSelectedHistoryTask] = useState<any>(null); // Selected task from history sidebar
  const [expandedToolCalls, setExpandedToolCalls] = useState<Set<number>>(new Set()); // Track which tool calls are expanded
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useState(() => {
    // Load from localStorage
    const saved = localStorage.getItem('workflow-history-collapsed');
    return saved ? JSON.parse(saved) : false; // Default to expanded
  });

  // Context menu state for task deletion
  const [taskContextMenu, setTaskContextMenu] = useState<{
    taskId: number;
    x: number;
    y: number;
  } | null>(null);

  // Context menu state for node operations
  const [nodeContextMenu, setNodeContextMenu] = useState<{
    nodeId: string;
    nodeData: NodeData;
    x: number;
    y: number;
  } | null>(null);

  // Save to library modal state
  const [showSaveToLibraryModal, setShowSaveToLibraryModal] = useState(false);
  const [saveToLibraryData, setSaveToLibraryData] = useState<{
    nodeId: string;
    nodeData: NodeData;
  } | null>(null);
  const [agentLibraryName, setAgentLibraryName] = useState('');
  const [agentLibraryDescription, setAgentLibraryDescription] = useState('');

  // Chat with unsaved agent warning modal
  const [showChatWarningModal, setShowChatWarningModal] = useState(false);

  // Project context
  const { activeProjectId } = useProject();
  const [availableWorkflows, setAvailableWorkflows] = useState<any[]>([]);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [saveWorkflowName, setSaveWorkflowName] = useState('');

  // Version management state
  const [versions, setVersions] = useState<any[]>([]);
  const [currentVersion, setCurrentVersion] = useState<any | null>(null);
  const [showVersionModal, setShowVersionModal] = useState(false);
  const [versionNotes, setVersionNotes] = useState('');
  const [showVersionDropdown, setShowVersionDropdown] = useState(false);
  const [showDebugModal, setShowDebugModal] = useState(false);  // ADDED: Debug workflow modal
  const [debugData, setDebugData] = useState<any>(null);  // ADDED: Debug data from backend
  const [loadingVersions, setLoadingVersions] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);  // Track unsaved changes
  const [lastSavedState, setLastSavedState] = useState<string>('');  // Track last saved state for comparison

  // Version comparison state
  const [compareMode, setCompareMode] = useState(false);
  const [compareVersion1, setCompareVersion1] = useState<any | null>(null);
  const [compareVersion2, setCompareVersion2] = useState<any | null>(null);
  const [versionComparison, setVersionComparison] = useState<any | null>(null);
  const [loadingComparison, setLoadingComparison] = useState(false);

  // Memoize nodeTypes to prevent React Flow warnings about recreation
  const nodeTypes = useMemo(() => ({
    custom: CustomNode,
  }), []);

  // Validate nodes and edges before passing to ReactFlow to prevent NaN rendering errors
  const validatedNodes = useMemo(() => {
    return nodes.map((node, index) => {
      const hasValidPosition =
        node.position &&
        typeof node.position.x === 'number' &&
        typeof node.position.y === 'number' &&
        !isNaN(node.position.x) &&
        !isNaN(node.position.y) &&
        isFinite(node.position.x) &&
        isFinite(node.position.y);

      if (!hasValidPosition) {
        console.warn(`Node ${node.id} has invalid position:`, node.position, '- fixing to default position');
        // Fix the position instead of filtering out the node
        return {
          ...node,
          position: {
            x: 250 + (index * 300),
            y: 250
          }
        };
      }

      return node;
    });
  }, [nodes]);

  const validatedEdges = useMemo(() => {
    const validNodeIds = new Set(validatedNodes.map(n => n.id));
    return edges.filter(edge => {
      const isValid = validNodeIds.has(edge.source) && validNodeIds.has(edge.target);
      if (!isValid) {
        console.warn(`Edge ${edge.id} connects to invalid nodes:`, edge.source, edge.target);
      }
      return isValid;
    });
  }, [edges, validatedNodes]);

  // Use workflow stream hook to get events and formatted output
  // Only connect when there's an active task running
  const { events: workflowEvents, latestEvent, clearEvents } = useWorkflowStream(currentWorkflowId, {
    autoConnect: executionStatus.state === 'running' && currentTaskId !== null,
    maxEvents: 10000, // Increased to 10000 to handle very long workflows
    taskId: currentTaskId,
    loadHistorical: true,
    tokenBufferMs: 16 // Smooth 60fps streaming
  });

  // Separate hook for replay panel - loads historical events independently
  const { events: replayEvents, isLoadingHistorical: _replayLoading } = useWorkflowStream(currentWorkflowId, {
    autoConnect: false, // Never connect to live stream in replay
    maxEvents: 10000,
    taskId: replayTaskId,
    loadHistorical: true,
    tokenBufferMs: 16
  });

  // Use node execution status hook to track real-time execution state
  // Only track when there's an active task
  const nodeExecutionStatuses = useNodeExecutionStatus(
    executionStatus.state === 'running' ? currentWorkflowId : null,
    {
      taskId: executionStatus.state === 'running' ? currentTaskId : null,
    }
  );

  // Analyze events for errors and warnings, attach to nodes
  const [nodeWarnings, setNodeWarnings] = useState<Record<string, Array<{ type: string; severity: 'warning' | 'error'; message: string }>>>({});

  useEffect(() => {
    if (workflowEvents.length > 0) {
      // Analyze workflow events for common issues
      const diagnoses = analyzeWorkflowEvents(workflowEvents);

      // Map diagnoses to nodes
      const warningsMap: Record<string, Array<{ type: string; severity: 'warning' | 'error'; message: string }>> = {};

      diagnoses.forEach(diagnosis => {
        // Get node ID from diagnosis or find the relevant node
        const nodeId = diagnosis.nodeId || 'unknown';

        if (!warningsMap[nodeId]) {
          warningsMap[nodeId] = [];
        }

        warningsMap[nodeId].push({
          type: diagnosis.type,
          severity: diagnosis.severity,
          message: diagnosis.message
        });

        // DISABLED: Don't show error popups - user wants uninterrupted stream
        // if (diagnosis.severity === 'error') {
        //   logError(diagnosis.message, diagnosis.suggestion);
        // }
      });

      setNodeWarnings(warningsMap);

      // Check for errors in the events (for logging only - errors are displayed in LiveExecutionPanel)
      const errorEvents = workflowEvents.filter(e => e.type === 'error');
      if (errorEvents.length > 0) {
        const latestError = errorEvents[errorEvents.length - 1];
        console.error('[WorkflowCanvas] Workflow error detected:', latestError.data);
      }

      // Check for complete event with error status - stop execution spinner
      const completeEvent = workflowEvents.find(e => e.type === 'complete');
      if (completeEvent?.data?.status === 'error') {
        console.log('[WorkflowCanvas] Workflow completed with error status');
        // Stop execution state if still running
        if (executionStatus.state === 'running') {
          setExecutionStatus({
            state: 'idle' as const,
            nodeStates: {},
            errorMessage: completeEvent.data?.error || 'Workflow failed'
          });
        }
      }

      // Check for warnings (e.g., short agent outputs)
      // DISABLED: Don't show popup warnings during live execution
      // const warningEvents = workflowEvents.filter(e => e.type === 'warning');
      // warningEvents.forEach(warning => {
      //   showWarning(warning.data.message, `Suggestion: ${warning.data.suggestion}`);
      // });
    }
  }, [workflowEvents, latestEvent, executionStatus.state]);

  // Handle recursion limit - continue with new limit
  // Save nodeTokenCosts to localStorage whenever they change
  useEffect(() => {
    if (currentWorkflowId && Object.keys(nodeTokenCosts).length > 0) {
      localStorage.setItem(`workflow-${currentWorkflowId}-token-costs`, JSON.stringify(nodeTokenCosts));
    }
  }, [nodeTokenCosts, currentWorkflowId]);

  // Update nodeTokenCosts when execution status has token cost data
  useEffect(() => {
    Object.entries(nodeExecutionStatuses).forEach(([nodeLabel, status]) => {
      if (status.tokenCost) {
        setNodeTokenCosts(prev => {
          // Only update if different to avoid unnecessary re-renders
          if (prev[nodeLabel]?.totalTokens === status.tokenCost?.totalTokens) {
            return prev;
          }
          const newCosts = { ...prev };
          newCosts[nodeLabel] = status.tokenCost!;
          return newCosts;
        });
      }
    });
  }, [nodeExecutionStatuses]);

  // Update nodes with execution status whenever it changes - OPTIMIZED to only update changed nodes
  useEffect(() => {
    setNodes((nds) =>
      nds.map((node) => {
        const newStatus = nodeExecutionStatuses[node.data.label];

        // Get persisted token cost for this node label
        const persistedTokenCost = nodeTokenCosts[node.data.label];

        // Use token cost from status if available, otherwise use persisted
        const tokenCost = newStatus?.tokenCost || persistedTokenCost;

        // Attach warnings to the status if available
        const warnings = nodeWarnings[node.data.label] || nodeWarnings[node.id];
        const statusWithWarnings = newStatus && warnings ? { ...newStatus, warnings } : newStatus;

        // Only update if status, token cost, or warnings changed (prevents unnecessary re-renders)
        if (node.data.executionStatus === statusWithWarnings && node.data.tokenCost === tokenCost) {
          return node; // Return same object reference - React.memo will skip re-render
        }

        return {
          ...node,
          data: {
            ...node.data,
            executionStatus: statusWithWarnings,
            // Use persisted token cost by label (survives node deletion/recreation)
            tokenCost: tokenCost,
          },
        };
      })
    );
  }, [nodeExecutionStatuses, nodeTokenCosts, nodeWarnings, setNodes]);

  // Update URL when tab changes - delegate to parent component
  const handleTabChange = useCallback((newTab: 'studio' | 'results') => {
    setActiveTab(newTab);
    onTabChange?.(newTab);
  }, [onTabChange]);

  // Fetch files for the current task
  const fetchFiles = useCallback(async () => {
    if (!currentTaskId) return;

    setFilesLoading(true);
    setFilesError(null);

    try {
      const response = await fetch(`/api/workspace/tasks/${currentTaskId}/files`);
      if (!response.ok) {
        throw new Error('Failed to fetch files');
      }

      const data = await response.json();
      setFiles(data.files || []);
    } catch (error) {
      console.error('Error fetching files:', error);
      setFilesError(error instanceof Error ? error.message : 'Failed to load files');
    } finally {
      setFilesLoading(false);
    }
  }, [currentTaskId]);

  // Download a file from the workspace
  const handleDownloadFile = useCallback((filename: string) => {
    if (!currentTaskId) return;
    window.open(`/api/workspace/tasks/${currentTaskId}/files/${filename}`, '_blank');
  }, [currentTaskId]);

  // Fetch files when Results tab is active and Files subtab is selected
  useEffect(() => {
    if (activeTab === 'results' && resultsSubTab === 'files' && currentTaskId) {
      fetchFiles();
    }
  }, [activeTab, resultsSubTab, currentTaskId, fetchFiles]);

  // Re-center canvas when execution starts and animate edges
  useEffect(() => {
    if (executionStatus.state === 'running' && reactFlowInstance && nodes.length > 0) {
      // Delay slightly to ensure nodes are updated
      setTimeout(() => {
        reactFlowInstance.fitView({ padding: 0.5, maxZoom: 0.6, duration: 400 });
      }, 200);

      // Animate edges during execution
      setEdges((eds) =>
        eds.map((edge) => ({
          ...edge,
          animated: true,
        }))
      );
    } else if (executionStatus.state === 'idle' || executionStatus.state === 'completed' || executionStatus.state === 'failed') {
      // Stop animating edges when not executing
      setEdges((eds) =>
        eds.map((edge) => ({
          ...edge,
          animated: false,
        }))
      );
    }
  }, [executionStatus.state, reactFlowInstance, nodes.length, setEdges]);


  // Sync activeTab with initialTab prop from parent
  useEffect(() => {
    if (initialTab) {
      setActiveTab(initialTab);
    }
  }, [initialTab]);

  // Extract user prompt from latest execution
  const userPrompt = useMemo(() => {
    // First try to get from the latest task in history
    if (taskHistory.length > 0) {
      const latestTask = taskHistory[0];
      // Extract from agent_messages if available (first human message)
      if (latestTask.result?.agent_messages) {
        for (const msg of latestTask.result.agent_messages) {
          if (msg.role === 'human') {
            return msg.content;
          }
        }
      }
    }

    // Fallback: Try to get from workflow events (status event with input_data)
    for (const event of workflowEvents) {
      if (event.data?.input_data?.query) {
        return event.data.input_data.query;
      }
    }

    return null;
  }, [taskHistory, workflowEvents]);

  // Memoize model name extraction for performance
  const currentModelName = useMemo(() => {
    // Try to get from workflow configuration first
    if (currentWorkflowId && availableWorkflows.length > 0) {
      const workflow = availableWorkflows.find(w => w.id === currentWorkflowId);
      if (workflow?.configuration?.nodes?.[0]?.config?.model) {
        return workflow.configuration.nodes[0].config.model;
      }
    }
    // Fallback to nodes state
    if (nodes.length > 0 && nodes[0].data.config?.model) {
      return nodes[0].data.config.model;
    }
    return 'default';
  }, [currentWorkflowId, availableWorkflows, nodes]);

  const workflowMetrics = useMemo(() => {
    const chainEnds = workflowEvents.filter(e => e.type === 'on_chain_end').length;
    const toolCalls = workflowEvents.filter(e => e.type === 'on_tool_start').length;
    const agentActions = workflowEvents.filter(e => e.type === 'on_agent_action').length;
    const llmCalls = workflowEvents.filter(e => e.type === 'on_llm_end').length;
    const errors = workflowEvents.filter(e => e.type === 'error').length;

    let totalTokens = 0;
    workflowEvents.filter(e => e.type === 'on_llm_end').forEach(e => {
      if (e.data?.tokens_used) {
        totalTokens += e.data.tokens_used;
      }
    });

    const firstEvent = workflowEvents[0];
    const lastEvent = workflowEvents[workflowEvents.length - 1];
    let duration = '0s';
    if (firstEvent && lastEvent && firstEvent.timestamp && lastEvent.timestamp) {
      const start = new Date(firstEvent.timestamp).getTime();
      const end = new Date(lastEvent.timestamp).getTime();
      const durationMs = end - start;
      const seconds = Math.floor(durationMs / 1000);
      const minutes = Math.floor(seconds / 60);
      if (minutes > 0) {
        duration = `${minutes}m ${seconds % 60}s`;
      } else {
        duration = `${seconds}s`;
      }
    }

    return {
      totalEvents: workflowEvents.length,
      chainEnds,
      toolCalls,
      agentActions,
      llmCalls,
      totalTokens,
      errors,
      duration
    };
  }, [workflowEvents]);

  // Log workflow metrics for debugging/analytics
  useEffect(() => {
    if (workflowMetrics.totalEvents > 0) {
      console.log('[WorkflowCanvas] Workflow Metrics Updated:', workflowMetrics);
    }
  }, [workflowMetrics]);

  // Detect workflow completion from events
  useEffect(() => {
    if (workflowEvents.length > 0) {
      const lastEvent = workflowEvents[workflowEvents.length - 1];

      // Check for completion or error
      if (lastEvent.type === 'complete') {
        setExecutionStatus(prev => ({
          ...prev,
          state: 'completed',
          progress: 100,
        }));

        // Refresh task history to get the new result
        fetchTaskHistory();

        // Auto-switch to results tab when workflow completes successfully
        setTimeout(() => {
          handleTabChange('results');
        }, 500); // Small delay to ensure history is fetched
      }
      // DISABLED: Don't stop stream on error events - let workflow complete naturally
      // else if (lastEvent.type === 'error') {
      //   setExecutionStatus(prev => ({
      //     ...prev,
      //     state: 'failed',
      //     progress: 0,
      //   }));
      // }
    }
  }, [workflowEvents]);

  // Callback to update status from monitoring panel
  // Fetch task history when workflow loads or changes
  useEffect(() => {
    if (currentWorkflowId) {
      fetchTaskHistory();
    }
  }, [currentWorkflowId]);

  // Save history collapsed state to localStorage
  useEffect(() => {
    localStorage.setItem('workflow-history-collapsed', JSON.stringify(isHistoryCollapsed));
  }, [isHistoryCollapsed]);

  // Close context menus when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      if (taskContextMenu) {
        setTaskContextMenu(null);
      }
      if (nodeContextMenu) {
        setNodeContextMenu(null);
      }
    };

    if (taskContextMenu || nodeContextMenu) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [taskContextMenu, nodeContextMenu]);

  // Handle task deletion
  const handleDeleteTask = async (taskId: number) => {
    if (!confirm('Are you sure you want to delete this task? This action cannot be undone.')) {
      return;
    }

    try {
      await apiClient.deleteTask(taskId);

      // Refresh task history
      await fetchTaskHistory();

      // Clear selected task if it was deleted
      if (selectedHistoryTask?.id === taskId) {
        setSelectedHistoryTask(null);
      }

      // Close replay panel if viewing deleted task
      if (replayTaskId === taskId) {
        setShowReplayPanel(false);
        setReplayTaskId(null);
      }

      setTaskContextMenu(null);
    } catch (error: any) {
      console.error('Failed to delete task:', error);
      alert(`Failed to delete task: ${error.response?.data?.detail || error.message}`);
    }
  };

  // Handle saving node as agent template to library
  const handleSaveToAgentLibrary = (nodeId: string, nodeData: NodeData) => {
    const suggestedName = `${nodeData.label} (Copy)`;
    setAgentLibraryName(suggestedName);
    setAgentLibraryDescription('');
    setSaveToLibraryData({ nodeId, nodeData });
    setShowSaveToLibraryModal(true);
    setNodeContextMenu(null);
  };

  const handleConfirmSaveToLibrary = async () => {
    if (!saveToLibraryData || !agentLibraryName.trim()) return;

    const { nodeId, nodeData } = saveToLibraryData;

    try {
      const agentTemplate = {
        name: agentLibraryName.trim(),
        description: agentLibraryDescription.trim() || 'Custom agent template',
        category: 'workflow',
        config: {
          model: nodeData.config.model,
          temperature: nodeData.config.temperature ?? 0.7,
          max_tokens: nodeData.config.max_tokens || 4000,
          system_prompt: nodeData.config.system_prompt || '',
          tools: nodeData.config.tools || [],
          native_tools: nodeData.config.native_tools || [],
          cli_tools: nodeData.config.cli_tools || [],
          custom_tools: nodeData.config.custom_tools || [],
          middleware: [],
          subagents: [],
          backend: {
            type: 'state',
            config: {},
            mappings: null
          },
          guardrails: {
            interrupts: {},
            token_limits: {
              max_total_tokens: 100000,
              eviction_threshold: 80000,
              summarization_threshold: 60000
            },
            enable_auto_eviction: true,
            enable_summarization: true,
            long_term_memory: false
          }
        }
      };

      const response = await apiClient.createDeepAgent(agentTemplate);
      const savedAgentId = response.data?.id;

      // Update the node with the saved agent ID and new name
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id === nodeId) {
            return {
              ...node,
              data: {
                ...node.data,
                label: agentLibraryName.trim(),
                deepAgentId: savedAgentId,
                config: {
                  ...node.data.config,
                  deepAgentId: savedAgentId,
                }
              }
            };
          }
          return node;
        })
      );

      showSuccess(`Agent "${agentLibraryName}" saved to library!`);
      setShowSaveToLibraryModal(false);
      setSaveToLibraryData(null);
      setAgentLibraryName('');
      setAgentLibraryDescription('');
    } catch (error: any) {
      console.error('Failed to save agent to library:', error);
      logError('Failed to save agent', error.response?.data?.detail || error.message);
    }
  };

  // Handle duplicating a node
  const handleDuplicateNode = (nodeId: string, nodeData: NodeData) => {
    const sourceNode = nodes.find(n => n.id === nodeId);
    if (!sourceNode) return;

    const newNodeId = `node-${Date.now()}`;
    const newNode = {
      ...sourceNode,
      id: newNodeId,
      position: {
        x: sourceNode.position.x + 50,
        y: sourceNode.position.y + 50,
      },
      data: {
        ...sourceNode.data,
        label: `${sourceNode.data.label} (Copy)`,
      },
    };

    setNodes((nds) => [...nds, newNode]);
    setNodeContextMenu(null);
    showSuccess('Node duplicated successfully');
  };

  // Handle opening chat with agent
  const handleChatWithAgent = (nodeId: string, nodeData: NodeData) => {
    // Close context menu
    setNodeContextMenu(null);

    // Check if this node has a linked deep agent ID
    const deepAgentId = (nodeData as any).deepAgentId || (nodeData.config as any)?.deepAgentId;

    if (deepAgentId) {
      // Open chat with this specific agent
      openChat(deepAgentId);
    } else {
      // Show modal that this node needs to be saved to library first
      setShowChatWarningModal(true);
    }
  };

  // Handle deleting a node
  const handleDeleteNode = (nodeId: string) => {
    if (!confirm('Are you sure you want to delete this node?')) return;

    setNodes((nds) => nds.filter((n) => n.id !== nodeId));
    setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
    setNodeContextMenu(null);
    showSuccess('Node deleted');
  };

  // Handle opening node configuration
  const handleConfigureNode = (nodeId: string) => {
    const node = nodes.find(n => n.id === nodeId);
    if (node) {
      setSelectedNodeId(nodeId);
      setSelectedNodeData({
        id: nodeId,
        data: node.data,
        type: node.type || 'agentNode',
      });
    }
    setNodeContextMenu(null);
  };

  // Handle copying LangChain code for a node
  const handleCopyLangChainCode = async (nodeId: string, nodeData: NodeData) => {
    try {
      // Generate Python code for this specific agent node
      const pythonCode = `from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

# Agent: ${nodeData.label}
# Model: ${nodeData.config.model}
# Temperature: ${nodeData.config.temperature}

# Initialize the model
${nodeData.config.model.includes('claude')
          ? `model = ChatAnthropic(
    model="${nodeData.config.model}",
    temperature=${nodeData.config.temperature},
    max_tokens=${nodeData.config.max_tokens || 4000}
)`
          : `model = ChatOpenAI(
    model="${nodeData.config.model}",
    temperature=${nodeData.config.temperature},
    max_tokens=${nodeData.config.max_tokens || 4000}
)`}

# System prompt
system_prompt = """${nodeData.config.system_prompt || 'You are a helpful AI assistant.'}"""

# Create the agent with tools
${nodeData.config.native_tools && nodeData.config.native_tools.length > 0
          ? `# Native tools: ${nodeData.config.native_tools.join(', ')}
tools = []  # Add your tools here
agent = create_react_agent(model, tools, state_modifier=system_prompt)`
          : `agent = create_react_agent(model, [], state_modifier=system_prompt)`}

# Run the agent
if __name__ == "__main__":
    result = agent.invoke({
        "messages": [HumanMessage(content="Your query here")]
    })
    print(result["messages"][-1].content)
`;

      await navigator.clipboard.writeText(pythonCode);
      showSuccess('LangChain code copied to clipboard!');
      setNodeContextMenu(null);
    } catch (error: any) {
      console.error('Failed to copy code:', error);
      logError('Failed to copy code', error.message);
    }
  };

  const fetchTaskHistory = async () => {
    if (!currentWorkflowId) return;

    setLoadingHistory(true);
    try {
      const response = await apiClient.getWorkflowHistory(currentWorkflowId, 50, 0);
      const tasks = response.data.tasks || [];
      setTaskHistory(tasks);

      // Check if there's a running task and restore execution state
      const runningTask = tasks.find((task: any) =>
        task.status === 'running' || task.status === 'pending'
      );

      if (runningTask) {
        setCurrentTaskId(runningTask.id);
        setExecutionStatus({
          state: 'running',
          currentNode: undefined,
          progress: 0,
          startTime: runningTask.created_at,
          duration: undefined,
        });
        // Events will auto-load from historical data via useWorkflowStream
      }
    } catch (err) {
      console.error('Failed to fetch task history:', err);
    } finally {
      setLoadingHistory(false);
    }
  };

  // Fetch available documents for context
  useEffect(() => {
    const fetchDocuments = async () => {
      if (!activeProjectId) return;
      try {
        const projectId = typeof activeProjectId === 'string' ? parseInt(activeProjectId, 10) : activeProjectId;
        const response = await apiClient.listDocuments({ project_id: projectId });
        setAvailableDocuments(response.data || []);
      } catch (error) {
        console.error('Failed to fetch documents:', error);
      }
    };
    fetchDocuments();
  }, [activeProjectId]);

  // Fetch workflow list for dropdown
  const fetchWorkflows = async () => {
    try {
      const response = await apiClient.listWorkflows();
      setAvailableWorkflows(response.data || []); // Changed from setTaskHistory to setAvailableWorkflows
    } catch (error) {
      console.error('Failed to fetch workflows:', error);
    }
  };

  // Load workflow data
  // Fetch available workflows on mount
  useEffect(() => {
    fetchWorkflows();
  }, []);

  // Fetch workflow details and lock_version when workflowId changes
  useEffect(() => {
    const fetchWorkflowDetails = async () => {
      if (!currentWorkflowId) return;

      try {
        const response = await apiClient.getWorkflow(currentWorkflowId);
        const workflow = response.data;

        // Update lock_version for optimistic locking
        if (workflow.lock_version !== undefined) {
          setCurrentLockVersion(workflow.lock_version);
        }

        // Update workflow name if available
        if (workflow.name) {
          setWorkflowName(workflow.name);
          setEditedName(workflow.name);
        }
      } catch (error) {
        console.error('Failed to fetch workflow details:', error);
      }
    };

    fetchWorkflowDetails();
  }, [currentWorkflowId]);

  // Memoize tool and action extraction for results tab (OUTSIDE of JSX render)
  const toolsAndActions = useMemo(() => {
    const displayTask = selectedHistoryTask || taskHistory[0];
    const taskOutput = displayTask?.result;
    const tools: any[] = [];
    const actions: string[] = [];

    if (taskOutput?.agent_messages) {
      for (let i = 0; i < taskOutput.agent_messages.length; i++) {
        const msg = taskOutput.agent_messages[i];

        if (msg.tool_calls && Array.isArray(msg.tool_calls)) {
          msg.tool_calls.forEach((tc: any) => {
            const toolName = tc.function?.name || tc.name || 'unknown_tool';
            const toolArgs = tc.function?.arguments || tc.args || '{}';

            let toolResult = null;
            for (let j = i + 1; j < taskOutput.agent_messages.length; j++) {
              const nextMsg = taskOutput.agent_messages[j];
              if (nextMsg.role === 'tool' && nextMsg.name === toolName) {
                toolResult = nextMsg.content;
                break;
              }
            }

            tools.push({
              name: toolName,
              agent: msg.name || 'Agent',
              args: toolArgs,
              result: toolResult
            });
          });
        }

        if (taskOutput.agent_messages[i].role === 'ai' && taskOutput.agent_messages[i].content) {
          const msg = taskOutput.agent_messages[i];
          const content = typeof msg.content === 'string' ? msg.content : '';
          const cleanContent = content.replace(/<thinking>[\s\S]*?<\/thinking>/gi, '');

          const lowerContent = cleanContent.toLowerCase();
          if (lowerContent.includes('role definition') ||
            lowerContent.includes('agent framework') ||
            lowerContent.includes('react methodology') ||
            lowerContent.includes('instruction to complete')) {
            continue;
          }

          const lines = cleanContent.split('\n');
          lines.forEach((line: string) => {
            const trimmed = line.trim();
            const lowerLine = trimmed.toLowerCase();

            if (lowerLine.includes('role definition') ||
              lowerLine.includes('agent framework') ||
              lowerLine.includes('research findings') ||
              lowerLine.includes('source materials') ||
              lowerLine.includes('empty context')) {
              return;
            }

            if (trimmed.length > 15 && trimmed.length < 150 &&
              (trimmed.match(/^[-*•]\s+/) ||
                trimmed.match(/^\d+\.\s+/) ||
                trimmed.match(/^(Analyzed|Found|Created|Generated|Retrieved|Completed|Processed|Searched|Fetched|Identified|Discovered):/i))) {
              actions.push(trimmed.replace(/^[-*•\d.]+\s*/, '').substring(0, 100));
            }
          });
        }
      }
    }

    return { tools, actions, toolCount: tools.length, actionCount: actions.length };
  }, [taskHistory, selectedHistoryTask, expandedToolCalls]);

  // Memoize token cost calculation for results tab
  const tokenCostInfo = useMemo(() => {
    const displayTask = selectedHistoryTask || taskHistory[0];
    const taskOutput = displayTask?.result;

    // PRIORITY 1: Use workflow_summary from backend (most accurate, already calculated)
    if (taskOutput?.workflow_summary) {
      const summary = taskOutput.workflow_summary;
      if (summary.total_tokens > 0) {
        const costString = summary.total_cost_usd !== undefined
          ? `$${Number(summary.total_cost_usd).toFixed(4)}`
          : '$0.0000';
        return {
          totalTokens: summary.total_tokens,
          promptTokens: 0,
          completionTokens: 0,
          costString
        };
      }
    }

    // PRIORITY 2: Sum costs from per-node token costs (for live execution)
    const nodeCostValues = Object.values(nodeTokenCosts);
    if (nodeCostValues.length > 0) {
      let totalTokens = 0;
      let promptTokens = 0;
      let completionTokens = 0;
      let totalCostCents = 0;

      nodeCostValues.forEach(nodeCost => {
        totalTokens += nodeCost.totalTokens;
        promptTokens += nodeCost.promptTokens;
        completionTokens += nodeCost.completionTokens;

        const costMatch = nodeCost.costString.match(/\$(\d+\.?\d*)/);
        if (costMatch) {
          totalCostCents += Math.round(parseFloat(costMatch[1]) * 100);
        }
      });

      const costString = `$${(totalCostCents / 100).toFixed(4)}`;
      return { totalTokens, promptTokens, completionTokens, costString };
    }

    // Fallback for older workflows
    let totalTokens = 0;
    let promptTokens = 0;
    let completionTokens = 0;

    // Try to get tokens_used from task record first (if backend stored it)
    if (displayTask?.tokens_used) {
      totalTokens = displayTask.tokens_used;
    }
    // Fallback to token_usage in result
    else if (taskOutput?.token_usage) {
      totalTokens = taskOutput.token_usage.total_tokens || 0;
      promptTokens = taskOutput.token_usage.prompt_tokens || 0;
      completionTokens = taskOutput.token_usage.completion_tokens || 0;
    }

    // If not available, sum from all LLM events in workflowEvents with per-event model costs
    if (totalTokens === 0 && workflowEvents.length > 0) {
      let totalCostCents = 0;
      let hasModelInfo = false;

      workflowEvents.forEach(event => {
        if (event.type === 'on_llm_end') {
          let eventPrompt = 0;
          let eventCompletion = 0;

          if (event.data?.tokens_used) {
            const tokens = event.data.tokens_used;
            if (typeof tokens === 'number') {
              eventCompletion = tokens;  // Assume completion if just a number
            } else if (tokens.prompt_tokens || tokens.completion_tokens) {
              eventPrompt = tokens.prompt_tokens || 0;
              eventCompletion = tokens.completion_tokens || 0;
            }
          } else if (event.data?.prompt_tokens || event.data?.completion_tokens) {
            eventPrompt = event.data.prompt_tokens || 0;
            eventCompletion = event.data.completion_tokens || 0;
          }

          promptTokens += eventPrompt;
          completionTokens += eventCompletion;
          totalTokens += eventPrompt + eventCompletion;

          // Calculate cost for this event if model is available
          const modelName = event.data?.model || event.data?.model_name;
          if (modelName) {
            hasModelInfo = true;
            const eventCostString = calculateAndFormatCost(eventPrompt, eventCompletion, modelName);
            const costMatch = eventCostString.match(/\$(\d+\.?\d*)/);
            if (costMatch) {
              totalCostCents += Math.round(parseFloat(costMatch[1]) * 100);
            }
          }
        }
      });

      // If we calculated per-event costs, use that instead of single-model calculation
      if (hasModelInfo && totalCostCents > 0) {
        const costString = `$${(totalCostCents / 100).toFixed(4)}`;
        return { totalTokens, promptTokens, completionTokens, costString };
      }
    }

    // Final fallback: estimate from agent messages
    if (totalTokens === 0 && taskOutput?.agent_messages) {
      taskOutput.agent_messages.forEach((msg: any) => {
        if (msg.role === 'human' || msg.role === 'system') {
          const tokens = Math.ceil((msg.content?.length || 0) / 4);
          promptTokens += tokens;
        } else if (msg.role === 'ai') {
          const tokens = Math.ceil((msg.content?.length || 0) / 4);
          completionTokens += tokens;
        }
      });
      totalTokens = promptTokens + completionTokens;
    }

    const costString = calculateAndFormatCost(promptTokens, completionTokens, currentModelName);
    return { totalTokens, promptTokens, completionTokens, costString };
  }, [taskHistory, selectedHistoryTask, currentModelName, workflowEvents, nodeTokenCosts]);

  // Update parent component with token cost info
  // Notify parent of token cost updates
  useEffect(() => {
    if (onTokenCostUpdate && tokenCostInfo.totalTokens > 0) {
      onTokenCostUpdate(tokenCostInfo);
    }
  }, [tokenCostInfo, onTokenCostUpdate]);

  // Load workflow from localStorage on mount (only once)
  useEffect(() => {
    if (hasLoadedRef.current) return;
    hasLoadedRef.current = true;

    const savedWorkflow = localStorage.getItem('langconfig-workflow');
    if (savedWorkflow) {
      try {
        const { nodes: savedNodes, edges: savedEdges, counter, name, workflowId } = JSON.parse(savedWorkflow);
        let validatedNodes = []; // Declare outside the if block

        if (savedNodes && Array.isArray(savedNodes)) {
          // Validate and fix node positions with better defaults
          validatedNodes = savedNodes.map((node, index) => ({
            ...node,
            position: {
              x: typeof node.position?.x === 'number' && !isNaN(node.position.x)
                ? node.position.x
                : 250 + (index * 200), // Better horizontal spacing
              y: typeof node.position?.y === 'number' && !isNaN(node.position.y)
                ? node.position.y
                : 250
            },
            width: node.width || 200, // Ensure width is always set
            height: node.height || 100 // Ensure height is always set
          }));
          setNodes(validatedNodes);
        }

        if (savedEdges && Array.isArray(savedEdges) && validatedNodes.length > 0) {
          // Validate edges - only keep edges that reference existing nodes with valid positions
          const nodeIds = new Set(validatedNodes.map(n => n.id));
          const validatedEdges = savedEdges.filter(edge => {
            // Check if both source and target nodes exist
            if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
              console.warn('Removing edge with invalid node reference:', edge);
              return false;
            }
            return true;
          });
          setEdges(validatedEdges);
        }
        if (counter) {
          setNodeIdCounter(counter);
        }
        if (name) {
          setWorkflowName(name);
          setEditedName(name);
        }
        if (workflowId) {
          setCurrentWorkflowId(workflowId);
        }

        // Always fit view to show all nodes after loading (ignore saved viewport)
        setTimeout(() => {
          if (reactFlowInstance && savedNodes && savedNodes.length > 0) {
            reactFlowInstance.fitView({ padding: 0.5, duration: 400, maxZoom: 0.6 });
          }
        }, 150);
      } catch (error) {
        console.error('Failed to load saved workflow:', error);
      }
    }
  }, [setNodes, setEdges, reactFlowInstance]);

  // Create a stable reference for nodes without runtime executionStatus
  // This prevents execution status changes from triggering auto-save
  const nodesForSave = useMemo(() =>
    nodes.map(n => ({
      ...n,
      data: {
        ...n.data,
        executionStatus: undefined // Strip runtime-only execution status
      }
    })),
    [nodes]
  );

  // Detect if nodes changed (excluding executionStatus) for auto-save
  const nodesSaveKey = useMemo(() =>
    JSON.stringify(nodesForSave.map(n => ({
      id: n.id,
      position: n.position,
      data: {
        label: n.data.label,
        config: n.data.config
      }
    }))),
    [nodesForSave]
  );

  // Auto-save workflow to localStorage on changes (debounced)
  useEffect(() => {
    if (!hasLoadedRef.current) return; // Don't save until we've loaded
    if (isDraggingRef.current) return; // Don't save while dragging nodes

    const saveWorkflow = setTimeout(() => {
      const workflowData = {
        nodes: nodesForSave, // Use nodes without execution status
        edges,
        counter: nodeIdCounter,
        viewport: reactFlowInstance ? reactFlowInstance.getViewport() : null,
        name: workflowName,
        workflowId: currentWorkflowId
      };
      // Silently save to localStorage
      localStorage.setItem('langconfig-workflow', JSON.stringify(workflowData));
    }, 500); // Reduced debounce since we're not saving during drag

    return () => clearTimeout(saveWorkflow);
  }, [nodesSaveKey, edges, nodeIdCounter, reactFlowInstance, workflowName, currentWorkflowId]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Ctrl+S or Cmd+S - Quick save
      if ((event.ctrlKey || event.metaKey) && event.key === 's') {
        event.preventDefault();
        if (nodes.length > 0) {
          handleSave();
        }
      }

      // Escape - Deselect all
      if (event.key === 'Escape') {
        setNodes(nodes.map(node => ({ ...node, selected: false })));
        setEdges(edges.map(edge => ({ ...edge, selected: false })));
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [nodes, edges, setNodes, setEdges]);

  const onConnect = useCallback(
    (params: Connection) => {
      // Add edge with enhanced styling using theme colors
      const primaryColor = getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim();
      const newEdge = {
        ...params,
        type: 'smoothstep',
        animated: false, // Don't animate by default
        style: {
          stroke: primaryColor || '#6366f1',
          strokeWidth: 2.5,
        },
        markerEnd: {
          type: 'arrowclosed' as const,
          color: primaryColor || '#6366f1',
        },
      };
      setEdges((eds) => addEdge(newEdge, eds));
    },
    [setEdges]
  );

  // Handle node drag start - prevent auto-save during drag
  const onNodeDragStart = useCallback(() => {
    isDraggingRef.current = true;
  }, []);

  // Handle node drag stop - save workflow after drag completes
  const onNodeDragStop = useCallback(() => {
    isDraggingRef.current = false;

    // Validate and fix node positions before saving
    setNodes((currentNodes) =>
      currentNodes.map((node) => {
        const validation = validateNodePosition(node.position.x, node.position.y);
        if (!validation.isValid) {
          console.warn(`Invalid node position for ${node.id}: ${validation.error}. Resetting to (250, 250)`);
          return {
            ...node,
            position: { x: 250, y: 250 },
          };
        }
        return node;
      })
    );

    // Defer save to avoid blocking mouseup handler (causes violations)
    // Use setTimeout to push the work to the next event loop tick
    setTimeout(() => {
      // Strip execution status (runtime-only data) before saving
      const cleanNodes = nodes.map(n => ({
        ...n,
        data: {
          ...n.data,
          executionStatus: undefined
        }
      }));

      const workflowData = {
        nodes: cleanNodes,
        edges,
        counter: nodeIdCounter,
        viewport: reactFlowInstance ? reactFlowInstance.getViewport() : null,
        name: workflowName,
        workflowId: currentWorkflowId
      };
      localStorage.setItem('langconfig-workflow', JSON.stringify(workflowData));
    }, 0);
  }, [nodes, edges, nodeIdCounter, reactFlowInstance, workflowName, currentWorkflowId, setNodes]);

  // Add selected agent as a new node
  useEffect(() => {
    if (selectedAgent) {
      // Smart positioning: place near existing nodes or centered
      let newPosition = { x: 250, y: 250 };

      if (nodes.length > 0) {
        // Find the rightmost node with valid position
        const validNodes = nodes.filter(n =>
          typeof n.position?.x === 'number' &&
          typeof n.position?.y === 'number' &&
          !isNaN(n.position.x) &&
          !isNaN(n.position.y)
        );

        if (validNodes.length > 0) {
          const rightmostNode = validNodes.reduce((max, node) =>
            node.position.x > max.position.x ? node : max
            , validNodes[0]);

          newPosition = {
            x: rightmostNode.position.x + 350, // 350px to the right
            y: rightmostNode.position.y, // Same vertical position
          };
        } else {
          // Fallback if no nodes have valid positions
          newPosition = { x: 250, y: 250 };
        }
      } else if (reactFlowInstance) {
        // If first node, place it in the center of the viewport
        const viewport = reactFlowInstance.getViewport();
        // Validate viewport values to prevent NaN coordinates
        const viewportX = typeof viewport?.x === 'number' && !isNaN(viewport.x) ? viewport.x : 0;
        const viewportY = typeof viewport?.y === 'number' && !isNaN(viewport.y) ? viewport.y : 0;
        const viewportZoom = typeof viewport?.zoom === 'number' && !isNaN(viewport.zoom) && viewport.zoom > 0 ? viewport.zoom : 1;

        const centerX = (window.innerWidth / 2 - viewportX) / viewportZoom;
        const centerY = (window.innerHeight / 2 - viewportY) / viewportZoom;

        // Final validation: ensure calculated values are valid numbers
        const finalX = typeof centerX === 'number' && !isNaN(centerX) ? centerX - 100 : 250;
        const finalY = typeof centerY === 'number' && !isNaN(centerY) ? centerY - 50 : 250;

        newPosition = { x: finalX, y: finalY };
      }

      // Validate the calculated position
      const positionValidation = validateNodePosition(newPosition.x, newPosition.y);
      if (!positionValidation.isValid) {
        console.warn(`Invalid new node position: ${positionValidation.error}. Using default (250, 250)`);
        newPosition = { x: 250, y: 250 };
      }

      const newNode: Node = {
        id: `node-${nodeIdCounter}`,
        type: 'custom',
        position: newPosition,
        data: {
          label: selectedAgent.name,
          agentType: selectedAgent.id,
          model: selectedAgent.model,
          // Add full agent config as expected by backend (simple_executor.py line 178)
          config: {
            model: selectedAgent.model,
            fallback_models: selectedAgent.fallback_models || [],
            temperature: selectedAgent.temperature,
            max_tokens: selectedAgent.max_tokens,
            system_prompt: selectedAgent.system_prompt,
            // Built-in tools
            native_tools: selectedAgent.native_tools || [],
            tools: [], // legacy
            cli_tools: selectedAgent.cli_tools || [],
            custom_tools: selectedAgent.custom_tools || [],  // User-created custom tools
            timeout_seconds: selectedAgent.timeout_seconds,
            max_retries: selectedAgent.max_retries,
            enable_model_routing: selectedAgent.enable_model_routing,
            enable_parallel_tools: selectedAgent.enable_parallel_tools,
            enable_memory: selectedAgent.enable_memory,
            enable_rag: selectedAgent.enable_rag || false,
            requires_human_approval: selectedAgent.requires_human_approval || false,
            // DeepAgent configuration
            use_deepagents: (selectedAgent as any).use_deepagents || false,
            subagents: (selectedAgent as any).subagents || [],
            // Tool Node configuration (instance-specific)
            tool_type: null,
            tool_id: null,
            tool_params: {}
          },
        },
      };

      setNodes((nds) => {
        return [...nds, newNode];
      });
      setNodeIdCounter(nodeIdCounter + 1);

      // Auto fit view to show all nodes after adding
      setTimeout(() => {
        if (reactFlowInstance) {
          reactFlowInstance.fitView({ padding: 0.2, duration: 400, maxZoom: 1.2 });
        }
      }, 100);

      // Notify parent that agent was added so it can clear the selection
      if (onAgentAdded) {
        onAgentAdded();
      }
    }
    // Only react to selectedAgent changes, not nodes changes to avoid re-running when we add a node
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAgent, onAgentAdded, reactFlowInstance, nodeIdCounter]);

  // Insert workflow recipe as a set of connected nodes and edges
  useEffect(() => {
    if (selectedRecipe) {
      console.log('[WorkflowCanvas] Inserting recipe:', selectedRecipe.name);

      // Calculate offset based on existing nodes to avoid overlap
      let offsetX = 0;
      let offsetY = 0;

      if (nodes.length > 0) {
        // Find the rightmost and lowest positions of existing nodes
        const validNodes = nodes.filter(n =>
          typeof n.position?.x === 'number' &&
          typeof n.position?.y === 'number' &&
          !isNaN(n.position.x) &&
          !isNaN(n.position.y)
        );

        if (validNodes.length > 0) {
          const maxX = Math.max(...validNodes.map(n => n.position.x));
          const maxY = Math.max(...validNodes.map(n => n.position.y));
          // Place recipe below and slightly to the right of existing content
          offsetX = 0; // Start at same X but offset Y
          offsetY = maxY + 250; // 250px gap below existing nodes
        }
      }

      // Create unique IDs for recipe nodes using current counter
      const idMap: Record<string, string> = {};
      let newCounter = nodeIdCounter;

      // Map old IDs to new unique IDs
      selectedRecipe.nodes.forEach((recipeNode: any) => {
        const newId = `node-${newCounter}`;
        idMap[recipeNode.id] = newId;
        newCounter++;
      });

      // Create new nodes with updated positions and IDs
      const newNodes: Node[] = selectedRecipe.nodes.map((recipeNode: any) => ({
        ...recipeNode,
        id: idMap[recipeNode.id],
        position: {
          x: recipeNode.position.x + offsetX,
          y: recipeNode.position.y + offsetY,
        },
      }));

      // Get primary color for edges
      const primaryColor = getComputedStyle(document.documentElement).getPropertyValue('--color-primary').trim() || '#6366f1';

      // Create new edges with updated source/target IDs and unique edge IDs
      const newEdges: Edge[] = selectedRecipe.edges.map((recipeEdge: any, idx: number) => ({
        ...recipeEdge,
        id: `recipe-edge-${nodeIdCounter}-${idx}`,
        source: idMap[recipeEdge.source] || recipeEdge.source,
        target: idMap[recipeEdge.target] || recipeEdge.target,
        type: recipeEdge.type || 'smoothstep',
        animated: false,
        style: {
          stroke: primaryColor,
          strokeWidth: 2.5,
        },
        markerEnd: {
          type: 'arrowclosed' as const,
          color: primaryColor,
        },
      }));

      // Add nodes and edges to canvas
      setNodes((nds) => [...nds, ...newNodes]);
      setEdges((eds) => [...eds, ...newEdges]);
      setNodeIdCounter(newCounter);

      // Auto fit view to show all nodes after adding
      setTimeout(() => {
        if (reactFlowInstance) {
          reactFlowInstance.fitView({ padding: 0.2, duration: 400, maxZoom: 1.2 });
        }
      }, 100);

      // Notify parent that recipe was inserted
      if (onRecipeInserted) {
        onRecipeInserted();
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRecipe, onRecipeInserted, reactFlowInstance, nodeIdCounter]);

  // Handle node selection
  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      if (onNodeSelect) {
        onNodeSelect(node.id, node.data as NodeData);
      }
    },
    [onNodeSelect]
  );

  // Handle node deletion
  const handleNodeDelete = useCallback((nodeId: string) => {
    setNodes((nds) => nds.filter((node) => node.id !== nodeId));
    setEdges((eds) => eds.filter((edge) => edge.source !== nodeId && edge.target !== nodeId));

    // Notify parent if callback provided
    if (onNodeDelete) {
      onNodeDelete(nodeId);
    }
  }, [onNodeDelete, setNodes, setEdges]);

  // Update node config function (exposed via ref)
  const updateNodeConfig = useCallback((nodeId: string, newConfig: any) => {
    console.log(`[WorkflowCanvas] updateNodeConfig called for node ${nodeId}:`, {
      native_tools: newConfig.native_tools,
      custom_tools: newConfig.custom_tools
    });

    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === nodeId) {
          const oldLabel = node.data.label;
          const newLabel = newConfig.label || newConfig.name || oldLabel;

          // If label changed, transfer token costs to new label
          if (newLabel !== oldLabel && oldLabel) {
            setNodeTokenCosts(prev => {
              const tokenCost = prev[oldLabel];
              if (tokenCost) {
                const updated = { ...prev };
                delete updated[oldLabel];
                updated[newLabel] = tokenCost;
                return updated;
              }
              return prev;
            });
          }

          // Create a completely new node object to force React Flow to detect the change
          return {
            ...node,
            // Force re-render by creating new data object
            data: {
              ...node.data,
              label: newLabel,
              agentType: newConfig.agentType || node.data.agentType,
              model: newConfig.model || node.data.model, // Update top-level model
              config: {
                ...node.data.config,
                ...newConfig,
                model: newConfig.model || node.data.config?.model, // Ensure model is in config too
                temperature: newConfig.temperature !== undefined ? newConfig.temperature : node.data.config?.temperature,
                max_tokens: newConfig.max_tokens !== undefined ? newConfig.max_tokens : node.data.config?.max_tokens,
                max_retries: newConfig.max_retries !== undefined ? newConfig.max_retries : node.data.config?.max_retries,
                recursion_limit: newConfig.recursion_limit !== undefined ? newConfig.recursion_limit : node.data.config?.recursion_limit,
                system_prompt: newConfig.system_prompt !== undefined ? newConfig.system_prompt : node.data.config?.system_prompt,
                // Explicitly update tools arrays to ensure reactivity
                native_tools: newConfig.native_tools !== undefined ? newConfig.native_tools : node.data.config?.native_tools,
                tools: newConfig.tools !== undefined ? newConfig.tools : node.data.config?.tools,
                custom_tools: newConfig.custom_tools !== undefined ? newConfig.custom_tools : node.data.config?.custom_tools,
                enable_memory: newConfig.enable_memory !== undefined ? newConfig.enable_memory : node.data.config?.enable_memory,
                enable_rag: newConfig.enable_rag !== undefined ? newConfig.enable_rag : node.data.config?.enable_rag,
              },
              // Add a timestamp to ensure React Flow sees this as a new object
              _lastUpdated: Date.now()
            }
          };
        }
        return node;
      })
    );
  }, [setNodes, setNodeTokenCosts]);

  // Memoized event handlers to prevent unnecessary re-renders
  const handleToggleWorkflowDropdown = useCallback(() => {
    setShowWorkflowDropdown(prev => !prev);
  }, []);

  const handleCloseWorkflowDropdown = useCallback(() => {
    setShowWorkflowDropdown(false);
  }, []);

  const handleToggleSettingsModal = useCallback(() => {
    setShowSettingsModal(prev => !prev);
  }, []);

  const handleCloseSettingsModal = useCallback(() => {
    setShowSettingsModal(false);
  }, []);

  const handleToggleThinkingStream = useCallback(() => {
    setShowThinkingStream(prev => !prev);
  }, []);

  const handleToggleLiveExecutionPanel = useCallback(() => {
    setShowLiveExecutionPanel(prev => !prev);
  }, []);

  const handleToggleCheckpointer = useCallback(() => {
    setCheckpointerEnabled(prev => !prev);
  }, []);

  const handleWorkflowSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setWorkflowSearchQuery(e.target.value);
  }, []);

  const handleStartEditingName = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setIsEditingName(true);
  }, []);

  // Load available documents when dialog opens
  useEffect(() => {
    if (showExecutionDialog && activeProjectId) {
      // Fetch documents from Knowledge Base using API client
      apiClient.listDocuments({ project_id: activeProjectId })
        .then(response => {
          setAvailableDocuments(response.data || []);
        })
        .catch(error => {
          console.error('Failed to load documents:', error);
          setAvailableDocuments([]);
        });
    }
  }, [showExecutionDialog, activeProjectId]);

  // Handle Escape key to close dialog
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && showExecutionDialog) {
        setShowExecutionDialog(false);
      }
    };

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [showExecutionDialog]);

  const handleRun = async () => {
    if (nodes.length === 0) {
      showWarning('Please add at least one agent to the workflow before running.');
      return;
    }

    // Check if workflow is already running
    if (executionStatus.state === 'running') {
      const shouldCancel = window.confirm(
        'A workflow is already running. Do you want to cancel it and start a new execution?'
      );

      if (shouldCancel) {
        await handleStop();
        // Wait a moment for cleanup
        await new Promise(resolve => setTimeout(resolve, 500));
      } else {
        return; // User chose to wait
      }
    }

    // Show execution dialog immediately - we'll validate on execution
    setShowExecutionDialog(true);
  };

  const handleStop = async () => {
    if (!currentTaskId) {
      showWarning('No running workflow to stop.');
      return;
    }

    try {
      await apiClient.cancelTask(currentTaskId);

      // CRITICAL: Clear the task ID so events stop coming
      setCurrentTaskId(null);
      localStorage.removeItem('langconfig-current-task-id');

      // DON'T clear events - keep them visible for debugging
      // clearEvents(); // Removed to allow debugging of stopped workflows

      // Update execution status to stopped
      setExecutionStatus({
        state: 'idle',
        currentNode: '',
        progress: 0,
        startTime: '',
        duration: '0s',
      });

      // Force clear all node statuses
      setNodes((nds) =>
        nds.map((node) => ({
          ...node,
          data: {
            ...node.data,
            executionStatus: {
              state: 'idle',
              thinking: '',
              thinkingPreview: '',
            },
          },
        }))
      );
    } catch (error: any) {
      console.error('Failed to cancel workflow:', error);
      logError('Failed to cancel workflow', error.response?.data?.detail || error.message);
    }
  };

  const executeWorkflow = async () => {
    setShowExecutionDialog(false);

    // Find the START node or the first node with no incoming edges
    const startNode = nodes.find(n => n.data.agentType === 'START_NODE') ||
      nodes.find(n => !edges.some(e => e.target === n.id)) ||
      nodes[0];

    setExecutionStatus({
      state: 'running',
      currentNode: startNode?.data.label,
      progress: 0,
      startTime: new Date().toLocaleTimeString(),
      duration: '0s',
    });

    if (onExecutionStart) {
      onExecutionStart();
    }

    try {
      // Make sure we have a workflow ID - always save/update before executing
      let workflowIdToExecute = currentWorkflowId;

      const configuration = {
        nodes: nodes.map(n => ({
          id: n.id,
          type: n.data.label.toLowerCase().replace(/\s+/g, '_'),
          config: {
            model: n.data.config?.model || 'gpt-4o-mini',
            temperature: n.data.config?.temperature ?? 0.7,
            system_prompt: n.data.config?.system_prompt || '',
            // Legacy tools field
            tools: n.data.config?.tools || [],
            // CRITICAL: Propagate native_tools and custom_tools for agent factory
            native_tools: n.data.config?.native_tools || [],
            cli_tools: n.data.config?.cli_tools || [],
            custom_tools: n.data.config?.custom_tools || [],
            enable_model_routing: n.data.config?.enable_model_routing ?? false,
            enable_parallel_tools: n.data.config?.enable_parallel_tools ?? true,
            enable_memory: n.data.config?.enable_memory ?? false,
            enable_rag: n.data.config?.enable_rag ?? false,
            // Ensure recursion limit is passed if set
            recursion_limit: n.data.config?.recursion_limit,
            // Pass pause settings
            pauseBefore: n.data.config?.pauseBefore ?? false,
            pauseAfter: n.data.config?.pauseAfter ?? false,
            // DeepAgent support: pass use_deepagents flag and subagent configs
            use_deepagents: n.data.config?.use_deepagents ?? false,
            subagents: n.data.config?.subagents || []
          }
        })),
        edges: edges.map(e => ({
          source: e.source,
          target: e.target
        }))
      };

      if (workflowIdToExecute) {
        // UPDATE existing workflow
        await apiClient.updateWorkflow(workflowIdToExecute, {
          configuration
        });
      } else {
        // CREATE new workflow
        const workflowData = {
          name: `Workflow ${Date.now()}`,
          configuration
        };

        const saveResponse = await apiClient.createWorkflow(workflowData);
        workflowIdToExecute = saveResponse.data.id;
        setCurrentWorkflowId(workflowIdToExecute);
      }

      // Clear previous execution events to prepare for new run
      // SSE connection stays alive across executions
      clearEvents();

      // Execute workflow with user-provided context
      const response = await apiClient.executeWorkflow({
        workflow_id: workflowIdToExecute as number,
        project_id: activeProjectId || 0, // Use active project if available, 0 for standalone
        input_data: {
          query: executionConfig.directive,
          task: executionConfig.task || executionConfig.directive,
          additional_context: additionalContext || '',
          checkpointer_enabled: checkpointerEnabled,
          recursion_limit: globalRecursionLimit
        },
        context_documents: contextDocuments,
      });

      // Save task ID for monitoring and persist to localStorage
      setCurrentTaskId(response.data.task_id);
      localStorage.setItem('langconfig-current-task-id', response.data.task_id.toString());

      // Set execution to running state
      setExecutionStatus(prev => ({
        ...prev,
        state: 'running',
        startTime: new Date().toISOString(),
      }));

      // Auto-open live execution panel when workflow runs
      setShowLiveExecutionPanel(true);

      // Close node config panel by deselecting all nodes
      onNodeSelect?.(null, null);

    } catch (error: any) {
      console.error('Workflow execution error:', error);

      // Extract detailed error information
      let errorMessage = 'Unknown error';
      let errorDetails = '';

      if (error.response?.data) {
        // API error response
        const errData = error.response.data;
        errorMessage = errData.detail || errData.message || 'Execution failed';
        if (errData.error) errorDetails = errData.error;
        if (errData.traceback) errorDetails += `\n\nTraceback:\n${errData.traceback}`;
      } else if (error.message) {
        errorMessage = error.message;
      }

      setExecutionStatus(prev => ({
        ...prev,
        state: 'failed',
      }));

      // DISABLED: Don't show error notification - let user see output
      // logError('Workflow execution failed!', `${errorMessage}${errorDetails ? '\n\nCheck logs for details.' : ''}`);
    } finally {
      // Execution complete
    }
  };

  // Helper to generate a hash of the workflow state, excluding visual properties like position
  // This ensures that moving nodes doesn't trigger "unsaved changes"
  const getWorkflowStateHash = useCallback((nodes: Node[], edges: Edge[]) => {
    const sanitizedNodes = nodes.map(node => ({
      id: node.id,
      type: node.type,
      data: node.data,
      // Exclude position, selected, dragging, width, height, etc.
    }));

    const sanitizedEdges = edges.map(edge => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      // Exclude visual properties
    }));

    return JSON.stringify({ nodes: sanitizedNodes, edges: sanitizedEdges });
  }, []);

  const handleSave = useCallback(async (silent: boolean = false) => {
    if (nodes.length === 0) return;

    // Validate workflow before saving
    const validation = validateWorkflow(nodes, edges);

    if (!validation.isValid) {
      // Only show error popup if not silent mode
      if (!silent) {
        const errorMessages = validation.errors.map((e) => e.message).join('\n');
        logError('Cannot save workflow', errorMessages);
      }
      return;
    }

    // Show warnings if any (only in manual save, not auto-save)
    if (!silent && validation.warnings.length > 0) {
      const warningMessages = validation.warnings.map((w) => w.message).join('\n');
      const proceed = confirm(
        `Workflow has warnings:\n\n${warningMessages}\n\nDo you want to continue?`
      );
      if (!proceed) return;
    }

    // Extract configuration from nodes (declare outside try so it's accessible in catch)
    const configuration = {
      nodes: nodes.map(n => {
        // DEBUG: Log what we're sending to backend
        // Normalize tool fields from node data
        const nativeTools = n.data.config?.native_tools || n.data.config?.nativeTools || [];

        const nodeConfig = {
          model: n.data.config?.model || 'gpt-4o-mini',
          temperature: n.data.config?.temperature ?? 0.7,
          system_prompt: n.data.config?.system_prompt || '',
          // Deprecated fields kept for backward compatibility
          tools: n.data.config?.tools || [],
          // Source of truth for built-in tools
          native_tools: nativeTools,
          custom_tools: n.data.config?.custom_tools || [],
          // Flags can be explicit or inferred from native_tools selections
          enable_memory: (n.data.config?.enable_memory ?? nativeTools.includes('enable_memory')) || false,
          enable_rag: (n.data.config?.enable_rag ?? nativeTools.includes('enable_rag')) || false
        };

        // ADDED: Log tools for debugging
        console.log(`[WORKFLOW SAVE] Node ${n.id} (${n.data.label}):`, {
          native_tools: nodeConfig.native_tools,
          custom_tools: nodeConfig.custom_tools,
          raw_config: n.data.config
        });

        return {
          id: n.id,
          type: n.data.agentType || n.data.label.toLowerCase().replace(/\s+/g, '_'),
          data: n.data, // Save the full data object so we can restore it properly
          position: n.position,
          config: nodeConfig
        };
      }),
      edges: edges.map(e => ({
        source: e.source,
        target: e.target
      }))
    };

    try {
      if (currentWorkflowId) {
        // UPDATE existing workflow - Include lock_version for optimistic locking
        const response = await apiClient.updateWorkflow(currentWorkflowId, {
          configuration,
          lock_version: currentLockVersion  // Send lock_version
        });

        // Update lock_version from response
        const updatedWorkflow = response.data;
        if (updatedWorkflow.lock_version !== undefined) {
          setCurrentLockVersion(updatedWorkflow.lock_version);
        }

        // Mark as saved and update last saved state using the sanitized hash
        setHasUnsavedChanges(false);
        setLastSavedState(getWorkflowStateHash(nodes, edges));

        // Only show success message if not auto-save
        if (!silent) {
          showSuccess('Workflow saved successfully!');
        } else {
        }
      } else {
        // CREATE new workflow - show modal (only for manual saves)
        if (!silent) {
          setShowSaveModal(true);
        }
        return;
      }
    } catch (error: any) {
      console.error('Failed to save workflow:', error);

      // Handle optimistic lock conflicts
      if (error instanceof ConflictErrorClass) {

        // Only handle conflicts in manual saves (not auto-saves)
        if (!silent) {
          // Fetch latest version from server
          try {
            const latestResponse = await apiClient.getWorkflow(currentWorkflowId!);
            const remoteWorkflow = latestResponse.data;

            // Show conflict dialog
            setConflictData({
              localData: { configuration, lock_version: currentLockVersion },
              remoteData: remoteWorkflow
            });
            setShowConflictDialog(true);
          } catch (fetchError) {
            console.error('Failed to fetch latest version:', fetchError);
            logError('Conflict detected', 'Unable to fetch latest workflow version');
          }
        } else {
          // Auto-save conflict - silently skip
        }
        return;
      }

      // Only show error notification if not silent mode
      if (!silent) {
        logError('Save failed', 'Unable to save workflow changes');
      }
    }
  }, [nodes, edges, currentWorkflowId, currentLockVersion, showSuccess, logError, setShowSaveModal, getWorkflowStateHash]);

  // Handle conflict resolution
  const handleConflictResolve = useCallback(async (resolution: 'reload' | 'force' | 'cancel') => {
    if (!conflictData || !currentWorkflowId) return;

    if (resolution === 'reload') {
      // Reload latest version from server
      try {
        const response = await apiClient.getWorkflow(currentWorkflowId);
        const latestWorkflow = response.data;

        // Update lock_version
        if (latestWorkflow.lock_version !== undefined) {
          setCurrentLockVersion(latestWorkflow.lock_version);
        }

        // Update workflow name
        if (latestWorkflow.name) {
          setWorkflowName(latestWorkflow.name);
          setEditedName(latestWorkflow.name);
        }

        // Reload canvas with latest configuration
        if (latestWorkflow.configuration) {
          const config = latestWorkflow.configuration;

          // Restore nodes
          if (config.nodes) {
            const restoredNodes = config.nodes.map((n: any) => ({
              id: n.id,
              type: 'custom',
              position: n.position || { x: 0, y: 0 },
              data: n.data || {
                label: n.type,
                agentType: n.type,
                model: n.config?.model || 'gpt-4o-mini',
                config: n.config || {}
              }
            }));
            setNodes(restoredNodes);
          }

          // Restore edges
          if (config.edges) {
            const restoredEdges = config.edges.map((e: any) => ({
              id: `${e.source}-${e.target}`,
              source: e.source,
              target: e.target,
              type: 'smoothstep',
              animated: true
            }));
            setEdges(restoredEdges);
          }
        }

        setHasUnsavedChanges(false);
        showSuccess('Workflow reloaded with latest changes');
      } catch (error) {
        console.error('Failed to reload workflow:', error);
        logError('Failed to reload', 'Unable to fetch latest workflow');
      }
    } else if (resolution === 'force') {
      // Force save with latest lock_version
      try {
        const latestResponse = await apiClient.getWorkflow(currentWorkflowId);
        const latestWorkflow = latestResponse.data;

        // Use latest lock_version but keep local changes
        setCurrentLockVersion(latestWorkflow.lock_version);

        // Retry save with new lock_version
        await handleSave(false);

        showSuccess('Workflow force-saved successfully');
      } catch (error) {
        console.error('Failed to force save:', error);
        logError('Force save failed', 'Unable to save workflow');
      }
    }
    // 'cancel' - just close dialog, do nothing

    setShowConflictDialog(false);
    setConflictData(null);
  }, [conflictData, currentWorkflowId, currentLockVersion, setNodes, setEdges, showSuccess, logError, handleSave]);

  // Track changes to nodes/edges to detect unsaved changes
  useEffect(() => {
    if (nodes.length === 0 && edges.length === 0) {
      // Empty workflow, no need to track
      return;
    }

    const currentState = getWorkflowStateHash(nodes, edges);

    if (lastSavedState && currentState !== lastSavedState) {
      setHasUnsavedChanges(true);
    } else if (!lastSavedState) {
      // First load, save the initial state
      setLastSavedState(currentState);
    }
  }, [nodes, edges, lastSavedState, getWorkflowStateHash]);

  // Warn user before leaving page with unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
        return e.returnValue;
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [hasUnsavedChanges]);

  // Clear canvas for new workflow
  const clearCanvas = useCallback(() => {
    setNodes([]);
    setEdges([]);
    setCurrentWorkflowId(null);
    setWorkflowName('Untitled Workflow');
    setExecutionStatus({
      state: 'idle',
      currentNode: '',
      progress: 0,
      startTime: '',
      duration: '0s',
    });
    setCurrentTaskId(null);
    setTaskHistory([]);
    setSelectedHistoryTask(null);
    localStorage.removeItem('langconfig-workflow-id');
    localStorage.removeItem('langconfig-current-task-id');
  }, [setNodes, setEdges]);

  // Expose methods to parent component via ref
  useImperativeHandle(ref, () => ({
    updateNodeConfig,
    deleteNode: handleNodeDelete,
    saveWorkflow: handleSave,
    hasUnsavedChanges: () => hasUnsavedChanges,
    clearCanvas
  }), [updateNodeConfig, handleNodeDelete, handleSave, hasUnsavedChanges, clearCanvas]);

  // ADDED: Debug workflow function
  const handleDebugWorkflow = useCallback(async () => {
    if (!currentWorkflowId) {
      showWarning('No workflow loaded');
      return;
    }

    try {
      const response = await apiClient.debugWorkflow(currentWorkflowId);
      setDebugData(response.data);
      setShowDebugModal(true);
    } catch (error) {
      console.error('Failed to fetch debug info:', error);
      logError('Debug failed', 'Unable to fetch workflow debug info');
    }
  }, [currentWorkflowId, showWarning, logError]);

  const handleSaveWorkflowConfirm = async () => {
    if (!saveWorkflowName.trim()) return;

    try {
      const configuration = {
        nodes: nodes.map(n => {
          const nativeTools = n.data.config?.native_tools || n.data.config?.nativeTools || [];
          const normalizedConfig = {
            ...n.data.config,
            native_tools: nativeTools,
            enable_memory: (n.data.config?.enable_memory ?? nativeTools.includes('enable_memory')) || false,
            enable_rag: (n.data.config?.enable_rag ?? nativeTools.includes('enable_rag')) || false,
          };
          return {
            id: n.id,
            type: n.data.agentType || 'default',
            data: n.data, // Save the full data object so we can restore it properly
            config: normalizedConfig,
            position: n.position
          };
        }),
        edges: edges.map(e => ({
          source: e.source,
          target: e.target
        }))
      };

      const response = await apiClient.createWorkflow({
        name: saveWorkflowName,
        configuration
      });

      setCurrentWorkflowId(response.data.id);
      setWorkflowName(saveWorkflowName); // Update the workflow name display
      setShowSaveModal(false);
      setSaveWorkflowName('');

      // Show success notification
      showSuccess('Workflow saved successfully!');
    } catch (error: any) {
      console.error('Failed to save workflow:', error);
      logError('Failed to save workflow', error.response?.data?.detail || error.message);
    }
  };

  // Version Management Functions
  const loadVersions = async (workflowId: number) => {
    setLoadingVersions(true);
    try {
      const response = await apiClient.getWorkflowVersions(workflowId);
      setVersions(response.data);

      // Find and set the current version
      const current = response.data.find((v: any) => v.is_current);
      if (current) {
        setCurrentVersion(current);
      }
    } catch (error) {
      console.error('Failed to load versions:', error);
    } finally {
      setLoadingVersions(false);
    }
  };

  const handleSaveVersion = async () => {
    if (!currentWorkflowId) {
      showWarning('Please save the workflow first');
      return;
    }

    setShowVersionModal(true);
  };

  const handleSaveVersionConfirm = async () => {
    if (!currentWorkflowId) return;

    try {
      const configuration = {
        nodes: nodes.map(n => {
          const nativeTools = n.data.config?.native_tools || n.data.config?.nativeTools || [];
          const normalizedConfig = {
            ...n.data.config,
            native_tools: nativeTools,
            enable_memory: (n.data.config?.enable_memory ?? nativeTools.includes('enable_memory')) || false,
            enable_rag: (n.data.config?.enable_rag ?? nativeTools.includes('enable_rag')) || false,
          };
          return {
            id: n.id,
            type: n.data.agentType || n.data.label.toLowerCase().replace(/\s+/g, '_'),
            data: n.data,
            position: n.position,
            config: normalizedConfig
          };
        }),
        edges: edges.map(e => ({
          source: e.source,
          target: e.target
        }))
      };

      const response = await apiClient.createWorkflowVersion(currentWorkflowId, {
        config_snapshot: configuration,
        notes: versionNotes || 'Manual save',
        created_by: 'user' // Default for local mode
      });

      setShowVersionModal(false);
      setVersionNotes('');

      // Reload versions
      await loadVersions(currentWorkflowId);

      showSuccess(`Version ${response.data.version_number} created successfully!`);
    } catch (error) {
      console.error('Failed to create version:', error);
      logError('Failed to create version. Please try again.');
    }
  };

  const handleLoadVersion = async (versionId: number) => {
    if (!currentWorkflowId) return;

    try {
      const response = await apiClient.getWorkflowVersion(currentWorkflowId, versionId);
      const versionData = response.data;

      // Load the configuration from this version
      const config = versionData.config_snapshot;

      if (config.nodes && config.edges) {
        // Restore nodes with validated positions
        const restoredNodes = config.nodes.map((n: any, index: number) => {
          // Validate position to prevent NaN coordinates
          let validPosition = { x: 250 + (index * 200), y: 250 }; // Default position with spacing

          if (n.position && typeof n.position.x === 'number' && typeof n.position.y === 'number') {
            if (!isNaN(n.position.x) && !isNaN(n.position.y)) {
              validPosition = { x: n.position.x, y: n.position.y };
            }
          }

          return {
            id: n.id,
            type: 'custom',
            position: validPosition,
            data: n.data || {
              label: n.type,
              agentType: n.type,
              config: n.config || {}
            }
          };
        });

        // Restore edges
        const restoredEdges = config.edges.map((e: any) => ({
          id: `e${e.source}-${e.target}`,
          source: e.source,
          target: e.target,
          type: 'smoothstep',
          animated: true
        }));

        setNodes(restoredNodes);
        setEdges(restoredEdges);
        setCurrentVersion(versionData);
        setShowVersionDropdown(false);

        showSuccess(`Loaded Version ${versionData.version_number}`);
      }
    } catch (error) {
      console.error('Failed to load version:', error);
      logError('Failed to load version. Please try again.');
    }
  };

  // Load versions when workflow changes
  useEffect(() => {
    if (currentWorkflowId) {
      loadVersions(currentWorkflowId);
    }
  }, [currentWorkflowId]);

  const handleCompareVersions = async () => {
    if (!compareVersion1 || !compareVersion2 || !currentWorkflowId) {
      showWarning('Please select two versions to compare');
      return;
    }

    setLoadingComparison(true);
    try {
      const response = await apiClient.compareWorkflowVersions(
        currentWorkflowId,
        compareVersion1.version_number,
        compareVersion2.version_number
      );
      setVersionComparison(response.data);
      setCompareMode(true);
    } catch (error) {
      console.error('Failed to compare versions:', error);
      logError('Failed to compare versions. Please try again.');
    } finally {
      setLoadingComparison(false);
    }
  };

  const handleClear = () => {
    const confirmed = confirm('Are you sure you want to clear the entire workflow? This cannot be undone.');
    if (!confirmed) return;

    setNodes([]);
    setEdges([]);
    setNodeIdCounter(1);
    localStorage.removeItem('langconfig-workflow');
  };

  const handleWorkflowNameSave = async () => {
    if (!editedName.trim()) {
      setIsEditingName(false);
      return;
    }

    const newName = editedName.trim();
    setWorkflowName(newName);
    setIsEditingName(false);

    // Save to backend if we have a workflow ID
    if (currentWorkflowId) {
      try {
        await apiClient.updateWorkflow(currentWorkflowId, {
          name: newName
        });
      } catch (error) {
        console.error('Failed to update workflow name:', error);
        // Optionally show error to user
        alert('Failed to update workflow name. Please try again.');
      }
    }
  };

  const handleWorkflowSwitch = async (workflowId: number) => {
    try {
      const response = await apiClient.getWorkflow(workflowId);
      const workflow = response.data;

      // Load workflow into canvas
      // Backend stores data in 'configuration' field, which may contain nodes/edges
      const config = workflow.configuration || workflow.graph;
      if (config && config.nodes) {
        // Validate and fix node positions and ensure type is set to 'custom'
        const validatedNodes = config.nodes.map((node: any, index: number) => {
          // Backend saves nodes with: id, type (from agentType), config, position
          // Frontend needs: id, type='custom', data={label, agentType, model, config}, position

          // If node already has data field (from a previous save), use it
          // Otherwise, reconstruct it from the saved type and config
          const nodeData = node.data || {
            label: node.type ? node.type.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase()) : `Node ${node.id}`,
            agentType: node.type || 'default',
            model: node.config?.model || 'gpt-4o-mini',
            config: node.config || {}
          };

          return {
            ...node,
            type: 'custom', // React Flow node type (always 'custom' for our CustomNode component)
            data: nodeData,
            position: {
              x: typeof node.position?.x === 'number' && !isNaN(node.position.x)
                ? node.position.x
                : 250 + (index * 200),
              y: typeof node.position?.y === 'number' && !isNaN(node.position.y)
                ? node.position.y
                : 250
            },
            width: node.width || 200, // Ensure width is always set
            height: node.height || 100 // Ensure height is always set
          };
        });
        setNodes(validatedNodes);
        setEdges(config.edges || []);
        setWorkflowName(workflow.name || 'Untitled Workflow');
        setEditedName(workflow.name || 'Untitled Workflow');
        setCurrentWorkflowId(workflowId);
        // Clear task ID when switching workflows to get fresh events
        setCurrentTaskId(null);
        localStorage.removeItem('langconfig-current-task-id');
      }

      setShowWorkflowDropdown(false);
      setWorkflowSearchQuery('');
    } catch (error) {
      console.error('Failed to load workflow:', error);
      alert('Failed to switch workflow. Please try again.');
    }
  };

  const filteredWorkflows = availableWorkflows.filter(wf =>
    wf.name.toLowerCase().includes(workflowSearchQuery.toLowerCase())
  );

  const getWorkflowStatus = (): 'draft' | 'saved' | 'running' | 'completed' | 'failed' => {
    if (executionStatus.state === 'running') return 'running';
    if (executionStatus.state === 'completed') return 'completed';
    if (executionStatus.state === 'failed') return 'failed';
    return currentWorkflowId ? 'saved' : 'draft';
  };

  const statusConfig = {
    draft: { color: 'yellow', label: 'Draft' },
    saved: { color: 'blue', label: 'Saved' },
    running: { color: 'green', label: 'Running' },
    completed: { color: 'green', label: 'Completed' },
    failed: { color: 'red', label: 'Failed' }
  };

  // Handler to open node context menu
  const openNodeContextMenu = useCallback((nodeId: string, nodeData: NodeData, x: number, y: number) => {
    setNodeContextMenu({ nodeId, nodeData, x, y });
  }, []);

  return (
    <WorkflowCanvasContext.Provider value={{ updateNodeConfig, openNodeContextMenu }}>
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Workflow Toolbar */}
        {nodes.length > 0 && (
          <div className="bg-white dark:bg-panel-dark border-b border-gray-200 dark:border-border-dark px-4 py-2.5">
            <div className="flex items-center gap-4">
              {/* LEFT SECTION: Workflow Switcher with integrated name */}
              <div className="relative flex items-center">
                {isEditingName ? (
                  <input
                    type="text"
                    value={editedName}
                    onChange={(e) => setEditedName(e.target.value)}
                    onBlur={handleWorkflowNameSave}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleWorkflowNameSave();
                      if (e.key === 'Escape') {
                        setEditedName(workflowName);
                        setIsEditingName(false);
                      }
                    }}
                    autoFocus
                    className="px-3 py-2 text-sm font-semibold bg-white dark:bg-background-dark border border-primary rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                    style={{ color: 'var(--color-text-primary, #1a1a1a)', minWidth: '250px' }}
                  />
                ) : (
                  <button
                    onClick={handleToggleWorkflowDropdown}
                    className="inline-flex items-center gap-2 px-3 py-2 text-sm font-semibold bg-white dark:bg-background-dark border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
                    style={{ color: 'var(--color-text-primary)' }}
                    title="Click to switch workflow or double-click name to rename"
                  >
                    <span
                      onDoubleClick={handleStartEditingName}
                      className="max-w-[200px] truncate"
                    >
                      {workflowName}
                    </span>
                    <span className="material-symbols-outlined text-lg" style={{ color: 'var(--color-text-muted)' }}>
                      expand_more
                    </span>
                  </button>
                )}

                {/* Workflow Dropdown */}
                {showWorkflowDropdown && (
                  <>
                    {/* Backdrop */}
                    <div
                      className="fixed inset-0 z-40"
                      onClick={handleCloseWorkflowDropdown}
                    />
                    <div
                      className="absolute top-full left-0 mt-1 w-80 rounded-lg shadow-xl z-50 max-h-96 overflow-hidden flex flex-col border"
                      style={{
                        backgroundColor: 'var(--color-panel-dark)',
                        borderColor: 'var(--color-border-dark)'
                      }}
                    >
                      {/* Search Bar */}
                      <div
                        className="p-3 border-b"
                        style={{ borderColor: 'var(--color-border-dark)' }}
                      >
                        <input
                          type="text"
                          placeholder="Search workflows..."
                          value={workflowSearchQuery}
                          onChange={handleWorkflowSearchChange}
                          className="w-full px-3 py-2 text-sm rounded-lg border focus:outline-none focus:ring-2 transition-all"
                          style={{
                            backgroundColor: 'var(--color-background-light)',
                            borderColor: 'var(--color-border-dark)',
                            color: 'var(--color-text-primary)'
                          }}
                        />
                      </div>

                      {/* Workflow List */}
                      <div className="overflow-y-auto">
                        {filteredWorkflows.length === 0 ? (
                          <div
                            className="p-4 text-center text-sm"
                            style={{ color: 'var(--color-text-muted)' }}
                          >
                            No workflows found
                          </div>
                        ) : (
                          filteredWorkflows.map((workflow) => {
                            const isActive = currentWorkflowId === workflow.id;
                            return (
                              <button
                                key={workflow.id}
                                onClick={() => handleWorkflowSwitch(workflow.id)}
                                className="w-full px-3 py-2.5 text-left transition-colors border-b last:border-0"
                                style={{
                                  borderColor: 'var(--color-border-dark)',
                                  backgroundColor: isActive ? 'var(--color-primary-alpha, rgba(139, 92, 246, 0.1))' : 'transparent',
                                  borderLeftWidth: isActive ? '3px' : '0px',
                                  borderLeftColor: isActive ? 'var(--color-primary)' : 'transparent'
                                }}
                                onMouseEnter={(e) => {
                                  if (!isActive) {
                                    e.currentTarget.style.backgroundColor = 'var(--color-background-light, rgba(255, 255, 255, 0.03))';
                                  }
                                }}
                                onMouseLeave={(e) => {
                                  if (!isActive) {
                                    e.currentTarget.style.backgroundColor = 'transparent';
                                  }
                                }}
                              >
                                {/* Workflow name - single line, larger text */}
                                <div
                                  className="font-semibold text-sm leading-tight"
                                  style={{
                                    color: isActive ? 'var(--color-primary)' : 'var(--color-text-primary)',
                                    wordBreak: 'break-word',
                                    overflowWrap: 'break-word',
                                    display: '-webkit-box',
                                    WebkitLineClamp: 2,
                                    WebkitBoxOrient: 'vertical',
                                    overflow: 'hidden'
                                  }}
                                >
                                  {workflow.name}
                                </div>
                                {/* Description - removed for cleaner look */}
                              </button>
                            );
                          })
                        )}
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* DIVIDER */}
              <div className="w-px h-6 bg-gray-300 dark:bg-border-dark" />

              {/* CENTER-LEFT SECTION: Action Buttons */}
              <div className="flex items-center gap-2.5">
                <button
                  onClick={() => handleSave(false)}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg transition-all hover:opacity-90 bg-primary text-white shadow-sm"
                  title="Save workflow"
                >
                  <Save className="w-4 h-4" />
                  <span>Save</span>
                </button>

                {/* Version Management Buttons */}
                {currentWorkflowId && (
                  <>
                    <button
                      onClick={handleSaveVersion}
                      className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg transition-all hover:opacity-90 bg-white dark:bg-background-dark border border-gray-300 dark:border-border-dark text-primary"
                      title="Save as new version"
                    >
                      <HistoryIcon className="w-4 h-4" />
                      <span>Save Version</span>
                    </button>

                    <div className="relative">
                      <button
                        onClick={() => setShowVersionDropdown(!showVersionDropdown)}
                        className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-white dark:bg-background-dark border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors text-text-primary dark:text-text-primary"
                        title="Switch version"
                      >
                        <HistoryIcon className="w-4 h-4" />
                        <span>{currentVersion ? `v${currentVersion.version_number}` : 'Versions'}</span>
                        <span className="text-xs opacity-60">▼</span>
                      </button>

                      {/* Version Dropdown */}
                      {showVersionDropdown && (
                        <div className="absolute top-full mt-2 right-0 w-80 bg-white dark:bg-panel-dark border border-gray-200 dark:border-border-dark rounded-lg shadow-xl z-50 max-h-96 overflow-y-auto">
                          <div className="p-3 border-b border-gray-200 dark:border-border-dark">
                            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                              Workflow Versions
                            </h3>
                          </div>

                          {loadingVersions ? (
                            <div className="p-4 text-center text-gray-500 dark:text-gray-400">
                              Loading versions...
                            </div>
                          ) : versions.length === 0 ? (
                            <div className="p-4 text-center text-gray-500 dark:text-gray-400 text-sm">
                              No versions yet. Click "Save Version" to create one.
                            </div>
                          ) : (
                            <div className="py-2">
                              {versions.map((version) => (
                                <button
                                  key={version.id}
                                  onClick={() => handleLoadVersion(version.version_number)}
                                  className={`w-full px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-white/5 transition-colors border-l-4 ${version.is_current
                                    ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
                                    : 'border-transparent'
                                    }`}
                                >
                                  <div className="flex items-center justify-between mb-1">
                                    <span className="text-sm font-semibold text-gray-900 dark:text-white">
                                      Version {version.version_number}
                                      {version.is_current && (
                                        <span className="ml-2 px-2 py-0.5 text-xs bg-green-500 text-white rounded">
                                          Current
                                        </span>
                                      )}
                                    </span>
                                    <span className="text-xs text-gray-500 dark:text-gray-400">
                                      {new Date(version.created_at).toLocaleDateString()}
                                    </span>
                                  </div>
                                  {version.notes && (
                                    <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-2">
                                      {version.notes}
                                    </p>
                                  )}
                                  {version.created_by && (
                                    <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                                      by {version.created_by}
                                    </p>
                                  )}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </>
                )}

                <button
                  onClick={handleToggleSettingsModal}
                  className="p-2 rounded-lg transition-colors flex items-center gap-2"
                  style={{
                    backgroundColor: 'var(--color-background-light)',
                    color: 'var(--color-text-primary)',
                    border: `1px solid var(--color-border-dark)`
                  }}
                  title="Workflow Settings"
                >
                  <Settings size={18} />
                  <span className="text-sm font-medium">Settings</span>
                </button>

                <button
                  onClick={handleRun}
                  className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg transition-all hover:opacity-90 text-white shadow-sm ${executionStatus.state === 'running'
                    ? 'bg-amber-500 dark:bg-amber-600'
                    : 'bg-primary'
                    }`}
                  title={executionStatus.state === 'running' ? 'Workflow running - click to cancel and restart' : 'Execute workflow'}
                >
                  {executionStatus.state === 'running' ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Running...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      <span>Run</span>
                    </>
                  )}
                </button>

                <button
                  onClick={handleStop}
                  disabled={!currentTaskId || executionStatus?.state !== 'running'}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed bg-red-600 dark:bg-red-500 text-white shadow-sm"
                  title="Stop running workflow"
                >
                  <StopCircle className="w-4 h-4" />
                  <span>Stop</span>
                </button>

              </div>

              {/* DIVIDER */}
              <div className="w-px h-6 bg-gray-300 dark:bg-border-dark" />

              {/* CENTER SECTION: Secondary Actions */}
              <div className="flex items-center gap-2">
                <button
                  onClick={handleClear}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 dark:text-red-400 bg-white dark:bg-background-dark border border-red-300 dark:border-red-500/30 rounded-lg hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors"
                  title="Clear all nodes"
                >
                  <Trash2 className="w-4 h-4" />
                  <span>Clear</span>
                </button>
              </div>

            </div>
          </div>
        )}

        {/* Tab Navigation */}
        {nodes.length > 0 && (
          <div className="bg-white dark:bg-panel-dark border-b border-gray-200 dark:border-border-dark">
            <div className="flex items-center px-4">
              <button
                onClick={() => handleTabChange('studio')}
                className={`px-4 py-3 text-sm font-semibold border-b-2 transition-all ${activeTab === 'studio'
                  ? 'border-primary text-primary'
                  : 'border-transparent text-gray-600 dark:text-text-muted hover:text-gray-900 dark:hover:text-white'
                  }`}
              >
                Studio
              </button>
              <button
                onClick={() => {
                  handleTabChange('results');
                  setShowExecutionDialog(false); // Close any open dialog when switching tabs
                  // Don't connect to workflow stream when just viewing results
                  if (executionStatus.state !== 'running') {
                    setCurrentTaskId(null);
                    localStorage.removeItem('langconfig-current-task-id');
                  }
                }}
                className={`px-4 py-3 text-sm font-semibold border-b-2 transition-all ${activeTab === 'results'
                  ? 'border-primary text-primary'
                  : 'border-transparent text-gray-600 dark:text-text-muted hover:text-gray-900 dark:hover:text-white'
                  }`}
              >
                Results {taskHistory.length > 0 && `(${taskHistory.length})`}
              </button>

              {/* Spacer to push workflow ID to the right */}
              <div className="flex-1" />

              {/* Unsaved Changes Indicator */}
              {hasUnsavedChanges && (
                <div className="flex items-center gap-2 text-xs font-medium text-yellow-600 dark:text-yellow-500 py-3 animate-pulse mr-4">
                  <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
                    warning
                  </span>
                  Unsaved Changes
                </div>
              )}

              {/* Workflow ID - Plain text on the right */}
              {currentWorkflowId && (
                <div className="text-xs font-mono text-text-muted dark:text-text-muted py-3">
                  ID: {currentWorkflowId}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Canvas Area */}
        <div className="flex-1 bg-gray-50 dark:bg-background-dark relative overflow-hidden" id="workflow-canvas-container">
          {/* Studio Tab - Keep ReactFlow mounted to preserve node selection */}
          <div style={{ display: activeTab === 'studio' ? 'flex' : 'none', flexDirection: 'column', height: '100%' }}>
            {nodes.length === 0 ? (
              <div className="w-full h-full flex flex-col items-center justify-center gap-6 text-center p-12">
                <div className="w-24 h-24 rounded-full bg-primary/10 dark:bg-primary/20 flex items-center justify-center">
                  <span className="material-symbols-outlined text-primary" style={{ fontSize: '48px' }}>
                    account_tree
                  </span>
                </div>
                <div>
                  <h4 className="text-2xl font-bold text-gray-900 dark:text-white mb-3">
                    Start Building Your Workflow
                  </h4>
                  <p className="text-gray-600 dark:text-gray-400 max-w-md text-base">
                    Click on an agent from the left panel to add your first node, then connect them to create your workflow.
                  </p>
                </div>
              </div>
            ) : (
              <>
                <ReactFlow
                  nodes={validatedNodes}
                  edges={validatedEdges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onConnect={onConnect}
                  onNodeClick={handleNodeClick}
                  onNodeDragStart={onNodeDragStart}
                  onNodeDragStop={onNodeDragStop}
                  onInit={(instance) => {
                    setReactFlowInstance(instance);
                    setCurrentZoom(instance.getZoom()); // Set initial zoom
                    // Fit view on initial load if nodes exist - more zoomed out for better visibility
                    if (nodes.length > 0) {
                      setTimeout(() => {
                        instance.fitView({ padding: 0.5, maxZoom: 0.6, minZoom: 0.3 });
                        setCurrentZoom(instance.getZoom()); // Update zoom after fit
                      }, 100);
                    }
                  }}
                  onMove={(_event, viewport) => {
                    // Update zoom level when viewport changes
                    if (viewport && viewport.zoom !== currentZoom) {
                      setCurrentZoom(viewport.zoom);
                    }
                  }}
                  nodeTypes={nodeTypes}
                  className="w-full h-full"
                  deleteKeyCode={["Backspace", "Delete"]}
                  multiSelectionKeyCode="Shift"
                  panOnScroll={true}
                  zoomOnScroll={true}
                  zoomOnPinch={true}
                  zoomOnDoubleClick={false}
                  fitView
                  fitViewOptions={{ padding: 0.5, maxZoom: 0.6, minZoom: 0.3 }}
                  defaultViewport={{ x: 0, y: 0, zoom: 0.5 }}
                >
                  <Background
                    variant={BackgroundVariant.Dots}
                    gap={16}
                    size={1}
                    className="bg-gray-50 dark:bg-background-dark"
                  />

                  {/* Controls - repositioned to top-left */}
                  <Controls
                    showInteractive={false}
                    position="top-left"
                    className="!bg-white dark:!bg-panel-dark !border-2 !border-gray-200 dark:!border-border-dark !rounded-lg !shadow-lg"
                  />

                  {/* Control Buttons - Top Right */}
                  <Panel position="top-right" className="flex gap-2">
                    {/* Live Execution Panel Toggle */}
                    <button
                      onClick={handleToggleLiveExecutionPanel}
                      className={`px-2 py-1.5 rounded-md border flex items-center gap-1.5 text-xs font-semibold transition-all ${!showLiveExecutionPanel ? 'hover:scale-105 hover:opacity-90' : ''
                        }`}
                      style={{
                        backgroundColor: showLiveExecutionPanel ? '#0d6832' : 'var(--color-primary)',
                        borderColor: showLiveExecutionPanel ? '#0d6832' : 'var(--color-primary)',
                        color: 'white',
                        boxShadow: showLiveExecutionPanel ? 'inset 0 2px 4px rgba(0,0,0,0.3)' : '0 2px 4px rgba(0,0,0,0.1)',
                        transform: showLiveExecutionPanel ? 'translateY(1px)' : 'translateY(-1px)'
                      }}
                      title="Toggle live execution panel - Shows detailed agent thinking, tool calls, and execution flow"
                    >
                      <List className="w-3.5 h-3.5" />
                      <span>Panel</span>
                    </button>

                    {/* Thinking Toasts Toggle */}
                    <button
                      onClick={handleToggleThinkingStream}
                      className={`px-2 py-1.5 rounded-md border flex items-center gap-1.5 text-xs font-semibold transition-all ${!showThinkingStream ? 'hover:scale-105 hover:opacity-90' : ''
                        }`}
                      style={{
                        backgroundColor: showThinkingStream ? '#0d6832' : 'var(--color-primary)',
                        borderColor: showThinkingStream ? '#0d6832' : 'var(--color-primary)',
                        color: 'white',
                        boxShadow: showThinkingStream ? 'inset 0 2px 4px rgba(0,0,0,0.3)' : '0 2px 4px rgba(0,0,0,0.1)',
                        transform: showThinkingStream ? 'translateY(1px)' : 'translateY(-1px)'
                      }}
                      title={showThinkingStream ? 'Hide thinking toast notifications on canvas' : 'Show thinking toast notifications on canvas'}
                    >
                      <Brain className="w-3.5 h-3.5" />
                      <span>Thinking</span>
                    </button>

                    {/* Workflow Settings Modal */}
                    {showSettingsModal && (
                      <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm">
                        <div
                          className="w-full max-w-md rounded-xl shadow-2xl overflow-hidden"
                          style={{
                            backgroundColor: 'var(--color-panel-dark)',
                            border: '1px solid var(--color-border-dark)'
                          }}
                        >
                          <div className="px-6 py-4 border-b flex justify-between items-center" style={{ borderColor: 'var(--color-border-dark)' }}>
                            <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                              Workflow Settings
                            </h3>
                            <button
                              onClick={handleCloseSettingsModal}
                              className="p-1 rounded hover:bg-white/10 transition-colors"
                              style={{ color: 'var(--color-text-muted)' }}
                            >
                              <X size={20} />
                            </button>
                          </div>

                          <div className="p-6 space-y-6">
                            {/* Checkpointer Setting */}
                            <div className="flex items-start gap-3">
                              <div className="flex-1">
                                <label className="text-sm font-medium block mb-1" style={{ color: 'var(--color-text-primary)' }}>
                                  Enable Persistence (Checkpointer)
                                </label>
                                <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
                                  Saves conversation history between workflow runs. Required for Human-in-the-Loop (HITL) and resuming interrupted workflows.
                                </p>
                                {checkpointerEnabled && (
                                  <p className="text-xs leading-relaxed mt-2 p-2 rounded-md" style={{ backgroundColor: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b' }}>
                                    ⚠️ <strong>Warning:</strong> When enabled, agents will remember previous executions. The same prompt may produce different results as the agent may reference prior context. Use clear, specific instructions to avoid confusion.
                                  </p>
                                )}
                              </div>
                              <div className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors cursor-pointer ${checkpointerEnabled ? 'bg-primary' : 'bg-gray-600'}`} onClick={handleToggleCheckpointer}>
                                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${checkpointerEnabled ? 'translate-x-6' : 'translate-x-1'}`} />
                              </div>
                            </div>

                            {/* Recursion Limit Setting */}
                            <div>
                              <label className="text-sm font-medium block mb-1" style={{ color: 'var(--color-text-primary)' }}>
                                Global Recursion Limit
                              </label>
                              <p className="text-xs mb-3" style={{ color: 'var(--color-text-muted)' }}>
                                Maximum number of steps the workflow can execute before stopping. Prevents infinite loops.
                              </p>
                              <div className="flex items-center gap-3">
                                <input
                                  type="range"
                                  min="5"
                                  max="500"
                                  step="5"
                                  value={globalRecursionLimit}
                                  onChange={(e) => setGlobalRecursionLimit(parseInt(e.target.value))}
                                  className="flex-1 h-2 rounded-lg appearance-none cursor-pointer bg-gray-700"
                                />
                                <span className="text-sm font-mono w-12 text-right" style={{ color: 'var(--color-text-primary)' }}>
                                  {globalRecursionLimit}
                                </span>
                              </div>
                            </div>
                          </div>

                          <div className="px-6 py-4 border-t flex justify-end" style={{ borderColor: 'var(--color-border-dark)', backgroundColor: 'var(--color-background-dark)' }}>
                            <button
                              onClick={() => setShowSettingsModal(false)}
                              className="px-4 py-2 rounded-lg text-sm font-medium transition-colors bg-primary text-white hover:bg-primary/90"
                            >
                              Done
                            </button>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Debug Modal */}
                    <button
                      onClick={handleDebugWorkflow}
                      className="px-2 py-1.5 rounded-md border flex items-center gap-1.5 text-xs font-semibold transition-all hover:scale-105 hover:opacity-90"
                      style={{
                        backgroundColor: 'var(--color-primary)',
                        borderColor: 'var(--color-primary)',
                        color: 'white',
                        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                        transform: 'translateY(-1px)'
                      }}
                      title="Debug Workflow - View backend configuration and tool assignments"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>bug_report</span>
                      <span>Debug</span>
                    </button>
                  </Panel>

                  {/* MiniMap with enhanced styling - only show when nodes have valid positions */}
                  {validatedNodes.length > 0 && (
                    <MiniMap
                      nodeColor={() => 'var(--color-primary)'}
                      maskColor="rgba(0, 0, 0, 0.1)"
                      position="bottom-left"
                      className="!bg-white dark:!bg-panel-dark !border-2 !border-gray-200 dark:!border-border-dark !rounded-lg !shadow-lg"
                      style={{
                        backgroundColor: 'var(--color-panel-dark)',
                        width: '120px',
                        height: '80px'
                      }}
                    />
                  )}
                </ReactFlow>

                {/* Live Execution Panel - Slides in from left, independent from thinking toasts */}
                <LiveExecutionPanel
                  isVisible={showLiveExecutionPanel}
                  events={workflowEvents}
                  latestEvent={latestEvent}
                  onClose={() => setShowLiveExecutionPanel(false)}
                  executionStatus={executionStatus}
                  workflowMetrics={workflowMetrics}
                  userPrompt={userPrompt}
                  workflowName={workflowName}
                />

                {/* Thinking Toasts - Rendered outside ReactFlow with screen coordinates */}
                {reactFlowInstance && nodes.map((node) => {
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
                    console.warn('[WorkflowCanvas] flowToScreenPosition failed:', error);
                    return null;
                  }

                  // Skip if screen position is invalid (can happen during initial render)
                  if (!screenPosition ||
                    typeof screenPosition.x !== 'number' ||
                    typeof screenPosition.y !== 'number' ||
                    isNaN(screenPosition.x) ||
                    isNaN(screenPosition.y)) {
                    console.warn('[WorkflowCanvas] Invalid screen position:', screenPosition, 'for node:', node.data.label);
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

                  // Only show toast if thinking stream is enabled AND there's something to display
                  if (!showThinkingStream || (!displayText && !showToolStatus)) {
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
            )}

            {/* Floating Total Cost Panel - Top Right */}
            {activeTab === 'studio' && (() => {
              // Calculate total cost from all nodes
              const totalCost = Object.values(nodeTokenCosts).reduce((sum, cost) => {
                // Parse cost string (e.g., "$0.0234" -> 0.0234)
                const costValue = parseFloat(cost.costString.replace('$', '')) || 0;
                return sum + costValue;
              }, 0);

              const totalTokens = Object.values(nodeTokenCosts).reduce((sum, cost) => sum + (cost.totalTokens || 0), 0);

              // Only show if there's any cost data
              if (totalTokens === 0) return null;

              return (
                <div
                  className="absolute top-4 z-40 transition-all duration-300 pointer-events-none"
                  style={{
                    right: onNodeSelect ? '420px' : '20px', // Shift left when node config panel is open
                  }}
                >
                  <div
                    className="rounded-lg shadow-xl border-2 pointer-events-auto"
                    style={{
                      backgroundColor: 'var(--color-panel-dark)',
                      borderColor: 'var(--color-primary)',
                    }}
                  >
                    <div className="px-4 py-2">
                      <div className="text-xs font-medium mb-1" style={{ color: 'var(--color-text-muted)' }}>
                        Total Workflow Cost
                      </div>
                      <div className="flex items-baseline gap-2">
                        <span className="text-2xl font-bold font-mono" style={{ color: 'var(--color-primary)' }}>
                          ${totalCost.toFixed(4)}
                        </span>
                        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                          {totalTokens.toLocaleString()} tokens
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })()}
          </div>

          {/* Results Tab - Only mount when active for performance */}
          {activeTab === 'results' && (
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
              {/* Results Tab Content */}
              <div className="w-full h-full flex flex-col">
                {/* Results Subtabs */}
                <div className="flex items-center justify-between border-b" style={{ borderColor: 'var(--color-border-dark)' }}>
                  <div className="flex">
                    <button
                      onClick={() => setResultsSubTab('output')}
                      className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${resultsSubTab === 'output'
                        ? 'border-primary text-primary'
                        : 'border-transparent hover:text-primary'
                        }`}
                      style={resultsSubTab !== 'output' ? { color: 'var(--color-text-muted)' } : {}}
                    >
                      Workflow Output
                    </button>
                    <button
                      onClick={() => setResultsSubTab('memory')}
                      className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${resultsSubTab === 'memory'
                        ? 'border-primary text-primary'
                        : 'border-transparent hover:text-primary'
                        }`}
                      style={resultsSubTab !== 'memory' ? { color: 'var(--color-text-muted)' } : {}}
                    >
                      <Database className="w-4 h-4 inline mr-2" />
                      Memory
                    </button>
                    <button
                      onClick={() => setResultsSubTab('files')}
                      className={`px-6 py-3 text-sm font-medium transition-colors border-b-2 ${resultsSubTab === 'files'
                        ? 'border-primary text-primary'
                        : 'border-transparent hover:text-primary'
                        }`}
                      style={resultsSubTab !== 'files' ? { color: 'var(--color-text-muted)' } : {}}
                    >
                      <FolderOpen className="w-4 h-4 inline mr-2" />
                      Files {files.length > 0 && `(${files.length})`}
                    </button>
                  </div>

                  {/* View Execution Log Button */}
                  {taskHistory.length > 0 && (
                    <button
                      onClick={() => {
                        const taskToView = selectedHistoryTask || taskHistory[0];
                        setReplayTaskId(taskToView.id);
                        setShowReplayPanel(true);
                      }}
                      className="inline-flex items-center gap-2 px-4 py-2 mr-4 text-sm font-medium rounded-lg transition-all hover:opacity-90"
                      style={{
                        backgroundColor: 'var(--color-primary)',
                        color: 'white'
                      }}
                      title="View detailed execution log"
                    >
                      <List className="w-4 h-4" />
                      <span>View Execution Log</span>
                    </button>
                  )}
                </div>

                {/* Subtab Content */}
                <div className="flex-1 overflow-hidden flex">
                  {/* Output Subtab */}
                  {resultsSubTab === 'output' && (
                    <div className="flex-1 overflow-y-auto p-6">
                      {loadingHistory ? (
                        <div className="flex items-center justify-center py-16">
                          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
                        </div>
                      ) : taskHistory.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-16 text-center">
                          <HistoryIcon className="w-16 h-16 text-gray-300 dark:text-text-muted/30 mb-4" />
                          <p className="text-lg font-medium text-gray-600 dark:text-text-muted">
                            No results yet
                          </p>
                          <p className="text-sm text-gray-500 dark:text-text-muted/70 mt-2">
                            Execute this workflow to see results here.
                          </p>
                        </div>
                      ) : (
                        <div className="w-full px-4">
                          {/* Display Selected Task or Latest */}
                          {(() => {
                            const displayTask = selectedHistoryTask || taskHistory[0];
                            const taskOutput = displayTask?.result;
                            const isLatestTask = displayTask?.id === taskHistory[0]?.id;

                            if (!taskOutput) {
                              return (
                                <div className="flex flex-col items-center justify-center py-16 text-center">
                                  <span className="material-symbols-outlined text-6xl text-gray-300 dark:text-text-muted/30 mb-4">
                                    pending_actions
                                  </span>
                                  <p className="text-lg font-medium text-gray-600 dark:text-text-muted">
                                    No output data available
                                  </p>
                                  <p className="text-sm text-gray-500 dark:text-text-muted/70 mt-2">
                                    Task #{displayTask?.id} has no result data.
                                  </p>
                                </div>
                              );
                            }

                            return (
                              <div className="bg-white dark:bg-panel-dark border-2 border-primary dark:border-primary/50 rounded-lg p-6 shadow-lg">
                                <div className="flex items-center justify-between mb-4">
                                  {/* Task Header with ID and Status */}
                                  <div className="flex-1 min-w-0 mr-4">
                                    <div className="flex items-center gap-3">
                                      <span className="text-xs font-mono text-gray-500 dark:text-text-muted">
                                        Task #{displayTask.id}
                                      </span>
                                      {!isLatestTask && (
                                        <span className="text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
                                          Historical
                                        </span>
                                      )}
                                      {isLatestTask && (
                                        <span className="text-xs px-2 py-0.5 rounded bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 font-semibold">
                                          Latest
                                        </span>
                                      )}
                                    </div>
                                    <h3 className="text-lg font-bold mt-1" style={{ color: 'var(--color-text-primary)' }}>
                                      Workflow Results
                                    </h3>
                                  </div>
                                  <div className="flex items-center gap-2 flex-shrink-0">
                                    {displayTask?.created_at && (
                                      <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                                        {new Date(displayTask.created_at).toLocaleString()}
                                      </span>
                                    )}

                                    {/* Toggle Animation Button */}
                                    <button
                                      onClick={() => setShowAnimatedReveal(!showAnimatedReveal)}
                                      className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-white/10"
                                      title={showAnimatedReveal ? "Show static view" : "Show animated reveal"}
                                    >
                                      <span className="material-symbols-outlined text-lg">
                                        {showAnimatedReveal ? 'auto_awesome' : 'text_fields'}
                                      </span>
                                    </button>

                                    {/* Compare Versions Button */}
                                    {currentWorkflowId && versions.length > 1 && (
                                      <button
                                        onClick={() => setCompareMode(!compareMode)}
                                        className={`p-2 rounded-md ${compareMode
                                          ? 'bg-primary text-white'
                                          : 'hover:bg-gray-100 dark:hover:bg-white/10'
                                          }`}
                                        title="Compare workflow versions"
                                      >
                                        <span className="material-symbols-outlined text-lg">
                                          compare_arrows
                                        </span>
                                      </button>
                                    )}

                                    {/* Copy Results Button */}
                                    <button
                                      onClick={() => {
                                        const textToCopy = taskOutput?.formatted_content || '';
                                        navigator.clipboard.writeText(textToCopy);
                                        setCopiedToClipboard(true);
                                        setTimeout(() => setCopiedToClipboard(false), 2000);
                                      }}
                                      className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-white/10"
                                      title="Copy results to clipboard"
                                    >
                                      {copiedToClipboard ? (
                                        <Check className="w-4 h-4 text-green-600 dark:text-green-400" />
                                      ) : (
                                        <Copy className="w-4 h-4 text-gray-600 dark:text-text-muted" />
                                      )}
                                    </button>

                                    {/* Export to PDF Button */}
                                    <button
                                      onClick={async () => {
                                        try {
                                          const content = taskOutput?.formatted_content || '';
                                          const metadata = {
                                            date: new Date().toLocaleString(),
                                            duration: selectedHistoryTask?.duration_seconds || taskHistory[0]?.duration_seconds,
                                            tokens: selectedHistoryTask?.result?.workflow_summary?.total_tokens || taskHistory[0]?.result?.workflow_summary?.total_tokens,
                                            cost: selectedHistoryTask?.result?.workflow_summary?.total_cost_usd || taskHistory[0]?.result?.workflow_summary?.total_cost_usd,
                                          };
                                          await exportToPDF(content, workflowName || 'Workflow_Results', metadata);
                                        } catch (error) {
                                          console.error('Failed to export PDF:', error);
                                          alert('Failed to export PDF. Please try again.');
                                        }
                                      }}
                                      className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-white/10"
                                      title="Export to PDF"
                                    >
                                      <Download className="w-4 h-4 text-gray-600 dark:text-text-muted" />
                                    </button>

                                    {/* Export to Word Button */}
                                    <button
                                      onClick={async () => {
                                        try {
                                          const executionId = selectedHistoryTask?.id || taskHistory[0]?.id;
                                          if (!executionId) {
                                            alert('No execution found to export');
                                            return;
                                          }

                                          // Call backend API to generate Word document
                                          const response = await apiClient.exportWorkflowExecutionDocx(executionId);

                                          // Create download link
                                          const url = window.URL.createObjectURL(new Blob([response.data]));
                                          const link = document.createElement('a');
                                          link.href = url;
                                          const filename = `${workflowName?.replace(/\s+/g, '_') || 'workflow_results'}_${executionId}.docx`;
                                          link.setAttribute('download', filename);
                                          document.body.appendChild(link);
                                          link.click();
                                          link.parentNode?.removeChild(link);
                                          window.URL.revokeObjectURL(url);
                                        } catch (error) {
                                          console.error('Failed to export Word document:', error);
                                          alert('Failed to export Word document. Please try again.');
                                        }
                                      }}
                                      className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-white/10"
                                      title="Export to Word (.docx)"
                                    >
                                      <span className="material-symbols-outlined text-base text-gray-600 dark:text-text-muted">
                                        description
                                      </span>
                                    </button>

                                    {/* View Raw Output Toggle */}
                                    <button
                                      onClick={() => setShowRawOutput(!showRawOutput)}
                                      className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-white/10"
                                      title={showRawOutput ? "Hide raw output" : "Show raw output"}
                                    >
                                      {showRawOutput ? (
                                        <EyeOff className="w-4 h-4 text-gray-600 dark:text-text-muted" />
                                      ) : (
                                        <Eye className="w-4 h-4 text-gray-600 dark:text-text-muted" />
                                      )}
                                    </button>
                                  </div>
                                </div>

                                {/* Version Comparison Panel */}
                                {compareMode && currentWorkflowId && (
                                  <div className="mb-6 p-4 bg-gray-50 dark:bg-background-dark border-2 border-primary dark:border-primary/50 rounded-lg">
                                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                                      Compare Workflow Versions
                                    </h3>

                                    <div className="grid grid-cols-2 gap-4 mb-4">
                                      {/* Version 1 Selector */}
                                      <div>
                                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                          Version 1
                                        </label>
                                        <select
                                          value={compareVersion1?.version_number || ''}
                                          onChange={(e) => {
                                            const version = versions.find(v => v.version_number === parseInt(e.target.value));
                                            setCompareVersion1(version);
                                          }}
                                          className="w-full px-3 py-2 bg-white dark:bg-panel-dark border border-gray-300 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white"
                                        >
                                          <option value="">Select version...</option>
                                          {versions.map(v => (
                                            <option key={v.id} value={v.version_number}>
                                              v{v.version_number} - {new Date(v.created_at).toLocaleDateString()}
                                              {v.notes ? ` - ${v.notes.substring(0, 30)}...` : ''}
                                            </option>
                                          ))}
                                        </select>
                                      </div>

                                      {/* Version 2 Selector */}
                                      <div>
                                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                          Version 2
                                        </label>
                                        <select
                                          value={compareVersion2?.version_number || ''}
                                          onChange={(e) => {
                                            const version = versions.find(v => v.version_number === parseInt(e.target.value));
                                            setCompareVersion2(version);
                                          }}
                                          className="w-full px-3 py-2 bg-white dark:bg-panel-dark border border-gray-300 dark:border-border-dark rounded-lg text-sm text-gray-900 dark:text-white"
                                        >
                                          <option value="">Select version...</option>
                                          {versions.map(v => (
                                            <option key={v.id} value={v.version_number}>
                                              v{v.version_number} - {new Date(v.created_at).toLocaleDateString()}
                                              {v.notes ? ` - ${v.notes.substring(0, 30)}...` : ''}
                                            </option>
                                          ))}
                                        </select>
                                      </div>
                                    </div>

                                    <button
                                      onClick={handleCompareVersions}
                                      disabled={!compareVersion1 || !compareVersion2 || loadingComparison}
                                      className="px-4 py-2 bg-primary text-white rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                      {loadingComparison ? 'Comparing...' : 'Compare Versions'}
                                    </button>

                                    {/* Comparison Results */}
                                    {versionComparison && (
                                      <div className="mt-6 space-y-4">
                                        <h4 className="text-md font-semibold text-gray-900 dark:text-white">
                                          Comparison Results
                                        </h4>

                                        <div className="grid grid-cols-2 gap-4">
                                          {/* Version 1 Details */}
                                          <div className="p-4 bg-white dark:bg-panel-dark border border-gray-200 dark:border-border-dark rounded-lg">
                                            <h5 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">
                                              Version {versionComparison.version1.version_number}
                                            </h5>
                                            <p className="text-xs text-gray-600 dark:text-gray-400 mb-2">
                                              {new Date(versionComparison.version1.created_at).toLocaleString()}
                                            </p>
                                            {versionComparison.version1.notes && (
                                              <p className="text-xs text-gray-700 dark:text-gray-300 italic">
                                                "{versionComparison.version1.notes}"
                                              </p>
                                            )}
                                            <div className="mt-3 text-xs">
                                              <div className="text-gray-600 dark:text-gray-400">
                                                Nodes: {versionComparison.version1.config_snapshot.nodes?.length || 0}
                                              </div>
                                              <div className="text-gray-600 dark:text-gray-400">
                                                Edges: {versionComparison.version1.config_snapshot.edges?.length || 0}
                                              </div>
                                            </div>
                                          </div>

                                          {/* Version 2 Details */}
                                          <div className="p-4 bg-white dark:bg-panel-dark border border-gray-200 dark:border-border-dark rounded-lg">
                                            <h5 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">
                                              Version {versionComparison.version2.version_number}
                                            </h5>
                                            <p className="text-xs text-gray-600 dark:text-gray-400 mb-2">
                                              {new Date(versionComparison.version2.created_at).toLocaleString()}
                                            </p>
                                            {versionComparison.version2.notes && (
                                              <p className="text-xs text-gray-700 dark:text-gray-300 italic">
                                                "{versionComparison.version2.notes}"
                                              </p>
                                            )}
                                            <div className="mt-3 text-xs">
                                              <div className="text-gray-600 dark:text-gray-400">
                                                Nodes: {versionComparison.version2.config_snapshot.nodes?.length || 0}
                                              </div>
                                              <div className="text-gray-600 dark:text-gray-400">
                                                Edges: {versionComparison.version2.config_snapshot.edges?.length || 0}
                                              </div>
                                            </div>
                                          </div>
                                        </div>

                                        {/* Diff Summary */}
                                        <div className="p-4 bg-white dark:bg-panel-dark border border-gray-200 dark:border-border-dark rounded-lg">
                                          <h5 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
                                            Changes Summary
                                          </h5>
                                          <div className="space-y-2 text-sm">
                                            {versionComparison.diff.modified && Object.keys(versionComparison.diff.modified).length > 0 && (
                                              <div>
                                                <span className="text-yellow-600 dark:text-yellow-400 font-medium">
                                                  Modified:
                                                </span>
                                                <ul className="ml-4 mt-1 space-y-1">
                                                  {Object.keys(versionComparison.diff.modified).map(key => (
                                                    <li key={key} className="text-gray-700 dark:text-gray-300">
                                                      {key}
                                                    </li>
                                                  ))}
                                                </ul>
                                              </div>
                                            )}
                                            {versionComparison.diff.added && Object.keys(versionComparison.diff.added).length > 0 && (
                                              <div>
                                                <span className="text-green-600 dark:text-green-400 font-medium">
                                                  Added:
                                                </span>
                                                <ul className="ml-4 mt-1 space-y-1">
                                                  {Object.keys(versionComparison.diff.added).map(key => (
                                                    <li key={key} className="text-gray-700 dark:text-gray-300">
                                                      {key}
                                                    </li>
                                                  ))}
                                                </ul>
                                              </div>
                                            )}
                                            {versionComparison.diff.removed && Object.keys(versionComparison.diff.removed).length > 0 && (
                                              <div>
                                                <span className="text-red-600 dark:text-red-400 font-medium">
                                                  Removed:
                                                </span>
                                                <ul className="ml-4 mt-1 space-y-1">
                                                  {Object.keys(versionComparison.diff.removed).map(key => (
                                                    <li key={key} className="text-gray-700 dark:text-gray-300">
                                                      {key}
                                                    </li>
                                                  ))}
                                                </ul>
                                              </div>
                                            )}
                                            {(!versionComparison.diff.modified || Object.keys(versionComparison.diff.modified).length === 0) &&
                                              (!versionComparison.diff.added || Object.keys(versionComparison.diff.added).length === 0) &&
                                              (!versionComparison.diff.removed || Object.keys(versionComparison.diff.removed).length === 0) && (
                                                <p className="text-gray-600 dark:text-gray-400">
                                                  No changes detected between versions.
                                                </p>
                                              )}
                                          </div>
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                )}

                                {/* Workflow Final Output Display - 3 column layout */}
                                <div className="flex gap-6 w-full">
                                  {/* LEFT SIDEBAR - Agent Activity Timeline */}
                                  <div className="w-80 flex-shrink-0">
                                    {(() => {
                                      // Use pre-computed memoized values (computed at component level)
                                      const { tools, actions, toolCount, actionCount } = toolsAndActions;

                                      return (
                                        <div className="space-y-3">
                                          {/* Compact Stats */}
                                          <div className="grid grid-cols-2 gap-2">
                                            <div className="px-3 py-2 rounded border text-center"
                                              style={{
                                                backgroundColor: 'var(--color-panel-dark)',
                                                borderColor: 'var(--color-border-dark)'
                                              }}>
                                              <div className="text-xl font-bold" style={{ color: 'var(--color-primary)' }}>
                                                {toolCount}
                                              </div>
                                              <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                                                Tools
                                              </div>
                                            </div>
                                            <div className="px-3 py-2 rounded border text-center"
                                              style={{
                                                backgroundColor: 'var(--color-panel-dark)',
                                                borderColor: 'var(--color-border-dark)'
                                              }}>
                                              <div className="text-xl font-bold" style={{ color: 'var(--color-primary)' }}>
                                                {actionCount}
                                              </div>
                                              <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                                                Actions
                                              </div>
                                            </div>
                                          </div>

                                          {/* Tool Calls List */}
                                          {tools.length > 0 && (
                                            <div>
                                              <h4 className="text-xs font-semibold uppercase tracking-wider mb-2"
                                                style={{ color: 'var(--color-text-muted)' }}>
                                                Tool Calls
                                              </h4>
                                              <div className="rounded border"
                                                style={{
                                                  backgroundColor: 'var(--color-panel-dark)',
                                                  borderColor: 'var(--color-border-dark)'
                                                }}>
                                                <div className="max-h-96 overflow-y-auto">
                                                  {tools.map((tool: any, idx: number) => {
                                                    const isExpanded = expandedToolCalls.has(idx);

                                                    return (
                                                      <div key={idx} className="border-b last:border-b-0" style={{ borderColor: 'var(--color-border-dark)' }}>
                                                        {/* Tool header - clickable */}
                                                        <button
                                                          onClick={() => {
                                                            const newExpanded = new Set(expandedToolCalls);
                                                            if (isExpanded) {
                                                              newExpanded.delete(idx);
                                                            } else {
                                                              newExpanded.add(idx);
                                                            }
                                                            setExpandedToolCalls(newExpanded);
                                                          }}
                                                          className="w-full px-2 py-1.5 flex items-center gap-2 hover:bg-white/5 transition-colors text-left"
                                                        >
                                                          <span className="material-symbols-outlined text-xs"
                                                            style={{ color: 'var(--color-primary)' }}>
                                                            {isExpanded ? 'expand_more' : 'chevron_right'}
                                                          </span>
                                                          <span className="material-symbols-outlined text-xs"
                                                            style={{ color: 'var(--color-primary)' }}>
                                                            build
                                                          </span>
                                                          <span className="text-xs font-medium flex-1"
                                                            style={{ color: 'var(--color-text-primary)' }}>
                                                            {tool.name}
                                                          </span>
                                                        </button>

                                                        {/* Expanded details */}
                                                        {isExpanded && (
                                                          <div className="px-8 py-2 space-y-2 text-xs" style={{ backgroundColor: 'rgba(0,0,0,0.1)' }}>
                                                            {/* Tool arguments */}
                                                            {tool.args && (
                                                              <div>
                                                                <div className="font-semibold mb-1" style={{ color: 'var(--color-text-muted)' }}>
                                                                  Arguments:
                                                                </div>
                                                                <pre className="font-mono text-xs p-2 rounded overflow-x-auto"
                                                                  style={{ backgroundColor: 'rgba(0,0,0,0.2)', color: 'var(--color-text-primary)' }}>
                                                                  {typeof tool.args === 'string' ? tool.args : JSON.stringify(tool.args, null, 2)}
                                                                </pre>
                                                              </div>
                                                            )}

                                                            {/* Tool result */}
                                                            {tool.result && (
                                                              <div>
                                                                <div className="font-semibold mb-1" style={{ color: 'var(--color-text-muted)' }}>
                                                                  Result:
                                                                </div>
                                                                <pre className="font-mono text-xs p-2 rounded overflow-x-auto max-h-40"
                                                                  style={{ backgroundColor: 'rgba(0,0,0,0.2)', color: 'var(--color-text-primary)' }}>
                                                                  {typeof tool.result === 'string' ? tool.result.substring(0, 500) : JSON.stringify(tool.result, null, 2).substring(0, 500)}
                                                                  {(typeof tool.result === 'string' && tool.result.length > 500) || (typeof tool.result !== 'string' && JSON.stringify(tool.result).length > 500) ? '...' : ''}
                                                                </pre>
                                                              </div>
                                                            )}
                                                          </div>
                                                        )}
                                                      </div>
                                                    );
                                                  }, [taskOutput?.agent_messages, expandedToolCalls])}
                                                </div>
                                              </div>
                                            </div>
                                          )}

                                          {/* Actions List */}
                                          {actions.length > 0 && (
                                            <div>
                                              <h4 className="text-xs font-semibold uppercase tracking-wider mb-2"
                                                style={{ color: 'var(--color-text-muted)' }}>
                                                Key Actions
                                              </h4>
                                              <div className="rounded border"
                                                style={{
                                                  backgroundColor: 'var(--color-panel-dark)',
                                                  borderColor: 'var(--color-border-dark)'
                                                }}>
                                                <div className="max-h-60 overflow-y-auto">
                                                  {actions.map((action: string, idx: number) => (
                                                    <div key={idx}
                                                      className="px-2 py-1.5 border-b last:border-b-0"
                                                      style={{ borderColor: 'var(--color-border-dark)' }}>
                                                      <span className="text-xs" style={{ color: 'var(--color-text-primary)' }}>
                                                        {action}
                                                      </span>
                                                    </div>
                                                  ))}
                                                </div>
                                              </div>
                                            </div>
                                          )}

                                          {tools.length === 0 && actions.length === 0 && (
                                            <div className="text-center py-8 text-sm"
                                              style={{ color: 'var(--color-text-muted)' }}>
                                              No activity recorded
                                            </div>
                                          )}

                                          {/* Task Summary */}
                                          <div className="p-3 rounded-lg border"
                                            style={{
                                              backgroundColor: 'var(--color-panel-dark)',
                                              borderColor: 'var(--color-border-dark)'
                                            }}>
                                            <div className="text-xs font-semibold uppercase tracking-wider mb-2"
                                              style={{ color: 'var(--color-text-muted)' }}>
                                              Task Summary
                                            </div>
                                            <div className="space-y-1.5 text-xs">
                                              {displayTask?.id && (
                                                <div className="flex justify-between">
                                                  <span style={{ color: 'var(--color-text-muted)' }}>Task ID</span>
                                                  <span className="font-mono font-medium"
                                                    style={{ color: 'var(--color-text-primary)' }}>#{displayTask.id}</span>
                                                </div>
                                              )}
                                              {displayTask?.duration_seconds && (
                                                <div className="flex justify-between">
                                                  <span style={{ color: 'var(--color-text-muted)' }}>Duration</span>
                                                  <span className="font-medium"
                                                    style={{ color: 'var(--color-text-primary)' }}>{Math.round(displayTask.duration_seconds)}s</span>
                                                </div>
                                              )}
                                              {displayTask?.status && (
                                                <div className="flex justify-between">
                                                  <span style={{ color: 'var(--color-text-muted)' }}>Status</span>
                                                  <span className="font-medium capitalize"
                                                    style={{ color: 'var(--color-text-primary)' }}>{displayTask.status}</span>
                                                </div>
                                              )}
                                              {/* Token Usage - Using pre-computed memoized values */}
                                              {(() => {
                                                // Use pre-computed memoized values (computed at component level)
                                                const { totalTokens, costString } = tokenCostInfo;

                                                if (totalTokens > 0) {
                                                  return (
                                                    <>
                                                      <div className="flex justify-between">
                                                        <span style={{ color: 'var(--color-text-muted)' }}>Tokens</span>
                                                        <span className="font-mono font-medium"
                                                          style={{ color: 'var(--color-text-primary)' }}>
                                                          {totalTokens.toLocaleString()}
                                                        </span>
                                                      </div>
                                                      <div className="flex justify-between">
                                                        <span style={{ color: 'var(--color-text-muted)' }}>Cost</span>
                                                        <span className="font-mono font-medium"
                                                          style={{ color: 'var(--color-text-primary)' }}>
                                                          {costString}
                                                        </span>
                                                      </div>
                                                      <div className="flex justify-between text-xxs" style={{ opacity: 0.7 }}>
                                                        <span style={{ color: 'var(--color-text-muted)' }}>Model</span>
                                                        <span style={{ color: 'var(--color-text-muted)' }}>
                                                          {Object.keys(nodeTokenCosts).length > 1 ? 'Multi-agent' : (currentModelName.length > 20 ? currentModelName.substring(0, 20) + '...' : currentModelName)}
                                                        </span>
                                                      </div>
                                                    </>
                                                  );
                                                }
                                                return null;
                                              })()}
                                              {/* User's Prompt */}
                                              {displayTask?.user_input && (
                                                <div className="mt-3 pt-2 border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
                                                  <div className="text-xs font-semibold uppercase tracking-wider mb-1"
                                                    style={{ color: 'var(--color-text-muted)' }}>
                                                    User Prompt
                                                  </div>
                                                  <div className="text-xs italic leading-relaxed"
                                                    style={{ color: 'var(--color-text-primary)', opacity: 0.85 }}>
                                                    "{displayTask.user_input.length > 150 ? displayTask.user_input.substring(0, 150) + '...' : displayTask.user_input}"
                                                  </div>
                                                </div>
                                              )}
                                            </div>
                                          </div>
                                        </div>
                                      );
                                    })()}
                                  </div>

                                  {/* CENTER - Main Output Content */}
                                  <div className="flex-1">
                                    {/* Output Header */}
                                    <div className="mb-6 text-center">
                                      <h2 className="text-3xl font-bold mb-2" style={{ color: 'var(--color-primary)' }}>
                                        Workflow Results
                                      </h2>
                                      <div className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                                        Final Output
                                      </div>
                                    </div>

                                    {/* Main Output Content - Properly Formatted */}
                                    <div className="bg-white dark:bg-gray-900/30 rounded-lg shadow-xl p-8 border"
                                      style={{ borderColor: 'var(--color-border-light)' }}>
                                      <div className="prose prose-lg max-w-none">
                                        {(() => {
                                          const finalReport = (() => {
                                            // Try formatted_content first (cleanest output)
                                            if (taskOutput?.formatted_content) {
                                              return taskOutput.formatted_content;
                                            }

                                            // Try to get from agent_messages (last AI message with tool call)
                                            if (taskOutput?.agent_messages && taskOutput.agent_messages.length > 0) {
                                              const aiMessages = taskOutput.agent_messages.filter((m: any) => m.role === 'ai');
                                              if (aiMessages.length > 0) {
                                                const lastAgent = aiMessages[aiMessages.length - 1];

                                                // Check for tool_calls with file_write content
                                                if (lastAgent.tool_calls && lastAgent.tool_calls.length > 0) {
                                                  const fileWriteCall = lastAgent.tool_calls.find((tc: any) => tc.name === 'file_write');
                                                  if (fileWriteCall?.args?.content) {
                                                    return fileWriteCall.args.content;
                                                  }
                                                }

                                                // Extract text from content array
                                                if (Array.isArray(lastAgent.content)) {
                                                  const textParts = lastAgent.content
                                                    .filter((item: any) => item.type === 'text')
                                                    .map((item: any) => item.text);
                                                  if (textParts.length > 0) {
                                                    return textParts.join('\n');
                                                  }
                                                } else if (typeof lastAgent.content === 'string') {
                                                  return lastAgent.content;
                                                }
                                              }
                                            }

                                            return '';
                                          })();

                                          // Ensure finalReport is a string
                                          const reportString = typeof finalReport === 'string' ? finalReport : String(finalReport || '');

                                          // Clean and extract the actual report content
                                          const cleanReport = reportString
                                            .replace(/<thinking>.*?<\/thinking>/gs, '') // Remove thinking tags
                                            .replace(/<context>.*?<\/context>/gs, '') // Remove context tags
                                            .replace(/<\/?[a-z][a-z0-9]*[^>]*>/gi, '') // Remove ALL HTML/XML tags
                                            .replace(/```[\s\S]*?```/g, '') // Remove code blocks
                                            .replace(/\[\s*{[\s\S]*?}\s*\]/g, '') // Remove JSON arrays
                                            .replace(/###\s*/g, '### ') // Clean up markdown headers
                                            .replace(/\n{3,}/g, '\n\n') // Remove excessive newlines
                                            .replace(/\\n/g, '\n') // Fix escaped newlines
                                            .trim();

                                          if (!cleanReport) {
                                            return 'No report generated yet.';
                                          }

                                          return (
                                            <ReactMarkdown
                                              remarkPlugins={[remarkGfm, remarkMath]}
                                              rehypePlugins={[rehypeKatex, rehypeHighlight]}
                                              components={{
                                                // Headers with proper hierarchy and styling
                                                h1: ({ node, ...props }) => (
                                                  <h1 className="text-3xl font-bold mt-8 mb-6 pb-3 border-b-2"
                                                    style={{ color: '#135bec', borderColor: '#e5e7eb' }}
                                                    {...props} />
                                                ),
                                                h2: ({ node, ...props }) => (
                                                  <h2 className="text-2xl font-bold mt-8 mb-4"
                                                    style={{ color: '#135bec' }}
                                                    {...props} />
                                                ),
                                                h3: ({ node, ...props }) => (
                                                  <h3 className="text-xl font-semibold mt-6 mb-3"
                                                    style={{ color: '#111827' }}
                                                    {...props} />
                                                ),
                                                h4: ({ node, ...props }) => (
                                                  <h4 className="text-lg font-semibold mt-4 mb-2"
                                                    style={{ color: '#111827' }}
                                                    {...props} />
                                                ),

                                                // Paragraphs and text
                                                p: ({ node, ...props }) => (
                                                  <p className="leading-relaxed mb-4"
                                                    style={{ color: '#111827' }}
                                                    {...props} />
                                                ),
                                                strong: ({ node, ...props }) => (
                                                  <strong className="font-bold"
                                                    style={{ color: '#111827' }}
                                                    {...props} />
                                                ),
                                                em: ({ node, ...props }) => (
                                                  <em className="italic"
                                                    style={{ color: '#374151' }}
                                                    {...props} />
                                                ),

                                                // Lists
                                                ul: ({ node, ...props }) => (
                                                  <ul className="list-disc mb-6 space-y-2 ml-8 pl-2"
                                                    style={{ color: '#111827' }}
                                                    {...props} />
                                                ),
                                                ol: ({ node, ...props }) => (
                                                  <ol className="list-decimal mb-6 space-y-2 ml-8 pl-2"
                                                    style={{ color: '#111827' }}
                                                    {...props} />
                                                ),
                                                li: ({ node, ...props }) => (
                                                  <li className="leading-relaxed pl-2"
                                                    style={{ color: '#111827' }}
                                                    {...props} />
                                                ),

                                                // Blockquotes for emphasis
                                                blockquote: ({ node, ...props }) => (
                                                  <blockquote className="border-l-4 pl-6 my-6 italic"
                                                    style={{ borderColor: 'var(--color-primary)', color: 'var(--color-text-muted)' }}
                                                    {...props} />
                                                ),

                                                // Tables for data
                                                table: ({ node, ...props }) => (
                                                  <div className="overflow-x-auto my-6">
                                                    <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700" {...props} />
                                                  </div>
                                                ),
                                                thead: ({ node, ...props }) => (
                                                  <thead className="bg-gray-50 dark:bg-gray-800" {...props} />
                                                ),
                                                th: ({ node, ...props }) => (
                                                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider" {...props} />
                                                ),
                                                td: ({ node, ...props }) => (
                                                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300" {...props} />
                                                ),

                                                // Code blocks - minimal display
                                                code: ({ node, inline, ...props }: any) =>
                                                  inline ? (
                                                    <code className="px-1.5 py-0.5 rounded text-sm font-mono bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200" {...props} />
                                                  ) : (
                                                    <code className="block my-4 p-4 bg-gray-100 dark:bg-gray-900 rounded-lg overflow-x-auto text-sm font-mono text-gray-800 dark:text-gray-200" {...props} />
                                                  ),
                                                pre: ({ node, ...props }) => (
                                                  <pre className="my-4 p-4 bg-gray-100 dark:bg-gray-900 rounded-lg overflow-x-auto" {...props} />
                                                ),

                                                // Horizontal rules
                                                hr: ({ node, ...props }) => (
                                                  <hr className="my-8 border-t-2" style={{ borderColor: 'var(--color-border-light)' }} {...props} />
                                                ),

                                                // Links
                                                a: ({ node, ...props }) => (
                                                  <a className="text-blue-600 dark:text-blue-400 hover:underline" target="_blank" rel="noopener noreferrer" {...props} />
                                                ),
                                              }}
                                            >
                                              {cleanReport}
                                            </ReactMarkdown>
                                          );
                                        })()}
                                      </div>
                                    </div>
                                  </div>
                                </div>


                                {/* Raw Output View - Structured Code Display */}
                                {showRawOutput && (
                                  <div className="mt-6 border-t pt-6" style={{ borderColor: 'var(--color-border-light)' }}>
                                    <h4 className="text-md font-bold mb-4" style={{ color: 'var(--color-text-secondary)' }}>
                                      Raw Output Data
                                    </h4>
                                    <div className="bg-gray-900 dark:bg-gray-950 rounded-lg overflow-hidden">
                                      {/* Header bar like a code editor */}
                                      <div className="bg-gray-800 dark:bg-gray-900 px-4 py-2 flex items-center justify-between border-b border-gray-700">
                                        <div className="flex items-center gap-2">
                                          <span className="text-xs text-gray-400 font-mono">output.json</span>
                                          <span className="text-xs text-gray-500">•</span>
                                          <span className="text-xs text-gray-500">
                                            {JSON.stringify(taskOutput).length.toLocaleString()} bytes
                                          </span>
                                        </div>
                                        <button
                                          onClick={() => {
                                            const formattedJson = JSON.stringify(taskOutput, null, 2);
                                            navigator.clipboard.writeText(formattedJson);
                                          }}
                                          className="text-xs text-gray-400 hover:text-white transition-colors flex items-center gap-1"
                                        >
                                          <span className="material-symbols-outlined text-sm">content_copy</span>
                                          Copy
                                        </button>
                                      </div>
                                      {/* Code content with syntax highlighting */}
                                      <div className="p-4 overflow-x-auto max-h-96 overflow-y-auto">
                                        <pre className="text-xs font-mono leading-relaxed">
                                          <code className="language-json">
                                            {JSON.stringify(taskOutput, null, 2)
                                              .split('\n')
                                              .map((line, idx) => {
                                                // Basic JSON syntax highlighting
                                                const highlightedLine = line
                                                  .replace(/("[^"]+")(\s*:)/g, '<span style="color: #86efac;">$1</span>$2') // Keys in green
                                                  .replace(/:([\s]*)"([^"]*)"/g, ':$1<span style="color: #fbbf24;">"$2"</span>') // String values in yellow
                                                  .replace(/:\s*(true|false)/g, ': <span style="color: #c084fc;">$1</span>') // Booleans in purple
                                                  .replace(/:\s*(null)/g, ': <span style="color: #f87171;">$1</span>') // Null in red
                                                  .replace(/:\s*([0-9.]+)/g, ': <span style="color: #67e8f9;">$1</span>'); // Numbers in cyan

                                                return (
                                                  <div key={idx} className="flex">
                                                    <span className="select-none pr-4 text-gray-600" style={{ minWidth: '3ch' }}>
                                                      {idx + 1}
                                                    </span>
                                                    <span dangerouslySetInnerHTML={{ __html: highlightedLine }} />
                                                  </div>
                                                );
                                              })}
                                          </code>
                                        </pre>
                                      </div>
                                    </div>
                                  </div>
                                )}

                              </div>
                            );
                          })()
                          }
                        </div>
                      )}
                    </div>
                  )}

                  {/* Sidebar for Task History - Only show on output subtab */}
                  {taskHistory.length > 0 && resultsSubTab === 'output' && (
                    <div
                      className="border-l overflow-y-auto flex-shrink-0 transition-all duration-300"
                      style={{
                        borderColor: 'var(--color-border-dark)',
                        width: isHistoryCollapsed ? '60px' : '384px'
                      }}
                    >
                      <div className={isHistoryCollapsed ? "p-2" : "p-4"}>
                        {/* Header with toggle button */}
                        <div className="flex items-center justify-between mb-4">
                          {!isHistoryCollapsed && (
                            <h3 className="text-sm font-semibold uppercase tracking-wide" style={{ color: 'var(--color-text-muted)' }}>
                              Task History ({taskHistory.length})
                            </h3>
                          )}
                          <button
                            onClick={() => setIsHistoryCollapsed(!isHistoryCollapsed)}
                            className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-white/10 transition-colors"
                            title={isHistoryCollapsed ? "Expand history" : "Collapse history"}
                          >
                            <ChevronRight
                              className={`w-4 h-4 transition-transform duration-200 ${isHistoryCollapsed ? 'rotate-0' : 'rotate-180'}`}
                              style={{ color: 'var(--color-text-muted)' }}
                            />
                          </button>
                        </div>
                        <div className="space-y-3">
                          {taskHistory.map((task, _index) => {
                            const isSelected = selectedHistoryTask?.id === task.id;

                            // Extract the prompt from the task - could be in input, directive, query, or first human message
                            const prompt = (() => {
                              // First check task.user_input (from backend API - should be the user's actual prompt)
                              if (task.user_input && typeof task.user_input === 'string' && task.user_input.trim()) {
                                return task.user_input;
                              }

                              // Check top-level fields
                              const topLevelFields = ['directive', 'query', 'task_input', 'prompt', 'question', 'message'];
                              for (const field of topLevelFields) {
                                if ((task as any)[field] && typeof (task as any)[field] === 'string' && (task as any)[field].trim()) {
                                  return (task as any)[field];
                                }
                              }

                              // Try input field if it exists
                              if (task.input !== undefined && task.input !== null) {
                                // Try direct input if it's a string
                                if (typeof task.input === 'string' && task.input.trim()) {
                                  return task.input;
                                }

                                // Try to get from input object fields (most common)
                                if (typeof task.input === 'object') {
                                  // Check all common field names
                                  const possibleFields = ['directive', 'query', 'task', 'prompt', 'question', 'message', 'input', 'text'];
                                  for (const field of possibleFields) {
                                    if (task.input[field] && typeof task.input[field] === 'string' && task.input[field].trim()) {
                                      return task.input[field];
                                    }
                                  }

                                  // Try to find any string value in input
                                  const values = Object.values(task.input);
                                  const firstString = values.find(v => typeof v === 'string' && v.trim() && v.length > 10);
                                  if (firstString) {
                                    return firstString as string;
                                  }
                                }
                              }

                              // Try to get from the first human message in agent_messages
                              if (task.result?.agent_messages?.length > 0) {
                                const humanMessages = task.result.agent_messages.filter((m: any) => m.role === 'human');
                                if (humanMessages.length > 0) {
                                  const firstHuman = humanMessages[0];
                                  if (firstHuman?.content) {
                                    const content = typeof firstHuman.content === 'string'
                                      ? firstHuman.content
                                      : JSON.stringify(firstHuman.content);
                                    // Clean up the content
                                    const cleanContent = content
                                      .replace(/^Human:\s*/i, '')
                                      .replace(/^User:\s*/i, '')
                                      .trim();
                                    if (cleanContent && cleanContent !== '{}' && cleanContent !== '[]') {
                                      return cleanContent;
                                    }
                                  }
                                }
                              }

                              // Last resort - check if there's a formatted_input field
                              if (task.formatted_input && typeof task.formatted_input === 'string') {
                                return task.formatted_input;
                              }

                              return 'No prompt available';
                            })();

                            return (
                              <button
                                key={task.id}
                                onClick={() => {
                                  setSelectedHistoryTask(task);
                                  // If replay panel is already open, update the task being viewed
                                  if (showReplayPanel) {
                                    setReplayTaskId(task.id);
                                  }
                                }}
                                onContextMenu={(e) => {
                                  e.preventDefault();
                                  setTaskContextMenu({
                                    taskId: task.id,
                                    x: e.clientX,
                                    y: e.clientY
                                  });
                                }}
                                className={`w-full text-left ${isHistoryCollapsed ? 'p-2' : 'p-3'} rounded-lg border transition-all ${isSelected
                                  ? 'bg-primary/10 dark:bg-primary/20 border-primary shadow-md'
                                  : 'bg-white dark:bg-panel-dark border-gray-200 dark:border-gray-700 hover:border-primary/50'
                                  } hover:shadow-md`}
                                title={isHistoryCollapsed ? `Task #${task.id}: ${prompt.substring(0, 50)}...` : ''}
                              >
                                {isHistoryCollapsed ? (
                                  /* Collapsed View - Icon only */
                                  <div className="flex flex-col items-center gap-1">
                                    <span className={`text-xs px-1.5 py-0.5 rounded-full ${task.status === 'COMPLETED' ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' :
                                      task.status === 'FAILED' ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400' :
                                        'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                                      }`}>
                                      {task.status === 'COMPLETED' ? '✓' : task.status === 'FAILED' ? '✗' : '•'}
                                    </span>
                                    <span className="text-[10px] font-mono" style={{ color: 'var(--color-text-muted)' }}>
                                      #{task.id}
                                    </span>
                                  </div>
                                ) : (
                                  /* Expanded View - Full details */
                                  <>
                                    {/* Task Header */}
                                    <div className="flex items-center justify-between mb-2">
                                      <span className="text-sm font-bold" style={{ color: 'var(--color-text-primary)' }}>
                                        Task #{task.id}
                                      </span>
                                      <span className={`text-xs px-2 py-0.5 rounded-full ${task.status === 'COMPLETED' ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' :
                                        task.status === 'FAILED' ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400' :
                                          'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                                        }`}>
                                        {task.status === 'COMPLETED' ? '✓' : task.status === 'FAILED' ? '✗' : '•'}
                                      </span>
                                    </div>

                                    {/* Prompt Preview */}
                                    <div className="mb-2">
                                      <div className="text-xs font-medium mb-1" style={{ color: 'var(--color-text-muted)' }}>
                                        Prompt:
                                      </div>
                                      <div className="text-xs line-clamp-2 italic" style={{ color: 'var(--color-text-primary)', opacity: 0.9 }}>
                                        "{prompt.substring(0, 100)}{prompt.length > 100 ? '...' : ''}"
                                      </div>
                                    </div>

                                    {/* Metadata Row */}
                                    <div className="flex items-center justify-between text-xs" style={{ color: 'var(--color-text-muted)' }}>
                                      {/* Date and Time */}
                                      {task.created_at && (
                                        <div>
                                          {new Date(task.created_at).toLocaleDateString()} {new Date(task.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                        </div>
                                      )}

                                      {/* Duration */}
                                      {task.duration_seconds && (
                                        <div className="font-medium">
                                          {task.duration_seconds < 60
                                            ? `${Math.round(task.duration_seconds)}s`
                                            : `${Math.floor(task.duration_seconds / 60)}m ${Math.round(task.duration_seconds % 60)}s`
                                          }
                                        </div>
                                      )}
                                    </div>
                                  </>
                                )}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Memory Subtab */}
                  {resultsSubTab === 'memory' && currentWorkflowId && (
                    <div className="flex-1 overflow-hidden">
                      <MemoryView workflowId={currentWorkflowId} nodes={nodes} />
                    </div>
                  )}

                  {/* Files Subtab */}
                  {resultsSubTab === 'files' && (
                    <div className="flex-1 overflow-y-auto p-6">
                      {filesLoading ? (
                        <div className="flex items-center justify-center py-16">
                          <div className="text-center">
                            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4" style={{ borderColor: 'var(--color-primary)' }}></div>
                            <p className="text-sm text-gray-600 dark:text-text-muted">Loading files...</p>
                          </div>
                        </div>
                      ) : filesError ? (
                        <div className="flex flex-col items-center justify-center py-16 text-center">
                          <FileIcon className="w-16 h-16 text-red-300 dark:text-red-900/30 mb-4" />
                          <p className="text-lg font-medium text-red-600 dark:text-red-400">
                            Failed to load files
                          </p>
                          <p className="text-sm text-gray-500 dark:text-text-muted/70 mt-2">
                            {filesError}
                          </p>
                          <button
                            onClick={fetchFiles}
                            className="mt-4 px-4 py-2 rounded-lg bg-primary/10 hover:bg-primary/20 transition-colors text-sm font-medium"
                            style={{ color: 'var(--color-primary)' }}
                          >
                            Retry
                          </button>
                        </div>
                      ) : files.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-16 text-center">
                          <FolderOpen className="w-16 h-16 text-gray-300 dark:text-text-muted/30 mb-4" />
                          <p className="text-lg font-medium text-gray-600 dark:text-text-muted">
                            No files generated
                          </p>
                          <p className="text-sm text-gray-500 dark:text-text-muted/70 mt-2">
                            This workflow didn't create any output files.
                          </p>
                        </div>
                      ) : (
                        <>
                          <div className="mb-4">
                            <p className="text-sm text-gray-600 dark:text-text-muted">
                              Files created by agents during workflow execution. All files are stored in the workspace directory.
                            </p>
                          </div>

                          <div className="space-y-2">
                            {files.map((file, index) => (
                              <div
                                key={index}
                                className="flex items-center justify-between p-4 rounded-lg border border-gray-200 dark:border-border-dark hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
                              >
                                <div className="flex items-center gap-3 flex-1 min-w-0">
                                  <div className="p-2 rounded-lg bg-primary/10" style={{ color: 'var(--color-primary)' }}>
                                    <FileIcon className="w-5 h-5" />
                                  </div>
                                  <div className="flex-1 min-w-0">
                                    <p className="font-medium text-gray-900 dark:text-white truncate">
                                      {file.filename}
                                    </p>
                                    <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-text-muted mt-1">
                                      <span>{file.size_human}</span>
                                      <span>•</span>
                                      <span>{new Date(file.modified_at).toLocaleString()}</span>
                                      {file.extension && (
                                        <>
                                          <span>•</span>
                                          <span className="uppercase">{file.extension.replace('.', '')}</span>
                                        </>
                                      )}
                                    </div>
                                  </div>
                                </div>

                                <button
                                  onClick={() => handleDownloadFile(file.filename)}
                                  className="ml-4 px-3 py-2 rounded-lg bg-gray-100 dark:bg-white/5 hover:bg-gray-200 dark:hover:bg-white/10 transition-colors flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-text-muted"
                                  title="Download file"
                                >
                                  <Download className="w-4 h-4" />
                                  Download
                                </button>
                              </div>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </div>

                {/* Execution Log Replay Panel */}
                <LiveExecutionPanel
                  isVisible={showReplayPanel}
                  events={replayEvents}
                  latestEvent={replayEvents.length > 0 ? replayEvents[replayEvents.length - 1] : null}
                  onClose={() => {
                    setShowReplayPanel(false);
                    setReplayTaskId(null); // Clear replay task when closing
                  }}
                  isReplay={true}
                  executionStatus={executionStatus}
                  workflowMetrics={undefined}
                  userPrompt={undefined}
                  workflowName={workflowName}
                />
              </div>
            </div>
          )}

          {/* Execution Configuration Dialog */}
          {showExecutionDialog && activeTab === 'studio' && (
            <div className="fixed inset-0 flex items-center justify-center z-50 cursor-pointer" style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }} onClick={() => setShowExecutionDialog(false)}>
              <div className="rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto" style={{ backgroundColor: 'var(--color-panel-dark)' }} onClick={(e) => e.stopPropagation()}>
                <h3 className="text-xl font-bold mb-4" style={{ color: 'var(--color-text-primary)' }}>
                  Run Workflow
                </h3>

                <div className="space-y-4">
                  {/* Prompt Input */}
                  <div>
                    <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                      What should this workflow do?
                    </label>
                    <textarea
                      className="w-full px-3 py-2 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
                      style={{
                        backgroundColor: 'white',
                        color: '#1f2937',
                        borderColor: 'var(--color-border-dark)'
                      }}
                      rows={5}
                      placeholder="Enter your task or prompt here..."
                      value={executionConfig.directive}
                      onChange={(e) => setExecutionConfig({
                        ...executionConfig,
                        directive: e.target.value,
                        query: e.target.value,
                        task: e.target.value,
                      })}
                      autoFocus
                    />
                  </div>

                  {/* Advanced Options Toggle */}
                  <button
                    onClick={() => setShowAdvancedOptions(!showAdvancedOptions)}
                    className="text-sm hover:underline flex items-center gap-1"
                    style={{ color: 'var(--color-primary)' }}
                  >
                    <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>
                      {showAdvancedOptions ? 'expand_less' : 'expand_more'}
                    </span>
                    {showAdvancedOptions ? 'Hide' : 'Show'} Advanced Options
                  </button>

                  {/* Advanced Options */}
                  {showAdvancedOptions && (
                    <div className="space-y-4 pt-2 border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
                      {/* Additional Context */}
                      <div>
                        <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                          Additional Context (Optional)
                        </label>
                        <textarea
                          className="w-full px-3 py-2 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
                          style={{
                            backgroundColor: 'white',
                            color: '#1f2937',
                            borderColor: 'var(--color-border-dark)'
                          }}
                          rows={3}
                          placeholder="Add any background information, constraints, or context..."
                          value={additionalContext}
                          onChange={(e) => setAdditionalContext(e.target.value)}
                        />
                      </div>

                      {/* Context Documents (RAG) */}
                      <div>
                        <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                          Context Documents (RAG)
                        </label>
                        {availableDocuments.length > 0 ? (
                          <div className="max-h-40 overflow-y-auto border rounded-md p-2" style={{
                            borderColor: 'var(--color-border-dark)',
                            backgroundColor: 'var(--color-background-dark)'
                          }}>
                            {availableDocuments.map((doc) => (
                              <label
                                key={doc.id}
                                className="flex items-center gap-2 py-1.5 px-2 rounded cursor-pointer hover:bg-white/5"
                              >
                                <input
                                  type="checkbox"
                                  checked={contextDocuments.includes(doc.id)}
                                  onChange={(e) => {
                                    if (e.target.checked) {
                                      setContextDocuments([...contextDocuments, doc.id]);
                                    } else {
                                      setContextDocuments(contextDocuments.filter(id => id !== doc.id));
                                    }
                                  }}
                                  className="rounded"
                                  style={{ accentColor: 'var(--color-primary)' }}
                                />
                                <span className="text-sm flex-1 truncate" style={{ color: 'var(--color-text-primary)' }}>
                                  {doc.name}
                                </span>
                                <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                                  {doc.document_type}
                                </span>
                              </label>
                            ))}
                          </div>
                        ) : (
                          <div className="text-sm italic py-2" style={{ color: 'var(--color-text-muted)' }}>
                            No documents available. Upload documents in the Knowledge Base first.
                          </div>
                        )}
                        <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                          Select documents from the Knowledge Base to use as context
                        </p>
                      </div>

                      {/* Max Retries */}
                      <div>
                        <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                          Max Retries
                        </label>
                        <input
                          type="number"
                          min="0"
                          max="10"
                          className="w-full px-3 py-2 border rounded-md focus:ring-2 focus:border-transparent"
                          style={{
                            backgroundColor: 'var(--color-background-dark)',
                            color: 'var(--color-text-primary)',
                            borderColor: 'var(--color-border-dark)'
                          }}
                          value={executionConfig.max_retries}
                          onChange={(e) => setExecutionConfig({
                            ...executionConfig,
                            max_retries: parseInt(e.target.value) || 0,
                          })}
                        />
                        <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                          Number of times to retry failed steps
                        </p>
                      </div>
                    </div>
                  )}
                </div>

                {/* Action Buttons */}
                <div className="flex gap-3 mt-6">
                  <button
                    onClick={() => setShowExecutionDialog(false)}
                    className="flex-1 px-4 py-2 border rounded-md transition-colors"
                    style={{
                      borderColor: 'var(--color-border-dark)',
                      color: 'var(--color-text-primary)'
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={executeWorkflow}
                    disabled={!executionConfig.directive.trim()}
                    className="flex-1 px-4 py-2 rounded-md transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
                    style={{
                      backgroundColor: 'var(--color-primary)',
                      color: '#ffffff'
                    }}
                  >
                    Run Workflow
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Enhanced Live Monitoring Panel with SSE Streaming - Commented out since we use toasts now */}
          {/* <EnhancedLiveMonitoringPanel
        workflowId={currentWorkflowId}
        taskId={currentTaskId}
        isVisible={monitoringVisible}
        onToggle={() => setMonitoringVisible(!monitoringVisible)}
        onStatusChange={handleWorkflowStatusChange}
        events={workflowEvents}
        isConnected={latestEvent !== null}
        error={null}
      /> */}


          {/* Save Workflow Modal */}
          {showSaveModal && (
            <div
              className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
              onClick={() => {
                setShowSaveModal(false);
                setSaveWorkflowName('');
              }}
            >
              <div
                className="rounded-lg shadow-xl p-6 max-w-md w-full mx-4"
                style={{
                  backgroundColor: 'var(--color-panel-dark)',
                  border: '1px solid var(--color-border-dark)',
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <h2
                  className="text-xl font-semibold mb-4"
                  style={{ color: 'var(--color-text-primary)' }}
                >
                  Save Workflow
                </h2>
                <p
                  className="mb-4 text-sm"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  Enter a name for your workflow:
                </p>
                <input
                  type="text"
                  value={saveWorkflowName}
                  onChange={(e) => setSaveWorkflowName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && saveWorkflowName.trim()) {
                      handleSaveWorkflowConfirm();
                    } else if (e.key === 'Escape') {
                      setShowSaveModal(false);
                      setSaveWorkflowName('');
                    }
                  }}
                  placeholder="Enter workflow name..."
                  autoFocus
                  className="w-full px-3 py-2 rounded-lg mb-4 border focus:outline-none focus:ring-2"
                  style={{
                    backgroundColor: 'var(--color-input-background)',
                    borderColor: 'var(--color-border-dark)',
                    color: 'var(--color-text-primary)',
                  }}
                />
                <div className="flex gap-2 justify-end">
                  <button
                    onClick={() => {
                      setShowSaveModal(false);
                      setSaveWorkflowName('');
                    }}
                    className="px-4 py-2 rounded-lg border transition-colors"
                    style={{
                      borderColor: 'var(--color-border-dark)',
                      color: 'var(--color-text-muted)',
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSaveWorkflowConfirm}
                    disabled={!saveWorkflowName.trim()}
                    className="px-4 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    style={{
                      backgroundColor: 'var(--color-primary)',
                      color: 'white',
                    }}
                  >
                    Save
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Save to Agent Library Modal */}
          {showSaveToLibraryModal && (
            <div
              className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
              onClick={() => {
                setShowSaveToLibraryModal(false);
                setSaveToLibraryData(null);
                setAgentLibraryName('');
                setAgentLibraryDescription('');
              }}
            >
              <div
                className="rounded-lg shadow-xl p-6 max-w-md w-full mx-4"
                style={{
                  backgroundColor: 'var(--color-panel-dark)',
                  border: '1px solid var(--color-border-dark)',
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <h2
                  className="text-xl font-semibold mb-4"
                  style={{ color: 'var(--color-text-primary)' }}
                >
                  Save to Agent Library
                </h2>

                <div className="space-y-4">
                  <div>
                    <label
                      className="block text-sm font-medium mb-2"
                      style={{ color: 'var(--color-text-primary)' }}
                    >
                      Agent Name
                    </label>
                    <input
                      type="text"
                      value={agentLibraryName}
                      onChange={(e) => setAgentLibraryName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && agentLibraryName.trim()) {
                          handleConfirmSaveToLibrary();
                        } else if (e.key === 'Escape') {
                          setShowSaveToLibraryModal(false);
                          setSaveToLibraryData(null);
                          setAgentLibraryName('');
                          setAgentLibraryDescription('');
                        }
                      }}
                      placeholder="Enter agent name..."
                      autoFocus
                      className="w-full px-3 py-2 rounded-lg border focus:outline-none focus:ring-2"
                      style={{
                        backgroundColor: 'var(--color-input-background)',
                        borderColor: 'var(--color-border-dark)',
                        color: 'var(--color-text-primary)',
                      }}
                    />
                  </div>

                  <div>
                    <label
                      className="block text-sm font-medium mb-2"
                      style={{ color: 'var(--color-text-primary)' }}
                    >
                      Description (optional)
                    </label>
                    <textarea
                      value={agentLibraryDescription}
                      onChange={(e) => setAgentLibraryDescription(e.target.value)}
                      placeholder="Describe what this agent does..."
                      rows={3}
                      className="w-full px-3 py-2 rounded-lg border focus:outline-none focus:ring-2 resize-none"
                      style={{
                        backgroundColor: 'var(--color-input-background)',
                        borderColor: 'var(--color-border-dark)',
                        color: 'var(--color-text-primary)',
                      }}
                    />
                  </div>
                </div>

                <div className="flex gap-2 justify-end mt-6">
                  <button
                    onClick={() => {
                      setShowSaveToLibraryModal(false);
                      setSaveToLibraryData(null);
                      setAgentLibraryName('');
                      setAgentLibraryDescription('');
                    }}
                    className="px-4 py-2 rounded-lg border transition-colors"
                    style={{
                      borderColor: 'var(--color-border-dark)',
                      color: 'var(--color-text-muted)',
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleConfirmSaveToLibrary}
                    disabled={!agentLibraryName.trim()}
                    className="px-4 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    style={{
                      backgroundColor: 'var(--color-primary)',
                      color: 'white',
                    }}
                  >
                    Save to Library
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Chat with Unsaved Agent Warning Modal */}
          {showChatWarningModal && (
            <div
              className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
              onClick={() => setShowChatWarningModal(false)}
            >
              <div
                className="rounded-lg shadow-xl p-6 max-w-md w-full mx-4"
                style={{
                  backgroundColor: 'var(--color-panel-dark)',
                  border: '1px solid var(--color-border-dark)',
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-start gap-3 mb-4">
                  <div className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center" style={{
                    backgroundColor: 'rgba(251, 191, 36, 0.1)',
                  }}>
                    <span className="material-symbols-outlined" style={{ color: '#f59e0b', fontSize: '24px' }}>
                      warning
                    </span>
                  </div>
                  <div>
                    <h2
                      className="text-lg font-semibold mb-2"
                      style={{ color: 'var(--color-text-primary)' }}
                    >
                      Agent Not Saved to Library
                    </h2>
                    <p
                      className="text-sm"
                      style={{ color: 'var(--color-text-primary)' }}
                    >
                      To chat with this agent, you need to save it to the Agent Library first. This allows you to have persistent conversations with the agent.
                    </p>
                  </div>
                </div>

                <div className="flex gap-2 justify-end">
                  <button
                    onClick={() => setShowChatWarningModal(false)}
                    className="px-4 py-2 rounded-lg transition-colors"
                    style={{
                      backgroundColor: 'var(--color-primary)',
                      color: 'white',
                    }}
                  >
                    Got it
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Save Version Modal */}
          {showVersionModal && (
            <div
              className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
              onClick={() => {
                setShowVersionModal(false);
                setVersionNotes('');
              }}
            >
              <div
                className="rounded-lg shadow-xl p-6 max-w-md w-full mx-4"
                style={{
                  backgroundColor: 'var(--color-panel-dark)',
                  border: '1px solid var(--color-border-dark)',
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <h2
                  className="text-xl font-semibold mb-4"
                  style={{ color: 'var(--color-text-primary)' }}
                >
                  Save New Version
                </h2>
                <p
                  className="mb-4 text-sm"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  Create a snapshot of your current workflow configuration. Add notes to describe what changed:
                </p>
                <textarea
                  value={versionNotes}
                  onChange={(e) => setVersionNotes(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Escape') {
                      setShowVersionModal(false);
                      setVersionNotes('');
                    }
                  }}
                  placeholder="What changed in this version? (optional)"
                  rows={4}
                  autoFocus
                  className="w-full px-3 py-2 rounded-lg mb-4 border focus:outline-none focus:ring-2"
                  style={{
                    backgroundColor: 'var(--color-input-background)',
                    borderColor: 'var(--color-border-dark)',
                    color: 'var(--color-text-primary)',
                  }}
                />
                <div className="flex gap-2 justify-end">
                  <button
                    onClick={() => {
                      setShowVersionModal(false);
                      setVersionNotes('');
                    }}
                    className="px-4 py-2 rounded-lg border transition-colors"
                    style={{
                      borderColor: 'var(--color-border-dark)',
                      color: 'var(--color-text-muted)',
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSaveVersionConfirm}
                    className="px-4 py-2 rounded-lg transition-colors"
                    style={{
                      backgroundColor: 'var(--color-primary)',
                      color: 'white',
                    }}
                  >
                    Create Version
                  </button>
                </div>
              </div>
            </div>
          )}

        </div>

        {/* Debug Workflow Modal */}
        {showDebugModal && debugData && (
          <div
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
            onClick={() => setShowDebugModal(false)}
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
                  onClick={() => setShowDebugModal(false)}
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
                {debugData.nodes.map((node: any) => (
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
                  {debugData.available_custom_tools.map((tool: any) => (
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
                  onClick={() => {
                    navigator.clipboard.writeText(JSON.stringify(debugData.raw_configuration, null, 2));
                    showSuccess('Configuration copied to clipboard!');
                  }}
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
        )}

        {/* Notification Modal */}
        <NotificationModal />

        {/* Task Context Menu */}
        {taskContextMenu && (
          <div
            className="fixed z-[9999] bg-white dark:bg-panel-dark border border-gray-200 dark:border-border-dark rounded-lg shadow-lg py-1 min-w-[160px]"
            style={{
              left: `${taskContextMenu.x}px`,
              top: `${taskContextMenu.y}px`,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => handleDeleteTask(taskContextMenu.taskId)}
              className="w-full text-left px-4 py-2 text-sm hover:bg-gray-100 dark:hover:bg-white/10 transition-colors flex items-center gap-2 text-red-600 dark:text-red-400"
            >
              <Trash2 className="w-4 h-4" />
              Delete Task
            </button>
          </div>
        )}

        {/* Node Context Menu */}
        {nodeContextMenu && (
          <>
            {/* Backdrop to catch clicks and prevent transparency */}
            <div
              className="fixed inset-0 z-[9998]"
              onClick={() => setNodeContextMenu(null)}
            />
            <div
              className="fixed z-[9999] border rounded-lg shadow-2xl py-1 min-w-[200px]"
              style={{
                left: `${nodeContextMenu.x}px`,
                top: `${nodeContextMenu.y}px`,
                backgroundColor: '#ffffff',
                borderColor: 'var(--color-border-dark)',
              }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Chat with Agent */}
              <button
                onClick={() => handleChatWithAgent(nodeContextMenu.nodeId, nodeContextMenu.nodeData)}
                className="w-full text-left px-4 py-2.5 text-sm transition-all flex items-center gap-3 rounded-t-lg"
                style={{ color: 'var(--color-text-primary)', backgroundColor: '#ffffff' }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--color-primary)';
                  e.currentTarget.style.color = '#ffffff';
                  const icon = e.currentTarget.querySelector('svg');
                  if (icon) (icon as HTMLElement).style.color = '#ffffff';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#ffffff';
                  e.currentTarget.style.color = 'var(--color-text-primary)';
                  const icon = e.currentTarget.querySelector('svg');
                  if (icon) (icon as HTMLElement).style.color = 'var(--color-primary)';
                }}
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
                onClick={() => handleSaveToAgentLibrary(nodeContextMenu.nodeId, nodeContextMenu.nodeData)}
                className="w-full text-left px-4 py-2.5 text-sm transition-all flex items-center gap-3"
                style={{ color: 'var(--color-text-primary)', backgroundColor: '#ffffff' }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--color-primary)';
                  e.currentTarget.style.color = '#ffffff';
                  const icon = e.currentTarget.querySelector('svg');
                  if (icon) (icon as HTMLElement).style.color = '#ffffff';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#ffffff';
                  e.currentTarget.style.color = 'var(--color-text-primary)';
                  const icon = e.currentTarget.querySelector('svg');
                  if (icon) (icon as HTMLElement).style.color = 'var(--color-primary)';
                }}
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
                onClick={() => handleCopyLangChainCode(nodeContextMenu.nodeId, nodeContextMenu.nodeData)}
                className="w-full text-left px-4 py-2 text-sm transition-all flex items-center gap-2"
                style={{ color: 'var(--color-text-primary)', backgroundColor: '#ffffff' }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--color-primary)';
                  e.currentTarget.style.color = '#ffffff';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#ffffff';
                  e.currentTarget.style.color = 'var(--color-text-primary)';
                }}
              >
                <FileIcon className="w-4 h-4" />
                Copy LangChain Code
              </button>

              {/* Duplicate Node */}
              <button
                onClick={() => handleDuplicateNode(nodeContextMenu.nodeId, nodeContextMenu.nodeData)}
                className="w-full text-left px-4 py-2 text-sm transition-all flex items-center gap-2"
                style={{ color: 'var(--color-text-primary)', backgroundColor: '#ffffff' }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--color-primary)';
                  e.currentTarget.style.color = '#ffffff';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#ffffff';
                  e.currentTarget.style.color = 'var(--color-text-primary)';
                }}
              >
                <Copy className="w-4 h-4" />
                Duplicate Node
              </button>

              {/* Configure Node */}
              <button
                onClick={() => handleConfigureNode(nodeContextMenu.nodeId)}
                className="w-full text-left px-4 py-2 text-sm transition-all flex items-center gap-2"
                style={{ color: 'var(--color-text-primary)', backgroundColor: '#ffffff' }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--color-primary)';
                  e.currentTarget.style.color = '#ffffff';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#ffffff';
                  e.currentTarget.style.color = 'var(--color-text-primary)';
                }}
              >
                <Settings className="w-4 h-4" />
                Configure
              </button>

              {/* View Metrics */}
              {nodeContextMenu.nodeData.executionStatus?.tokenCost && (
                <button
                  onClick={() => {
                    handleConfigureNode(nodeContextMenu.nodeId);
                    setNodeContextMenu(null);
                  }}
                  className="w-full text-left px-4 py-2 text-sm transition-all flex items-center gap-2"
                  style={{ color: 'var(--color-text-primary)', backgroundColor: '#ffffff' }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--color-primary)';
                    e.currentTarget.style.color = '#ffffff';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = '#ffffff';
                    e.currentTarget.style.color = 'var(--color-text-primary)';
                  }}
                >
                  <Brain className="w-4 h-4" />
                  <div className="flex-1 flex items-center justify-between">
                    <span>View Metrics</span>
                    <span className="text-xs font-mono">
                      {nodeContextMenu.nodeData.executionStatus.tokenCost.costString}
                    </span>
                  </div>
                </button>
              )}

              {/* Divider */}
              <div className="h-px my-1" style={{ backgroundColor: 'var(--color-border-dark)' }} />

              {/* Delete Node */}
              <button
                onClick={() => handleDeleteNode(nodeContextMenu.nodeId)}
                className="w-full text-left px-4 py-2 text-sm transition-all flex items-center gap-2"
                style={{ color: '#dc2626', backgroundColor: '#ffffff' }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#dc2626';
                  e.currentTarget.style.color = '#ffffff';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#ffffff';
                  e.currentTarget.style.color = '#dc2626';
                }}
              >
                <Trash2 className="w-4 h-4" />
                Delete Node
              </button>
            </div>
          </>
        )}

        {showConflictDialog && conflictData && (
          <ConflictDialog
            open={showConflictDialog}
            resourceType="Workflow"
            resourceName={workflowName}
            localData={conflictData.localData}
            remoteData={conflictData.remoteData}
            onResolve={handleConflictResolve}
            onClose={() => {
              setShowConflictDialog(false);
              setConflictData(null);
            }}
          />
        )}
      </div>
    </WorkflowCanvasContext.Provider>
  );
});

WorkflowCanvas.displayName = 'WorkflowCanvas';

export default WorkflowCanvas;
