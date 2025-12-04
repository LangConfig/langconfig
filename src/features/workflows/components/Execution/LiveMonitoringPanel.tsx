/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect, useRef } from 'react';
import { ChevronUp, ChevronDown } from 'lucide-react';

type TabType = 'status' | 'logs' | 'outputs' | 'metrics';

interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'success';
  message: string;
}

interface ExecutionStatus {
  state: 'idle' | 'running' | 'completed' | 'failed';
  currentNode?: string;
  progress: number;
  startTime?: string;
  duration?: string;
}

interface Metrics {
  tokensUsed: number;
  estimatedCost: number;
  executionTime: string;
  nodesExecuted: number;
  totalNodes: number;
}

interface LiveMonitoringPanelProps {
  isVisible: boolean;
  onToggle: () => void;
  executionStatus: ExecutionStatus;
  logs: LogEntry[];
  outputs: Record<string, any>;
  metrics: Metrics;
}

export default function LiveMonitoringPanel({
  isVisible,
  onToggle,
  executionStatus,
  logs,
  outputs,
  metrics
}: LiveMonitoringPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>('status');
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (activeTab === 'logs' && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, activeTab]);

  const getStatusColor = (state: ExecutionStatus['state']) => {
    switch (state) {
      case 'running':
        return 'text-blue-600 dark:text-blue-400';
      case 'completed':
        return 'text-green-600 dark:text-green-400';
      case 'failed':
        return 'text-red-600 dark:text-red-400';
      default:
        return 'text-gray-600 dark:text-gray-400';
    }
  };

  const getStatusIcon = (state: ExecutionStatus['state']) => {
    switch (state) {
      case 'running':
        return 'progress_activity';
      case 'completed':
        return 'check_circle';
      case 'failed':
        return 'error';
      default:
        return 'radio_button_unchecked';
    }
  };

  const getLevelColor = (level: LogEntry['level']) => {
    switch (level) {
      case 'error':
        return 'text-red-600 dark:text-red-400';
      case 'warning':
        return 'text-yellow-600 dark:text-yellow-400';
      case 'success':
        return 'text-green-600 dark:text-green-400';
      default:
        return 'text-gray-600 dark:text-gray-300';
    }
  };

  const getLevelIcon = (level: LogEntry['level']) => {
    switch (level) {
      case 'error':
        return 'error';
      case 'warning':
        return 'warning';
      case 'success':
        return 'check_circle';
      default:
        return 'info';
    }
  };

  return (
    <div
      className={`bg-white dark:bg-panel-dark border-t border-gray-200 dark:border-border-dark transition-all duration-300 ${
        isVisible ? 'h-48' : 'h-10'
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 dark:border-border-dark bg-gray-50 dark:bg-background-dark">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-sm">
              monitoring
            </span>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
              Live Monitoring
            </h3>
          </div>

          {isVisible && (
            <nav className="flex items-center gap-1">
              {(['status', 'logs', 'outputs', 'metrics'] as TabType[]).map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                    activeTab === tab
                      ? 'bg-primary text-white'
                      : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-white/5'
                  }`}
                >
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </nav>
          )}
        </div>

        <button
          onClick={onToggle}
          className="p-1 hover:bg-gray-200 dark:hover:bg-white/10 rounded transition-colors"
        >
          {isVisible ? (
            <ChevronDown className="w-4 h-4 text-gray-500 dark:text-gray-400" />
          ) : (
            <ChevronUp className="w-4 h-4 text-gray-500 dark:text-gray-400" />
          )}
        </button>
      </div>

      {/* Content */}
      {isVisible && (
        <div className="h-[calc(100%-2.5rem)] overflow-y-auto p-4">
          {/* Status Tab */}
          {activeTab === 'status' && (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <span className={`material-symbols-outlined ${getStatusColor(executionStatus.state)} ${
                  executionStatus.state === 'running' ? 'animate-spin' : ''
                }`}>
                  {getStatusIcon(executionStatus.state)}
                </span>
                <div>
                  <p className="text-sm font-semibold text-gray-900 dark:text-white">
                    {executionStatus.state === 'idle' && 'Ready to Execute'}
                    {executionStatus.state === 'running' && 'Execution in Progress'}
                    {executionStatus.state === 'completed' && 'Execution Completed'}
                    {executionStatus.state === 'failed' && 'Execution Failed'}
                  </p>
                  {executionStatus.currentNode && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      Current: {executionStatus.currentNode}
                    </p>
                  )}
                </div>
              </div>

              {executionStatus.state !== 'idle' && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                      Progress
                    </span>
                    <span className="text-xs font-semibold text-primary">
                      {executionStatus.progress}%
                    </span>
                  </div>
                  <div className="w-full h-2 bg-gray-200 dark:bg-background-dark rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary transition-all duration-300"
                      style={{ width: `${executionStatus.progress}%` }}
                    />
                  </div>
                </div>
              )}

              {executionStatus.startTime && (
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Start Time</span>
                    <p className="font-medium text-gray-900 dark:text-white mt-0.5">
                      {executionStatus.startTime}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Duration</span>
                    <p className="font-medium text-gray-900 dark:text-white mt-0.5">
                      {executionStatus.duration || '0s'}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Logs Tab */}
          {activeTab === 'logs' && (
            <div className="space-y-1 font-mono text-xs">
              {logs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <span className="material-symbols-outlined text-gray-300 dark:text-gray-600 text-3xl mb-2">
                    article
                  </span>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    No logs yet. Start execution to see logs.
                  </p>
                </div>
              ) : (
                <>
                  {logs.map((log, idx) => (
                    <div key={idx} className="flex items-start gap-2 py-1 px-2 hover:bg-gray-50 dark:hover:bg-white/5 rounded">
                      <span className="text-gray-400 dark:text-gray-500 shrink-0">
                        {log.timestamp}
                      </span>
                      <span className={`material-symbols-outlined text-sm mt-0.5 ${getLevelColor(log.level)}`}>
                        {getLevelIcon(log.level)}
                      </span>
                      <span className={getLevelColor(log.level)}>
                        {log.message}
                      </span>
                    </div>
                  ))}
                  <div ref={logsEndRef} />
                </>
              )}
            </div>
          )}

          {/* Outputs Tab */}
          {activeTab === 'outputs' && (
            <div className="space-y-3">
              {Object.keys(outputs).length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <span className="material-symbols-outlined text-gray-300 dark:text-gray-600 text-3xl mb-2">
                    output
                  </span>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    No outputs yet. Execute workflow to see results.
                  </p>
                </div>
              ) : (
                Object.entries(outputs).map(([key, value]) => (
                  <div key={key} className="bg-gray-50 dark:bg-background-dark rounded-lg p-3">
                    <p className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">
                      {key}
                    </p>
                    <pre className="text-xs text-gray-600 dark:text-gray-400 overflow-x-auto">
                      {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
                    </pre>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Metrics Tab */}
          {activeTab === 'metrics' && (
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-50 dark:bg-background-dark rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <span className="material-symbols-outlined text-primary text-sm">
                    token
                  </span>
                  <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                    Tokens Used
                  </span>
                </div>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {metrics.tokensUsed.toLocaleString()}
                </p>
              </div>

              <div className="bg-gray-50 dark:bg-background-dark rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <span className="material-symbols-outlined text-green-600 dark:text-green-400 text-sm">
                    payments
                  </span>
                  <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                    Estimated Cost
                  </span>
                </div>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  ${metrics.estimatedCost.toFixed(4)}
                </p>
              </div>

              <div className="bg-gray-50 dark:bg-background-dark rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <span className="material-symbols-outlined text-blue-600 dark:text-blue-400 text-sm">
                    schedule
                  </span>
                  <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                    Execution Time
                  </span>
                </div>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {metrics.executionTime}
                </p>
              </div>

              <div className="bg-gray-50 dark:bg-background-dark rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <span className="material-symbols-outlined text-purple-600 dark:text-purple-400 text-sm">
                    account_tree
                  </span>
                  <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                    Nodes Executed
                  </span>
                </div>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {metrics.nodesExecuted}/{metrics.totalNodes}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
