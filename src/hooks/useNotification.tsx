/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useCallback } from 'react';
import NotificationModal from '../components/ui/NotificationModal';

interface NotificationOptions {
  type?: 'success' | 'error' | 'warning' | 'info';
  title?: string;
  message: string;
  details?: string;
  showCancel?: boolean;
  onConfirm?: () => void;
  confirmText?: string;
  cancelText?: string;
}

export function useNotification() {
  const [notification, setNotification] = useState<NotificationOptions | null>(null);

  const showNotification = useCallback((options: NotificationOptions) => {
    setNotification(options);
  }, []);

  const closeNotification = useCallback(() => {
    setNotification(null);
  }, []);

  // Convenience methods
  const showSuccess = useCallback((message: string, details?: string) => {
    showNotification({ type: 'success', message, details });
  }, [showNotification]);

  const logError = useCallback((message: string, details?: string) => {
    // Logs errors to console without showing UI notification
    // Renamed from showError to clarify that this doesn't show popups
    console.error('Error:', message, details);
  }, []);

  const showWarning = useCallback((message: string, details?: string) => {
    showNotification({ type: 'warning', message, details });
  }, [showNotification]);

  const showInfo = useCallback((message: string, details?: string) => {
    showNotification({ type: 'info', message, details });
  }, [showNotification]);

  const confirm = useCallback((message: string, onConfirm: () => void, options?: Partial<NotificationOptions>) => {
    showNotification({
      type: 'warning',
      message,
      showCancel: true,
      onConfirm,
      confirmText: 'Confirm',
      cancelText: 'Cancel',
      ...options,
    });
  }, [showNotification]);

  const Modal = useCallback(() => {
    if (!notification) return null;

    return (
      <NotificationModal
        isOpen={true}
        onClose={closeNotification}
        {...notification}
      />
    );
  }, [notification, closeNotification]);

  return {
    showNotification,
    showSuccess,
    logError,
    showWarning,
    showInfo,
    confirm,
    closeNotification,
    NotificationModal: Modal,
  };
}
