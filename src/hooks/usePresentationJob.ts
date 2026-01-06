/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect, useCallback, useRef } from 'react';

const API_BASE = 'http://localhost:8765';

/**
 * Presentation job status values
 */
export type PresentationJobStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'idle';

/**
 * Presentation output formats
 */
export type PresentationFormat = 'google_slides' | 'pdf' | 'revealjs';

/**
 * Presentation themes
 */
export type PresentationTheme = 'default' | 'dark' | 'minimal';

/**
 * Selected item for presentation generation
 */
export interface PresentationSelectedItem {
  type: 'artifact' | 'file';
  id: string;
  taskId?: number;
  blockIndex?: number;
  block?: {
    type: string;
    text?: string;
    data?: string;
    mimeType?: string;
    name?: string;
    [key: string]: any;
  };
  filePath?: string;
  filename?: string;
}

/**
 * Presentation job data from API
 */
export interface PresentationJob {
  id: number;
  status: PresentationJobStatus;
  output_format: PresentationFormat;
  title: string | null;
  theme: string | null;
  result_url: string | null;
  result_file_path: string | null;
  error_message: string | null;
  created_at: string | null;
  completed_at: string | null;
}

/**
 * Request to generate a presentation
 */
export interface GeneratePresentationRequest {
  title: string;
  output_format: PresentationFormat;
  selected_items: PresentationSelectedItem[];
  theme?: PresentationTheme;
  workflow_id?: number;
  task_id?: number;
}

/**
 * Format information from API
 */
export interface PresentationFormatInfo {
  id: string;
  name: string;
  description: string;
  file_extension: string | null;
  requires_oauth: boolean;
  oauth_connected: boolean | null;
  oauth_email?: string;
}

/**
 * Theme information from API
 */
export interface PresentationThemeInfo {
  id: string;
  name: string;
  description: string;
}

/**
 * Available formats response from API
 */
export interface PresentationFormatsResponse {
  formats: PresentationFormatInfo[];
  themes: PresentationThemeInfo[];
}

interface UsePresentationJobOptions {
  jobId?: number | null;
  enabled?: boolean;
  onComplete?: (job: PresentationJob) => void;
  onError?: (error: string) => void;
  pollInterval?: number;
}

interface UsePresentationJobResult {
  job: PresentationJob | null;
  status: PresentationJobStatus;
  isLoading: boolean;
  error: string | null;
  progress: number;
  generate: (request: GeneratePresentationRequest) => Promise<PresentationJob | null>;
  download: () => Promise<void>;
  openResult: () => void;
  fetchFormats: () => Promise<PresentationFormatsResponse | null>;
}

/**
 * Hook for managing presentation generation jobs
 *
 * Usage:
 * ```typescript
 * const {
 *   job,
 *   status,
 *   isLoading,
 *   error,
 *   generate,
 *   download,
 *   openResult,
 *   fetchFormats
 * } = usePresentationJob({
 *   onComplete: (job) => {
 *     toast.success('Presentation created!');
 *   },
 *   onError: (error) => {
 *     toast.error(`Failed: ${error}`);
 *   }
 * });
 *
 * // Start generation
 * await generate({
 *   title: 'My Presentation',
 *   output_format: 'pdf',
 *   selected_items: selectedItems
 * });
 * ```
 */
