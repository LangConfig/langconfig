/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * useToast Hook
 *
 * Convenience export for the useToast hook.
 * Import from here instead of the Toast context directly.
 *
 * @example
 * import { useToast } from '@/hooks/useToast';
 *
 * function MyComponent() {
 *   const { showToast } = useToast();
 *
 *   const handleSuccess = () => {
 *     showToast('Operation successful!', 'success');
 *   };
 *
 *   const handleError = () => {
 *     showToast('Something went wrong', 'error');
 *   };
 *
 *   return ...;
 * }
 */

export { useToast, ToastProvider, type Toast, type ToastType } from '../components/ui/Toast/ToastContext';
export { ToastContainer } from '../components/ui/Toast/ToastContainer';
