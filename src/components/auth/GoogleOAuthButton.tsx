/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect, useCallback, useRef } from 'react';

const API_BASE = 'http://localhost:8765';

interface GoogleOAuthStatus {
  connected: boolean;
  email?: string;
  expires_at?: string;
}

interface GoogleOAuthButtonProps {
  onConnectionChange?: (connected: boolean) => void;
  className?: string;
}

/**
 * GoogleOAuthButton Component
 *
 * Handles Google OAuth flow for connecting Google account for Slides API access.
 * Opens OAuth consent in a popup window and handles the callback.
 */
export default function GoogleOAuthButton({
  onConnectionChange,
  className = ''
}: GoogleOAuthButtonProps) {
  const [status, setStatus] = useState<GoogleOAuthStatus>({ connected: false });
  const [isLoading, setIsLoading] = useState(true);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasFetchedRef = useRef(false);
  const onConnectionChangeRef = useRef(onConnectionChange);

  // Keep ref updated
  onConnectionChangeRef.current = onConnectionChange;

  // Fetch current OAuth status
  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/auth/google/status`);
      if (response.ok) {
        const data = await response.json();
        setStatus(data);
        onConnectionChangeRef.current?.(data.connected);
      }
    } catch (err) {
      console.error('Failed to fetch Google OAuth status:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch status only once on mount
  useEffect(() => {
    if (hasFetchedRef.current) return;
    hasFetchedRef.current = true;
    fetchStatus();
  }, [fetchStatus]);

  // Handle OAuth popup message
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      // Verify origin
      if (event.origin !== API_BASE) return;

      if (event.data?.type === 'google-oauth-success') {
        setIsConnecting(false);
        setError(null);
        fetchStatus();
      } else if (event.data?.type === 'google-oauth-error') {
        setIsConnecting(false);
        setError(event.data.error || 'OAuth failed');
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [fetchStatus]);

  const handleConnect = async () => {
    setIsConnecting(true);
    setError(null);

    try {
      // Get OAuth URL from backend
      const response = await fetch(`${API_BASE}/api/auth/google/authorize`);
      if (!response.ok) {
        throw new Error('Failed to get authorization URL');
      }

      const { authorization_url } = await response.json();

      // Open popup
      const width = 600;
      const height = 700;
      const left = window.screenX + (window.outerWidth - width) / 2;
      const top = window.screenY + (window.outerHeight - height) / 2;

      const popup = window.open(
        authorization_url,
        'google-oauth',
        `width=${width},height=${height},left=${left},top=${top},scrollbars=yes`
      );

      // Poll for popup close (fallback if postMessage fails)
      const pollTimer = setInterval(() => {
        if (popup?.closed) {
          clearInterval(pollTimer);
          setIsConnecting(false);
          fetchStatus(); // Refresh status when popup closes
        }
      }, 500);

    } catch (err) {
      setIsConnecting(false);
      setError(err instanceof Error ? err.message : 'Connection failed');
    }
  };

  const handleDisconnect = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/auth/google/disconnect`, {
        method: 'DELETE'
      });

      if (response.ok) {
        setStatus({ connected: false });
        onConnectionChange?.(false);
      } else {
        throw new Error('Failed to disconnect');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Disconnect failed');
    }
  };

  if (isLoading) {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <div className="w-4 h-4 border-2 border-gray-300 border-t-primary rounded-full animate-spin" />
        <span className="text-sm text-gray-500">Checking connection...</span>
      </div>
    );
  }

  if (status.connected) {
    return (
      <div className={`flex items-center gap-3 ${className}`}>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500" />
          <span className="text-sm text-gray-600 dark:text-gray-400">
            Connected as {status.email}
          </span>
        </div>
        <button
          onClick={handleDisconnect}
          className="px-3 py-1.5 text-sm text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
        >
          Disconnect
        </button>
      </div>
    );
  }

  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      <button
        onClick={handleConnect}
        disabled={isConnecting}
        className="flex items-center justify-center gap-2 px-4 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isConnecting ? (
          <>
            <div className="w-4 h-4 border-2 border-gray-300 border-t-primary rounded-full animate-spin" />
            <span className="text-sm">Connecting...</span>
          </>
        ) : (
          <>
            {/* Google Icon */}
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Connect Google Account
            </span>
          </>
        )}
      </button>

      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}
    </div>
  );
}