export function usePresentationJob({
  jobId: initialJobId = null,
  enabled = true,
  onComplete,
  onError,
  pollInterval = 3000  // 3 seconds to avoid rate limiting
}: UsePresentationJobOptions = {}): UsePresentationJobResult {
  const [jobId, setJobId] = useState<number | null>(initialJobId);
  const [job, setJob] = useState<PresentationJob | null>(null);
  const [status, setStatus] = useState<PresentationJobStatus>('idle');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  const intervalRef = useRef<number | null>(null);
  const hasCompletedRef = useRef(false);
  const isPollingRef = useRef(false);

  // Clear any existing interval
  const clearPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    isPollingRef.current = false;
  }, []);

  // Start polling when jobId changes
  useEffect(() => {
    if (!enabled || !jobId) {
      clearPolling();
      return;
    }

    // Prevent multiple polling loops
    if (isPollingRef.current) {
      return;
    }

    hasCompletedRef.current = false;
    isPollingRef.current = true;
    setIsLoading(true);

    const checkStatus = async (): Promise<boolean> => {
      if (!jobId || hasCompletedRef.current) return true;

      try {
        const response = await fetch(`${API_BASE}/api/presentations/${jobId}/status`);

        if (!response.ok) {
          if (response.status === 404) {
            throw new Error('Job not found');
          }
          if (response.status === 429) {
            // Rate limited, continue polling but don't error
            console.warn('Rate limited, will retry...');
            return false;
          }
          throw new Error('Failed to check job status');
        }

        const jobData: PresentationJob = await response.json();
        setJob(jobData);
        setStatus(jobData.status);

        if (jobData.status === 'completed') {
          setProgress(100);
          setIsLoading(false);

          if (!hasCompletedRef.current) {
            hasCompletedRef.current = true;
            onComplete?.(jobData);
          }

          return true; // Stop polling
        } else if (jobData.status === 'failed') {
          const errorMsg = jobData.error_message || 'Job failed with unknown error';
          setError(errorMsg);
          setIsLoading(false);

          if (!hasCompletedRef.current) {
            hasCompletedRef.current = true;
            onError?.(errorMsg);
          }

          return true; // Stop polling
        } else if (jobData.status === 'processing') {
          setProgress(50);
        } else if (jobData.status === 'pending') {
          setProgress(20);
        }

        return false; // Continue polling
      } catch (err) {
        console.error('Failed to check presentation job status:', err);
        const errorMsg = err instanceof Error ? err.message : 'Failed to check job status';

        if (err instanceof Error && err.message.includes('not found')) {
          setError(errorMsg);
          setIsLoading(false);
          hasCompletedRef.current = true;
          onError?.(errorMsg);
          return true; // Stop polling
        }

        return false; // Continue polling on temporary errors
      }
    };

    // Check immediately
    checkStatus().then((shouldStop) => {
      if (shouldStop) {
        clearPolling();
        return;
      }

      // Then poll at intervals (use longer interval to avoid rate limiting)
      intervalRef.current = window.setInterval(async () => {
        const shouldStop = await checkStatus();
        if (shouldStop) {
          clearPolling();
        }
      }, pollInterval);
    });

    return () => {
      clearPolling();
    };
  }, [enabled, jobId, pollInterval, onComplete, onError, clearPolling]);

  // Generate a new presentation
  const generate = useCallback(async (request: GeneratePresentationRequest): Promise<PresentationJob | null> => {
    // Reset polling state for new job
    clearPolling();
    setIsLoading(true);
    setError(null);
    setProgress(0);
    hasCompletedRef.current = false;

    try {
      const response = await fetch(`${API_BASE}/api/presentations/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to start presentation generation');
      }

      const jobData: PresentationJob = await response.json();
      setJob(jobData);
      setJobId(jobData.id);
      setStatus(jobData.status);
      setProgress(10);

      return jobData;
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to generate presentation';
      setError(errorMsg);
      setIsLoading(false);
      onError?.(errorMsg);
      return null;
    }
  }, [onError, clearPolling]);

  // Download the result file
  const download = useCallback(async () => {
    if (!job || job.status !== 'completed') {
      console.error('Cannot download: job not completed');
      return;
    }

    if (job.output_format === 'google_slides') {
      // Google Slides - open in new tab
      if (job.result_url) {
        window.open(job.result_url, '_blank');
      }
      return;
    }

    // PDF or Reveal.js - download file
    try {
      const response = await fetch(`${API_BASE}/api/presentations/${job.id}/download`);

      if (!response.ok) {
        throw new Error('Failed to download presentation');
      }

      const blob = await response.blob();
      const filename = job.output_format === 'pdf'
        ? `${job.title || 'presentation'}.pptx`
        : `${job.title || 'presentation'}.zip`;

      // Create download link
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Download failed';
      setError(errorMsg);
      onError?.(errorMsg);
    }
  }, [job, onError]);

  // Open the result (URL for Google Slides, download for others)
  const openResult = useCallback(() => {
    if (!job || job.status !== 'completed') return;

    if (job.result_url) {
      window.open(job.result_url, '_blank');
    } else {
      download();
    }
  }, [job, download]);

  // Fetch available formats
  const fetchFormats = useCallback(async (): Promise<PresentationFormatsResponse | null> => {
    try {
      const response = await fetch(`${API_BASE}/api/presentations/formats`);

      if (!response.ok) {
        throw new Error('Failed to fetch formats');
      }

      return await response.json();
    } catch (err) {
      console.error('Failed to fetch presentation formats:', err);
      return null;
    }
  }, []);

  return {
    job,
    status,
    isLoading,
    error,
    progress,
    generate,
    download,
    openResult,
    fetchFormats
  };
}
