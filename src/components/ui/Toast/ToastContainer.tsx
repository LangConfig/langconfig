/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Toast Container Component
 *
 * Displays all active toasts using React Portal.
 * Renders outside normal DOM hierarchy for proper z-index layering.
 */

import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useToast, Toast as ToastType } from './ToastContext';
import { AlertCircle, CheckCircle, Info, X, AlertTriangle } from 'lucide-react';

function ToastItem({ toast }: { toast: ToastType }) {
  const { removeToast } = useToast();

  useEffect(() => {
    const timer = setTimeout(() => {
      removeToast(toast.id);
    }, toast.duration || 5000);

    return () => clearTimeout(timer);
  }, [toast.id, toast.duration, removeToast]);

  const handleClose = () => {
    removeToast(toast.id);
  };

  const getIcon = () => {
    switch (toast.type) {
      case 'success':
        return <CheckCircle size={20} />;
      case 'error':
        return <AlertCircle size={20} />;
      case 'warning':
        return <AlertTriangle size={20} />;
      case 'info':
      default:
        return <Info size={20} />;
    }
  };

  const getTypeStyles = () => {
    switch (toast.type) {
      case 'success':
        return 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800 text-green-800 dark:text-green-200';
      case 'error':
        return 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800 text-red-800 dark:text-red-200';
      case 'warning':
        return 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800 text-yellow-800 dark:text-yellow-200';
      case 'info':
      default:
        return 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-200';
    }
  };

  return (
    <div
      id={toast.id}
      className={`flex items-center gap-3 px-4 py-3 rounded-lg border shadow-lg min-w-[300px] max-w-md animate-in slide-in-from-right ${getTypeStyles()}`}
      role="alert"
      aria-live="polite"
    >
      <div className="flex-shrink-0">
        {getIcon()}
      </div>
      <div className="flex-1 text-sm font-medium">
        {toast.message}
      </div>
      <button
        className="flex-shrink-0 p-1 rounded hover:bg-black/10 dark:hover:bg-white/10 transition-colors"
        onClick={handleClose}
        aria-label="Close notification"
        type="button"
      >
        <X size={16} />
      </button>
    </div>
  );
}

/**
 * Toast Container
 * Mount this component once in your app (typically in App.tsx)
 */
export function ToastContainer() {
  const { toasts } = useToast();

  // Create portal target if it doesn't exist
  useEffect(() => {
    let portalRoot = document.getElementById('toast-portal');
    if (!portalRoot) {
      portalRoot = document.createElement('div');
      portalRoot.id = 'toast-portal';
      document.body.appendChild(portalRoot);
    }
  }, []);

  const portalRoot = document.getElementById('toast-portal');
  if (!portalRoot) return null;

  return createPortal(
    <div
      className="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none"
      aria-live="polite"
      aria-atomic="true"
    >
      {toasts.map((toast) => (
        <div key={toast.id} className="pointer-events-auto">
          <ToastItem toast={toast} />
        </div>
      ))}
    </div>,
    portalRoot
  );
}
