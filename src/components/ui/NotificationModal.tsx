/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';

interface NotificationModalProps {
  isOpen: boolean;
  onClose: () => void;
  type?: 'success' | 'error' | 'warning' | 'info';
  title?: string;
  message: string;
  details?: string;
  showCancel?: boolean;
  onConfirm?: () => void;
  confirmText?: string;
  cancelText?: string;
}

export default function NotificationModal({
  isOpen,
  onClose,
  type = 'info',
  title,
  message,
  details,
  showCancel = false,
  onConfirm,
  confirmText = 'OK',
  cancelText = 'Cancel',
}: NotificationModalProps) {
  if (!isOpen) return null;

  const getIcon = () => {
    switch (type) {
      case 'success':
        return <CheckCircle className="w-6 h-6 text-green-500" />;
      case 'error':
        return <AlertCircle className="w-6 h-6 text-red-500" />;
      case 'warning':
        return <AlertTriangle className="w-6 h-6 text-yellow-500" />;
      default:
        return <Info className="w-6 h-6" style={{ color: 'var(--color-primary)' }} />;
    }
  };

  const getTitle = () => {
    if (title) return title;
    switch (type) {
      case 'success':
        return 'Success';
      case 'error':
        return 'Error';
      case 'warning':
        return 'Warning';
      default:
        return 'Notification';
    }
  };

  const handleConfirm = () => {
    if (onConfirm) {
      onConfirm();
    }
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative max-w-md w-full mx-4 rounded-lg shadow-2xl"
        style={{
          backgroundColor: 'var(--color-panel-dark)',
          border: '1px solid var(--color-border-dark)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b" style={{ borderColor: 'var(--color-border-dark)' }}>
          <div className="flex items-center gap-3">
            {getIcon()}
            <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              {getTitle()}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 dark:hover:bg-white/10 rounded transition-colors"
          >
            <X className="w-5 h-5" style={{ color: 'var(--color-text-muted)' }} />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-3">
          <p className="text-sm whitespace-pre-wrap" style={{ color: 'var(--color-text-primary)' }}>
            {message}
          </p>
          {details && (
            <div
              className="p-3 rounded text-xs whitespace-pre-wrap"
              style={{
                backgroundColor: 'var(--color-background-dark)',
                color: 'var(--color-text-muted)',
                border: '1px solid var(--color-border-dark)',
              }}
            >
              {details}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 p-4 border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
          {showCancel && (
            <button
              onClick={onClose}
              className="px-4 py-2 rounded text-sm font-medium transition-colors"
              style={{
                backgroundColor: 'var(--color-background-dark)',
                color: 'var(--color-text-primary)',
                border: '1px solid var(--color-border-dark)',
              }}
            >
              {cancelText}
            </button>
          )}
          <button
            onClick={handleConfirm}
            className="px-4 py-2 rounded text-sm font-medium text-white transition-opacity hover:opacity-90"
            style={{
              backgroundColor: 'var(--color-primary)',
            }}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
