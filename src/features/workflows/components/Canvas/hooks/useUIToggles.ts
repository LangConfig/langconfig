/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useCallback } from 'react';

interface UseUITogglesReturn {
  // Workflow dropdown
  showWorkflowDropdown: boolean;
  setShowWorkflowDropdown: React.Dispatch<React.SetStateAction<boolean>>;
  handleToggleWorkflowDropdown: () => void;
  handleCloseWorkflowDropdown: () => void;

  // Settings modal
  showSettingsModal: boolean;
  setShowSettingsModal: React.Dispatch<React.SetStateAction<boolean>>;
  handleToggleSettingsModal: () => void;
  handleCloseSettingsModal: () => void;

  // Thinking stream
  showThinkingStream: boolean;
  setShowThinkingStream: React.Dispatch<React.SetStateAction<boolean>>;
  handleToggleThinkingStream: () => void;

  // Live execution panel
  showLiveExecutionPanel: boolean;
  setShowLiveExecutionPanel: React.Dispatch<React.SetStateAction<boolean>>;
  handleToggleLiveExecutionPanel: () => void;

  // Checkpointer
  checkpointerEnabled: boolean;
  setCheckpointerEnabled: React.Dispatch<React.SetStateAction<boolean>>;
  handleToggleCheckpointer: () => void;

  // Workflow search
  workflowSearchQuery: string;
  setWorkflowSearchQuery: React.Dispatch<React.SetStateAction<string>>;
  handleWorkflowSearchChange: (e: React.ChangeEvent<HTMLInputElement>) => void;

  // Name editing
  isEditingName: boolean;
  setIsEditingName: React.Dispatch<React.SetStateAction<boolean>>;
  handleStartEditingName: (e: React.MouseEvent) => void;
}

/**
 * Hook for managing UI toggle states and handlers
 */
export function useUIToggles(): UseUITogglesReturn {
  // Workflow dropdown
  const [showWorkflowDropdown, setShowWorkflowDropdown] = useState(false);
  const handleToggleWorkflowDropdown = useCallback(() => {
    setShowWorkflowDropdown(prev => !prev);
  }, []);
  const handleCloseWorkflowDropdown = useCallback(() => {
    setShowWorkflowDropdown(false);
  }, []);

  // Settings modal
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const handleToggleSettingsModal = useCallback(() => {
    setShowSettingsModal(prev => !prev);
  }, []);
  const handleCloseSettingsModal = useCallback(() => {
    setShowSettingsModal(false);
  }, []);

  // Thinking stream
  const [showThinkingStream, setShowThinkingStream] = useState(false);
  const handleToggleThinkingStream = useCallback(() => {
    setShowThinkingStream(prev => !prev);
  }, []);

  // Live execution panel
  const [showLiveExecutionPanel, setShowLiveExecutionPanel] = useState(false);
  const handleToggleLiveExecutionPanel = useCallback(() => {
    setShowLiveExecutionPanel(prev => !prev);
  }, []);

  // Checkpointer
  const [checkpointerEnabled, setCheckpointerEnabled] = useState(false);
  const handleToggleCheckpointer = useCallback(() => {
    setCheckpointerEnabled(prev => !prev);
  }, []);

  // Workflow search
  const [workflowSearchQuery, setWorkflowSearchQuery] = useState('');
  const handleWorkflowSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setWorkflowSearchQuery(e.target.value);
  }, []);

  // Name editing
  const [isEditingName, setIsEditingName] = useState(false);
  const handleStartEditingName = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setIsEditingName(true);
  }, []);

  return {
    showWorkflowDropdown,
    setShowWorkflowDropdown,
    handleToggleWorkflowDropdown,
    handleCloseWorkflowDropdown,
    showSettingsModal,
    setShowSettingsModal,
    handleToggleSettingsModal,
    handleCloseSettingsModal,
    showThinkingStream,
    setShowThinkingStream,
    handleToggleThinkingStream,
    showLiveExecutionPanel,
    setShowLiveExecutionPanel,
    handleToggleLiveExecutionPanel,
    checkpointerEnabled,
    setCheckpointerEnabled,
    handleToggleCheckpointer,
    workflowSearchQuery,
    setWorkflowSearchQuery,
    handleWorkflowSearchChange,
    isEditingName,
    setIsEditingName,
    handleStartEditingName,
  };
}
