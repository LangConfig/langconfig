/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo, useState, useRef, useEffect, useMemo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { MessageSquare } from 'lucide-react';
import { useAvailableModels } from '../../../../../hooks/useAvailableModels';
import { getModelDisplayName } from '../../../../../lib/model-utils';
import type { NodeExecutionStatus } from '../../../../../hooks/useNodeExecutionStatus';
import { useWorkflowCanvasContext } from '../context';

/**
 * Custom Node Component with enhanced visuals and execution status
 * Memoized for performance during canvas operations
 */
const CustomNode = memo(function CustomNode({ id, data, selected }: NodeProps) {
  // Always prefer data.config.model over data.model for display
  const modelName = data.config?.model || data.model;
  const agentType = data.agentType || 'default';
  const executionStatus = data.executionStatus as NodeExecutionStatus | undefined;

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
        const customToolCount = data.config?.custom_tools?.length || 0;
        const toolCount = nativeToolCount + builtInToolCount + customToolCount;

        if (toolCount === 0) return null;

        return (
          <div
            className="absolute top-2 right-2 flex items-center gap-1"
            style={{
              filter: 'drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3))',
            }}
            title={`Tools: ${nativeToolCount} Native${customToolCount > 0 ? `, ${customToolCount} Custom` : ''}`}
          >
            <span
              className="material-symbols-outlined"
              style={{
                fontSize: '16px',
                color: customToolCount > 0 ? '#f59e0b' : (isDarkTheme ? 'var(--color-primary)' : 'var(--color-background-light)'),
                fontWeight: 600
              }}
            >
              construction
            </span>
            <span
              className="text-sm font-bold"
              style={{
                color: customToolCount > 0 ? '#f59e0b' : (isDarkTheme ? 'var(--color-primary)' : 'var(--color-background-light)')
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

export default CustomNode;
