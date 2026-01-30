/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo, useState, useEffect, useCallback } from 'react';
import { X, FolderOpen, Check, AlertCircle, Loader2, Clock, Plus, Pencil, Play, Trash2, Webhook, FolderSearch } from 'lucide-react';
import FolderBrowserDialog from './FolderBrowserDialog';
import ScheduleDialog from './ScheduleDialog';
import TriggerDialog from './TriggerDialog';
import apiClient from '@/lib/api-client';
import type { WorkflowSchedule, WorkflowTrigger } from '@/types/workflow';

interface PathValidation {
  valid: boolean;
  resolved_path?: string;
  error?: string;
  writable: boolean;
  exists: boolean;
}

interface WorkflowSettingsDialogProps {
  isOpen: boolean;
  onClose: () => void;
  workflowId?: number;
  checkpointerEnabled: boolean;
  onToggleCheckpointer: () => void;
  globalRecursionLimit: number;
  setGlobalRecursionLimit: (limit: number) => void;
  customOutputPath: string | null;
  onOutputPathChange: (path: string | null) => void;
}

/**
 * Modal for configuring workflow settings (checkpointer, recursion limit, output path)
 */
const WorkflowSettingsDialog = memo(function WorkflowSettingsDialog({
  isOpen,
  onClose,
  workflowId,
  checkpointerEnabled,
  onToggleCheckpointer,
  globalRecursionLimit,
  setGlobalRecursionLimit,
  customOutputPath,
  onOutputPathChange,
}: WorkflowSettingsDialogProps) {
  const [localPath, setLocalPath] = useState<string>(customOutputPath || '');
  const [showFolderBrowser, setShowFolderBrowser] = useState(false);
  const [pathValidation, setPathValidation] = useState<PathValidation | null>(null);
  const [validating, setValidating] = useState(false);

  // Scheduling state
  const [schedules, setSchedules] = useState<WorkflowSchedule[]>([]);
  const [loadingSchedules, setLoadingSchedules] = useState(false);
  const [showScheduleDialog, setShowScheduleDialog] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<WorkflowSchedule | null>(null);

  // Trigger state
  const [triggers, setTriggers] = useState<WorkflowTrigger[]>([]);
  const [loadingTriggers, setLoadingTriggers] = useState(false);
  const [showTriggerDialog, setShowTriggerDialog] = useState(false);
  const [editingTrigger, setEditingTrigger] = useState<WorkflowTrigger | null>(null);

  // Sync local state with prop
  useEffect(() => {
    setLocalPath(customOutputPath || '');
  }, [customOutputPath]);

  // Load schedules when dialog opens
  const loadSchedules = useCallback(async () => {
    if (!workflowId) return;
    setLoadingSchedules(true);
    try {
      const response = await apiClient.listSchedules(workflowId);
      setSchedules(response.data.schedules || []);
    } catch (err) {
      console.error('Failed to load schedules:', err);
    } finally {
      setLoadingSchedules(false);
    }
  }, [workflowId]);

  useEffect(() => {
    if (isOpen && workflowId) {
      loadSchedules();
    }
  }, [isOpen, workflowId, loadSchedules]);

  const handleScheduleSaved = () => {
    loadSchedules();
    setEditingSchedule(null);
  };

  const handleEditSchedule = (schedule: WorkflowSchedule) => {
    setEditingSchedule(schedule);
    setShowScheduleDialog(true);
  };

  const handleAddSchedule = () => {
    setEditingSchedule(null);
    setShowScheduleDialog(true);
  };

  const handleToggleSchedule = async (schedule: WorkflowSchedule) => {
    try {
      await apiClient.updateSchedule(schedule.id, { enabled: !schedule.enabled });
      loadSchedules();
    } catch (err) {
      console.error('Failed to toggle schedule:', err);
    }
  };

  const handleTriggerSchedule = async (schedule: WorkflowSchedule) => {
    try {
      await apiClient.triggerScheduleNow(schedule.id);
    } catch (err) {
      console.error('Failed to trigger schedule:', err);
    }
  };

  const handleDeleteSchedule = async (schedule: WorkflowSchedule) => {
    if (!window.confirm('Delete this schedule?')) return;
    try {
      await apiClient.deleteSchedule(schedule.id);
      loadSchedules();
    } catch (err) {
      console.error('Failed to delete schedule:', err);
    }
  };

  // Load triggers when dialog opens
  const loadTriggers = useCallback(async () => {
    if (!workflowId) return;
    setLoadingTriggers(true);
    try {
      const response = await apiClient.listTriggers(workflowId);
      setTriggers(response.data.triggers || []);
    } catch (err) {
      console.error('Failed to load triggers:', err);
    } finally {
      setLoadingTriggers(false);
    }
  }, [workflowId]);

  useEffect(() => {
    if (isOpen && workflowId) {
      loadTriggers();
    }
  }, [isOpen, workflowId, loadTriggers]);

  const handleTriggerSaved = () => {
    loadTriggers();
    setEditingTrigger(null);
  };

  const handleEditTrigger = (trigger: WorkflowTrigger) => {
    setEditingTrigger(trigger);
    setShowTriggerDialog(true);
  };

  const handleAddTrigger = () => {
    setEditingTrigger(null);
    setShowTriggerDialog(true);
  };

  const handleToggleTrigger = async (trigger: WorkflowTrigger) => {
    try {
      await apiClient.updateTrigger(trigger.id, { enabled: !trigger.enabled });
      loadTriggers();
    } catch (err) {
      console.error('Failed to toggle trigger:', err);
    }
  };

  const handleTestTrigger = async (trigger: WorkflowTrigger) => {
    try {
      await apiClient.testTrigger(trigger.id);
    } catch (err) {
      console.error('Failed to test trigger:', err);
    }
  };

  const handleDeleteTrigger = async (trigger: WorkflowTrigger) => {
    if (!window.confirm('Delete this trigger?')) return;
    try {
      await apiClient.deleteTrigger(trigger.id);
      loadTriggers();
    } catch (err) {
      console.error('Failed to delete trigger:', err);
    }
  };

  // Debounced path validation
  const validatePath = useCallback(async (path: string) => {
    if (!path.trim() || !workflowId) {
      setPathValidation(null);
      return;
    }

    setValidating(true);
    try {
      const response = await apiClient.validateOutputPath(workflowId, path);
      setPathValidation(response.data);
    } catch (err: any) {
      setPathValidation({
        valid: false,
        error: err?.response?.data?.detail || 'Validation failed',
        writable: false,
        exists: false,
      });
    } finally {
      setValidating(false);
    }
  }, [workflowId]);

  // Validate on path change (debounced)
  useEffect(() => {
    const timer = setTimeout(() => {
      if (localPath.trim()) {
        validatePath(localPath);
      } else {
        setPathValidation(null);
      }
    }, 500);

    return () => clearTimeout(timer);
  }, [localPath, validatePath]);

  const handlePathChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setLocalPath(e.target.value);
  };

  const handleFolderSelect = (path: string) => {
    setLocalPath(path);
    setShowFolderBrowser(false);
  };

  const handleClearPath = () => {
    setLocalPath('');
    setPathValidation(null);
    onOutputPathChange(null);
  };

  const handleApplyPath = () => {
    if (localPath.trim() && pathValidation?.valid) {
      onOutputPathChange(pathValidation.resolved_path || localPath);
    } else if (!localPath.trim()) {
      onOutputPathChange(null);
    }
  };

  if (!isOpen) return null;

  return (
    <>
      <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm">
        <div
          className="w-full max-w-md max-h-[90vh] rounded-xl shadow-2xl overflow-hidden flex flex-col"
          style={{
            backgroundColor: 'var(--color-panel-dark)',
            border: '1px solid var(--color-border-dark)'
          }}
        >
          <div className="px-6 py-4 border-b flex justify-between items-center shrink-0" style={{ borderColor: 'var(--color-border-dark)' }}>
            <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              Workflow Settings
            </h3>
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-white/10 transition-colors"
              style={{ color: 'var(--color-text-muted)' }}
            >
              <X size={20} />
            </button>
          </div>

          <div className="p-6 space-y-6 overflow-y-auto flex-1">
            {/* Custom Output Path Setting */}
            <div>
              <label className="text-sm font-medium block mb-1" style={{ color: 'var(--color-text-primary)' }}>
                Custom Output Directory
              </label>
              <p className="text-xs mb-3" style={{ color: 'var(--color-text-muted)' }}>
                Files generated by agents will be saved here. Leave empty to use the default location (backend/outputs).
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={localPath}
                  onChange={handlePathChange}
                  placeholder="e.g., C:\Projects\MyApp\outputs"
                  className="flex-1 px-3 py-2 rounded-lg text-sm font-mono"
                  style={{
                    backgroundColor: 'var(--color-background-dark)',
                    border: '1px solid var(--color-border-dark)',
                    color: 'var(--color-text-primary)',
                  }}
                />
                <button
                  onClick={() => setShowFolderBrowser(true)}
                  className="px-3 py-2 rounded-lg text-sm font-medium transition-colors hover:bg-white/10 flex items-center gap-2"
                  style={{
                    backgroundColor: 'var(--color-background-dark)',
                    border: '1px solid var(--color-border-dark)',
                    color: 'var(--color-text-primary)',
                  }}
                >
                  <FolderOpen size={16} />
                  Browse
                </button>
              </div>

              {/* Validation Status */}
              {localPath.trim() && (
                <div className="mt-2 flex items-center gap-2">
                  {validating ? (
                    <>
                      <Loader2 size={14} className="animate-spin" style={{ color: 'var(--color-text-muted)' }} />
                      <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Validating...</span>
                    </>
                  ) : pathValidation?.valid ? (
                    <>
                      <Check size={14} style={{ color: '#22c55e' }} />
                      <span className="text-xs" style={{ color: '#22c55e' }}>
                        Valid: {pathValidation.resolved_path}
                      </span>
                    </>
                  ) : pathValidation?.error ? (
                    <>
                      <AlertCircle size={14} style={{ color: '#ef4444' }} />
                      <span className="text-xs" style={{ color: '#ef4444' }}>{pathValidation.error}</span>
                    </>
                  ) : null}
                </div>
              )}

              {/* Action Buttons */}
              {localPath.trim() && (
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={handleClearPath}
                    className="px-3 py-1.5 rounded text-xs font-medium transition-colors hover:bg-white/10"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    Clear
                  </button>
                  <button
                    onClick={handleApplyPath}
                    disabled={validating || (pathValidation !== null && !pathValidation.valid)}
                    className="px-3 py-1.5 rounded text-xs font-medium transition-colors bg-primary text-white hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Apply
                  </button>
                </div>
              )}

              {/* Current configured path indicator */}
              {customOutputPath && customOutputPath !== localPath && (
                <p className="text-xs mt-2 p-2 rounded-md" style={{ backgroundColor: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6' }}>
                  Currently configured: {customOutputPath}
                </p>
              )}
            </div>

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
                    Warning: When enabled, agents will remember previous executions. The same prompt may produce different results as the agent may reference prior context. Use clear, specific instructions to avoid confusion.
                  </p>
                )}
              </div>
              <div
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors cursor-pointer ${checkpointerEnabled ? 'bg-primary' : 'bg-gray-600'}`}
                onClick={onToggleCheckpointer}
              >
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

            {/* Scheduling Section */}
            {workflowId && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Clock size={16} style={{ color: 'var(--color-primary)' }} />
                    <label className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                      Scheduled Runs
                    </label>
                  </div>
                  <button
                    onClick={handleAddSchedule}
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors bg-primary text-white hover:bg-primary/90"
                  >
                    <Plus size={12} />
                    Add Schedule
                  </button>
                </div>
                <p className="text-xs mb-3" style={{ color: 'var(--color-text-muted)' }}>
                  Automatically run this workflow on a cron schedule.
                </p>

                {loadingSchedules ? (
                  <div className="flex items-center gap-2 py-4">
                    <Loader2 size={14} className="animate-spin" style={{ color: 'var(--color-text-muted)' }} />
                    <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Loading schedules...</span>
                  </div>
                ) : schedules.length === 0 ? (
                  <p className="text-xs py-4" style={{ color: 'var(--color-text-muted)' }}>
                    No schedules configured. Click "Add Schedule" to create one.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {schedules.map((schedule) => (
                      <div
                        key={schedule.id}
                        className="p-3 rounded-lg"
                        style={{
                          backgroundColor: 'var(--color-background-dark)',
                          border: '1px solid var(--color-border-dark)',
                        }}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium truncate" style={{ color: 'var(--color-text-primary)' }}>
                                {schedule.name || 'Unnamed Schedule'}
                              </span>
                              <span
                                className={`px-1.5 py-0.5 rounded text-xs ${
                                  schedule.enabled ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'
                                }`}
                              >
                                {schedule.enabled ? 'Active' : 'Disabled'}
                              </span>
                              {schedule.last_run_status && (
                                <span
                                  className={`px-1.5 py-0.5 rounded text-xs ${
                                    schedule.last_run_status === 'SUCCESS'
                                      ? 'bg-green-500/20 text-green-400'
                                      : schedule.last_run_status === 'FAILED'
                                      ? 'bg-red-500/20 text-red-400'
                                      : 'bg-gray-500/20 text-gray-400'
                                  }`}
                                >
                                  Last: {schedule.last_run_status}
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-2 mt-1">
                              <code className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                                {schedule.cron_expression}
                              </code>
                              <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                                ({schedule.timezone})
                              </span>
                            </div>
                            {schedule.next_run_at && schedule.enabled && (
                              <p className="text-xs mt-1" style={{ color: 'var(--color-text-secondary)' }}>
                                Next run: {new Date(schedule.next_run_at).toLocaleString()}
                              </p>
                            )}
                          </div>
                          <div className="flex items-center gap-1 ml-2">
                            <button
                              onClick={() => handleToggleSchedule(schedule)}
                              className="p-1.5 rounded transition-colors hover:bg-white/10"
                              title={schedule.enabled ? 'Disable' : 'Enable'}
                            >
                              <div
                                className={`w-8 h-4 rounded-full relative transition-colors ${
                                  schedule.enabled ? 'bg-green-500' : 'bg-gray-600'
                                }`}
                              >
                                <div
                                  className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${
                                    schedule.enabled ? 'left-4' : 'left-0.5'
                                  }`}
                                />
                              </div>
                            </button>
                            <button
                              onClick={() => handleTriggerSchedule(schedule)}
                              disabled={!schedule.enabled}
                              className="p-1.5 rounded transition-colors hover:bg-white/10 disabled:opacity-50"
                              title="Run Now"
                              style={{ color: 'var(--color-text-muted)' }}
                            >
                              <Play size={14} />
                            </button>
                            <button
                              onClick={() => handleEditSchedule(schedule)}
                              className="p-1.5 rounded transition-colors hover:bg-white/10"
                              title="Edit"
                              style={{ color: 'var(--color-text-muted)' }}
                            >
                              <Pencil size={14} />
                            </button>
                            <button
                              onClick={() => handleDeleteSchedule(schedule)}
                              className="p-1.5 rounded transition-colors hover:bg-red-500/20"
                              title="Delete"
                              style={{ color: '#ef4444' }}
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Event Triggers Section */}
            {workflowId && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Webhook size={16} style={{ color: 'var(--color-primary)' }} />
                    <label className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                      Event Triggers
                    </label>
                  </div>
                  <button
                    onClick={handleAddTrigger}
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors bg-primary text-white hover:bg-primary/90"
                  >
                    <Plus size={12} />
                    Add Trigger
                  </button>
                </div>
                <p className="text-xs mb-3" style={{ color: 'var(--color-text-muted)' }}>
                  Trigger workflow execution via webhooks or file system changes.
                </p>

                {loadingTriggers ? (
                  <div className="flex items-center gap-2 py-4">
                    <Loader2 size={14} className="animate-spin" style={{ color: 'var(--color-text-muted)' }} />
                    <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Loading triggers...</span>
                  </div>
                ) : triggers.length === 0 ? (
                  <p className="text-xs py-4" style={{ color: 'var(--color-text-muted)' }}>
                    No triggers configured. Click "Add Trigger" to create a webhook or file watcher.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {triggers.map((trigger) => (
                      <div
                        key={trigger.id}
                        className="p-3 rounded-lg"
                        style={{
                          backgroundColor: 'var(--color-background-dark)',
                          border: '1px solid var(--color-border-dark)',
                        }}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              {trigger.trigger_type === 'webhook' ? (
                                <Webhook size={14} style={{ color: 'var(--color-text-muted)' }} />
                              ) : (
                                <FolderSearch size={14} style={{ color: 'var(--color-text-muted)' }} />
                              )}
                              <span className="text-sm font-medium truncate" style={{ color: 'var(--color-text-primary)' }}>
                                {trigger.name || (trigger.trigger_type === 'webhook' ? 'Webhook' : 'File Watch')}
                              </span>
                              <span
                                className={`px-1.5 py-0.5 rounded text-xs ${
                                  trigger.enabled ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'
                                }`}
                              >
                                {trigger.enabled ? 'Active' : 'Disabled'}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 mt-1">
                              <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                                {trigger.trigger_type === 'webhook'
                                  ? 'HTTP POST webhook'
                                  : `Watching: ${(trigger.config.watch_path as string) || 'Not configured'}`
                                }
                              </span>
                              {trigger.trigger_count > 0 && (
                                <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                                  ({trigger.trigger_count} triggers)
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-1 ml-2">
                            <button
                              onClick={() => handleToggleTrigger(trigger)}
                              className="p-1.5 rounded transition-colors hover:bg-white/10"
                              title={trigger.enabled ? 'Disable' : 'Enable'}
                            >
                              <div
                                className={`w-8 h-4 rounded-full relative transition-colors ${
                                  trigger.enabled ? 'bg-green-500' : 'bg-gray-600'
                                }`}
                              >
                                <div
                                  className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${
                                    trigger.enabled ? 'left-4' : 'left-0.5'
                                  }`}
                                />
                              </div>
                            </button>
                            <button
                              onClick={() => handleTestTrigger(trigger)}
                              className="p-1.5 rounded transition-colors hover:bg-white/10"
                              title="Test Trigger"
                              style={{ color: 'var(--color-text-muted)' }}
                            >
                              <Play size={14} />
                            </button>
                            <button
                              onClick={() => handleEditTrigger(trigger)}
                              className="p-1.5 rounded transition-colors hover:bg-white/10"
                              title="Edit"
                              style={{ color: 'var(--color-text-muted)' }}
                            >
                              <Pencil size={14} />
                            </button>
                            <button
                              onClick={() => handleDeleteTrigger(trigger)}
                              className="p-1.5 rounded transition-colors hover:bg-red-500/20"
                              title="Delete"
                              style={{ color: '#ef4444' }}
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="px-6 py-4 border-t flex justify-end shrink-0" style={{ borderColor: 'var(--color-border-dark)', backgroundColor: 'var(--color-background-dark)' }}>
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm font-medium transition-colors bg-primary text-white hover:bg-primary/90"
            >
              Done
            </button>
          </div>
        </div>
      </div>

      {/* Folder Browser Dialog */}
      <FolderBrowserDialog
        isOpen={showFolderBrowser}
        onClose={() => setShowFolderBrowser(false)}
        onSelect={handleFolderSelect}
        initialPath={localPath || undefined}
      />

      {/* Schedule Dialog */}
      {workflowId && (
        <ScheduleDialog
          isOpen={showScheduleDialog}
          onClose={() => {
            setShowScheduleDialog(false);
            setEditingSchedule(null);
          }}
          workflowId={workflowId}
          existingSchedule={editingSchedule}
          onSaved={handleScheduleSaved}
        />
      )}

      {/* Trigger Dialog */}
      {workflowId && (
        <TriggerDialog
          isOpen={showTriggerDialog}
          onClose={() => {
            setShowTriggerDialog(false);
            setEditingTrigger(null);
          }}
          workflowId={workflowId}
          existingTrigger={editingTrigger}
          onSaved={handleTriggerSaved}
        />
      )}
    </>
  );
});

export default WorkflowSettingsDialog;
