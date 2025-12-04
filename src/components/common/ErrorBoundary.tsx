/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Error Boundary Component
 *
 * Catches JavaScript errors in child component tree and displays fallback UI.
 * Prevents entire app from crashing due to a single component error.
 *
 * Usage:
 * <ErrorBoundary>
 *   <YourComponent />
 * </ErrorBoundary>
 */

import React, { Component, ReactNode } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    // Update state so the next render will show the fallback UI
    return {
      hasError: true,
      error,
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log error to console in development
    console.error('Error caught by boundary:', error, errorInfo);

    // Call optional error handler
    this.props.onError?.(error, errorInfo);

    // Store error info in state
    this.setState({
      errorInfo,
    });

    // In production, you might want to send this to an error tracking service
    // Example: Sentry.captureException(error, { extra: errorInfo });
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  render() {
    if (this.state.hasError) {
      // Custom fallback UI provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default fallback UI
      return (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '400px',
            padding: '40px 20px',
            textAlign: 'center',
          }}
        >
          <div
            style={{
              backgroundColor: '#fee2e2',
              border: '1px solid #fecaca',
              borderRadius: '12px',
              padding: '32px',
              maxWidth: '600px',
            }}
          >
            <AlertCircle
              size={48}
              style={{ color: '#dc2626', marginBottom: '16px' }}
            />
            <h2
              style={{
                fontSize: '24px',
                fontWeight: '600',
                color: '#991b1b',
                marginBottom: '12px',
              }}
            >
              Something went wrong
            </h2>
            <p
              style={{
                fontSize: '16px',
                color: '#7f1d1d',
                marginBottom: '24px',
                lineHeight: '1.5',
              }}
            >
              We encountered an unexpected error. The error has been logged and
              we're working to fix it.
            </p>

            {/* Show error details in development */}
            {import.meta.env.DEV && this.state.error && (
              <details
                style={{
                  textAlign: 'left',
                  backgroundColor: '#fef2f2',
                  padding: '16px',
                  borderRadius: '8px',
                  marginBottom: '20px',
                  fontSize: '14px',
                  fontFamily: 'monospace',
                }}
              >
                <summary
                  style={{
                    cursor: 'pointer',
                    fontWeight: '600',
                    marginBottom: '8px',
                  }}
                >
                  Error Details (Development Only)
                </summary>
                <pre
                  style={{
                    overflow: 'auto',
                    color: '#991b1b',
                    margin: 0,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {this.state.error.toString()}
                  {this.state.errorInfo?.componentStack}
                </pre>
              </details>
            )}

            <button
              onClick={this.handleReset}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                backgroundColor: '#dc2626',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                padding: '12px 24px',
                fontSize: '16px',
                fontWeight: '500',
                cursor: 'pointer',
                transition: 'background-color 0.2s',
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.backgroundColor = '#b91c1c')
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.backgroundColor = '#dc2626')
              }
            >
              <RefreshCw size={18} />
              Try Again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * Higher-order component that wraps a component in an Error Boundary
 */
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  fallback?: ReactNode,
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void
) {
  return function WithErrorBoundary(props: P) {
    return (
      <ErrorBoundary fallback={fallback} onError={onError}>
        <Component {...props} />
      </ErrorBoundary>
    );
  };
}
