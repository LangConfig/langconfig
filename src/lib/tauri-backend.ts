/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { invoke } from '@tauri-apps/api/core';

/**
 * Start the Python backend process
 */
export async function startPythonBackend(): Promise<string> {
  return await invoke<string>('start_python_backend');
}

/**
 * Stop the Python backend process
 */
export async function stopPythonBackend(): Promise<string> {
  return await invoke<string>('stop_python_backend');
}

/**
 * Check if the Python backend is running
 */
export async function isBackendRunning(): Promise<boolean> {
  return await invoke<boolean>('is_backend_running');
}

/**
 * Check the health status of the backend
 */
export async function checkBackendHealth(): Promise<string> {
  return await invoke<string>('check_backend_health');
}

/**
 * Get the backend API URL
 */
export async function getBackendUrl(): Promise<string> {
  return await invoke<string>('get_backend_url');
}

/**
 * Wait for the backend to be ready (with retry logic)
 * @param maxRetries Maximum number of retries
 * @param delayMs Delay between retries in milliseconds
 */
export async function waitForBackend(
  maxRetries: number = 30,
  delayMs: number = 1000
): Promise<boolean> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      await checkBackendHealth();
      return true;
    } catch (error) {
      if (i === maxRetries - 1) {
        throw new Error('Backend failed to start');
      }
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }
  return false;
}

/**
 * Initialize the backend (start if not running, wait for health check)
 */
export async function initializeBackend(): Promise<void> {
  const running = await isBackendRunning();

  if (!running) {
    await startPythonBackend();
  }

  await waitForBackend();
}
