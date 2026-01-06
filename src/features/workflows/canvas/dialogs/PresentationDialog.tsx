/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo, useState, useEffect } from 'react';
import GoogleOAuthButton from '@/components/auth/GoogleOAuthButton';
import {
  usePresentationJob,
  type PresentationFormat,
  type PresentationTheme,
  type PresentationFormatInfo,
  type PresentationThemeInfo,
  type PresentationSelectedItem
} from '@/hooks/usePresentationJob';
import { useSelectionOptional } from '../context/SelectionContext';

interface PresentationDialogProps {
  isOpen: boolean;
  onClose: () => void;
  workflowId?: number;
  taskId?: number;
}

/**
 * Dialog for creating presentations from selected artifacts and files
 */
const PresentationDialog = memo(function PresentationDialog({
  isOpen,
  onClose,
  workflowId,
  taskId
}: PresentationDialogProps) {
  // Get selected items from selection context
  const selectionContext = useSelectionOptional();
  const selectedItems = selectionContext?.getSelectedItems() ?? [];
  const [title, setTitle] = useState('');
  const [outputFormat, setOutputFormat] = useState<PresentationFormat>('pdf');
  const [theme, setTheme] = useState<PresentationTheme>('default');
  const [formats, setFormats] = useState<PresentationFormatInfo[]>([]);
  const [themes, setThemes] = useState<PresentationThemeInfo[]>([]);
  const [googleConnected, setGoogleConnected] = useState(false);

  const {
    job,
    status,
    isLoading,
    error,
    progress,
    generate,
    download,
    openResult,
    fetchFormats
  } = usePresentationJob({
    onComplete: (completedJob) => {
      console.log('Presentation created:', completedJob);
    },
    onError: (err) => {
      console.error('Presentation failed:', err);
    }
  });

  // Fetch available formats on open
  useEffect(() => {
    if (isOpen) {
      fetchFormats().then((data) => {
        if (data) {
          setFormats(data.formats);
          setThemes(data.themes);
          // Check if Google is connected
          const googleFormat = data.formats.find(f => f.id === 'google_slides');
          setGoogleConnected(googleFormat?.oauth_connected ?? false);
        }
      });
    }
  }, [isOpen, fetchFormats]);

  // Reset state when dialog opens
  useEffect(() => {
    if (isOpen && selectedItems.length > 0) {
      // Generate default title from first item or generic
      const firstItem = selectedItems[0];
      setTitle(firstItem?.displayName || 'Untitled Presentation');
    }
  }, [isOpen, selectedItems]);

  if (!isOpen) return null;

  const handleClose = () => {
    if (!isLoading) {
      onClose();
    }
  };

  const handleGenerate = async () => {
    // Convert SelectionItems to PresentationSelectedItems
    const presentationItems: PresentationSelectedItem[] = selectedItems.map(item => ({
      type: item.type,
      id: item.id,
      taskId: item.taskId,
      blockIndex: item.blockIndex,
      block: item.block ? {
        type: item.block.type,
        text: 'text' in item.block ? item.block.text : undefined,
        data: 'data' in item.block ? item.block.data : undefined,
        mimeType: 'mimeType' in item.block ? item.block.mimeType : undefined,
        name: 'name' in item.block ? item.block.name : undefined
      } : undefined,
      filePath: item.filePath,
      filename: item.displayName
    }));

    await generate({
      title,
      output_format: outputFormat,
      selected_items: presentationItems,
      theme,
      workflow_id: workflowId,
      task_id: taskId
    });
  };

  const handleGoogleConnectionChange = (connected: boolean) => {
    setGoogleConnected(connected);
    // If user just connected and had Google Slides selected, keep it
    // If user just disconnected and had Google Slides selected, switch to PDF
    if (!connected && outputFormat === 'google_slides') {
      setOutputFormat('pdf');
    }
  };

  const isGoogleSlidesDisabled = outputFormat === 'google_slides' && !googleConnected;
  const canGenerate = title.trim() && selectedItems.length > 0 && !isLoading && !isGoogleSlidesDisabled;

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={handleClose}
    >
      <div
        className="rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto"
        style={{
          backgroundColor: 'var(--color-panel-dark)',
          border: '1px solid var(--color-border-dark)'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h2
            className="text-xl font-semibold"
            style={{ color: 'var(--color-text-primary)' }}
          >
            Create Presentation
          </h2>
          <button
            onClick={handleClose}
            className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition-colors"
            disabled={isLoading}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Selected Items Summary */}
        <div
          className="mb-4 p-3 rounded-lg"
          style={{ backgroundColor: 'var(--color-background-secondary)' }}
        >
          <div className="flex items-center gap-2 mb-2">
            <svg className="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span
              className="text-sm font-medium"
              style={{ color: 'var(--color-text-primary)' }}
            >
              {selectedItems.length} item{selectedItems.length !== 1 ? 's' : ''} selected
            </span>
          </div>
          <div className="text-xs space-y-1" style={{ color: 'var(--color-text-muted)' }}>
            {selectedItems.slice(0, 3).map(item => (
              <div key={item.id} className="truncate">
                {item.type === 'artifact' ? '📄' : '📁'} {item.displayName}
              </div>
            ))}
            {selectedItems.length > 3 && (
              <div>...and {selectedItems.length - 3} more</div>
            )}
          </div>
        </div>

        {/* Title Input */}
        <div className="mb-4">
          <label
            className="block text-sm font-medium mb-2"
            style={{ color: 'var(--color-text-primary)' }}
          >
            Presentation Title
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Enter presentation title..."
            disabled={isLoading}
            className="w-full px-3 py-2 rounded-lg border focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
            style={{
              backgroundColor: 'var(--color-input-background)',
              borderColor: 'var(--color-border-dark)',
              color: 'var(--color-text-primary)'
            }}
          />
        </div>

        {/* Output Format */}
        <div className="mb-4">
          <label
            className="block text-sm font-medium mb-2"
            style={{ color: 'var(--color-text-primary)' }}
          >
            Output Format
          </label>
          <div className="grid grid-cols-3 gap-2">
            {formats.map((format) => (
              <button
                key={format.id}
                onClick={() => setOutputFormat(format.id as PresentationFormat)}
                disabled={isLoading || (format.id === 'google_slides' && !googleConnected)}
                className={`p-3 rounded-lg border-2 text-left transition-all ${
                  outputFormat === format.id
                    ? 'border-primary bg-primary/10'
                    : 'border-transparent hover:border-gray-300 dark:hover:border-gray-600'
                } ${(format.id === 'google_slides' && !googleConnected) ? 'opacity-50 cursor-not-allowed' : ''}`}
                style={{
                  backgroundColor: outputFormat === format.id
                    ? 'var(--color-primary-alpha-10)'
                    : 'var(--color-background-secondary)'
                }}
              >
                <div className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                  {format.name}
                </div>
                <div className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                  {format.id === 'google_slides' && !googleConnected
                    ? 'Connect Google first'
                    : format.file_extension
                      ? `.${format.file_extension}`
                      : 'Opens in browser'
                  }
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Google OAuth - Show when Google Slides selected or needed */}
        {(outputFormat === 'google_slides' || !googleConnected) && (
          <div className="mb-4 p-4 rounded-lg" style={{ backgroundColor: 'var(--color-background-secondary)' }}>
            <div className="text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
              Google Account
            </div>
            <GoogleOAuthButton onConnectionChange={handleGoogleConnectionChange} />
          </div>
        )}

        {/* Theme Selector */}
        <div className="mb-6">
          <label
            className="block text-sm font-medium mb-2"
            style={{ color: 'var(--color-text-primary)' }}
          >
            Theme
          </label>
          <div className="flex gap-2">
            {themes.map((t) => (
              <button
                key={t.id}
                onClick={() => setTheme(t.id as PresentationTheme)}
                disabled={isLoading}
                className={`flex-1 px-3 py-2 rounded-lg border-2 text-sm transition-all ${
                  theme === t.id
                    ? 'border-primary bg-primary/10'
                    : 'border-transparent hover:border-gray-300 dark:hover:border-gray-600'
                }`}
                style={{
                  backgroundColor: theme === t.id
                    ? 'var(--color-primary-alpha-10)'
                    : 'var(--color-background-secondary)'
                }}
              >
                <span style={{ color: 'var(--color-text-primary)' }}>{t.name}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Progress/Status */}
        {isLoading && (
          <div className="mb-4">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-4 h-4 border-2 border-gray-300 border-t-primary rounded-full animate-spin" />
              <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
                {status === 'pending' && 'Queued...'}
                {status === 'processing' && 'Generating presentation...'}
              </span>
            </div>
            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
              <div
                className="bg-primary h-2 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          </div>
        )}

        {/* Success State */}
        {status === 'completed' && job && (
          <div className="mb-4 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="font-medium text-green-700 dark:text-green-400">
                Presentation created!
              </span>
            </div>
            <button
              onClick={openResult}
              className="w-full mt-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors"
            >
              {job.result_url ? 'Open in Google Slides' : 'Download Presentation'}
            </button>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-2 justify-end">
          <button
            onClick={handleClose}
            disabled={isLoading}
            className="px-4 py-2 rounded-lg border transition-colors disabled:opacity-50"
            style={{
              borderColor: 'var(--color-border-dark)',
              color: 'var(--color-text-muted)'
            }}
          >
            {status === 'completed' ? 'Close' : 'Cancel'}
          </button>
          {status !== 'completed' && (
            <button
              onClick={handleGenerate}
              disabled={!canGenerate}
              className="px-4 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                background: 'linear-gradient(135deg, #6366F1 0%, #8B5CF6 50%, #D946EF 100%)',
                color: 'white'
              }}
            >
              {isLoading ? 'Creating...' : 'Create Presentation'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
});

export default PresentationDialog;
