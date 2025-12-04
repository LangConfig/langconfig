/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { Clock, Hash, Activity, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface SearchMetrics {
  query: string;
  use_hyde: boolean;
  hyde_auto_detected: boolean;
  use_toon: boolean;
  top_k: number;
  retrieval_duration_ms: number;
  query_tokens: number;
  total_context_tokens: number;
  results_count: number;
  avg_similarity_score: number;
  max_similarity_score: number;
  min_similarity_score: number;
}

interface SearchMetricsDisplayProps {
  metrics: SearchMetrics;
  comparisonMetrics?: SearchMetrics; // For side-by-side comparison
  className?: string;
}

export default function SearchMetricsDisplay({ metrics, comparisonMetrics, className = '' }: SearchMetricsDisplayProps) {
  const formatDuration = (ms: number) => `${ms.toFixed(0)}ms`;
  const formatScore = (score: number) => (score * 100).toFixed(1) + '%';

  // Calculate differences if we have comparison data
  const getDifference = (current: number, comparison: number) => {
    if (!comparisonMetrics) return null;
    const diff = current - comparison;
    const percentDiff = (diff / comparison) * 100;
    return { diff, percentDiff };
  };

  const tokenDiff = getDifference(metrics.total_context_tokens, comparisonMetrics?.total_context_tokens || 0);
  const latencyDiff = getDifference(metrics.retrieval_duration_ms, comparisonMetrics?.retrieval_duration_ms || 0);
  const similarityDiff = getDifference(metrics.avg_similarity_score, comparisonMetrics?.avg_similarity_score || 0);

  const DiffIndicator = ({ diff, isLowerBetter = false }: { diff: { diff: number; percentDiff: number } | null; isLowerBetter?: boolean }) => {
    if (!diff || Math.abs(diff.percentDiff) < 0.1) {
      return <Minus className="w-3 h-3 text-gray-400" />;
    }

    const isPositive = isLowerBetter ? diff.diff < 0 : diff.diff > 0;
    const Icon = isPositive ? TrendingUp : TrendingDown;
    const colorClass = isPositive ? 'text-green-500' : 'text-red-500';

    return (
      <span className={`flex items-center gap-1 text-xs ${colorClass}`}>
        <Icon className="w-3 h-3" />
        {Math.abs(diff.percentDiff).toFixed(1)}%
      </span>
    );
  };

  return (
    <div className={`bg-white dark:bg-panel-dark border border-gray-200 dark:border-border-dark rounded-lg p-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
          Search Metrics {comparisonMetrics && '(Comparison)'}
        </h3>
        <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
          {metrics.use_hyde && (
            <span className="px-2 py-0.5 bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-400 rounded">
              HyDE {metrics.hyde_auto_detected ? '(Auto)' : ''}
            </span>
          )}
          {metrics.use_toon && (
            <span className="px-2 py-0.5 bg-purple-100 dark:bg-purple-500/20 text-purple-700 dark:text-purple-400 rounded">
              TOON
            </span>
          )}
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {/* Results Count */}
        <div className="flex flex-col">
          <div className="flex items-center gap-1 text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>
            <Hash className="w-3 h-3" />
            <span>Results</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>{metrics.results_count}</span>
            {comparisonMetrics && (
              <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>vs {comparisonMetrics.results_count}</span>
            )}
          </div>
        </div>

        {/* Tokens */}
        <div className="flex flex-col">
          <div className="flex items-center gap-1 text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>
            <Activity className="w-3 h-3" />
            <span>Total Tokens</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              {metrics.total_context_tokens.toLocaleString()}
            </span>
            {comparisonMetrics && <DiffIndicator diff={tokenDiff} isLowerBetter={true} />}
          </div>
          {comparisonMetrics && (
            <span className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
              vs {comparisonMetrics.total_context_tokens.toLocaleString()}
            </span>
          )}
        </div>

        {/* Latency */}
        <div className="flex flex-col">
          <div className="flex items-center gap-1 text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>
            <Clock className="w-3 h-3" />
            <span>Retrieval Time</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              {formatDuration(metrics.retrieval_duration_ms)}
            </span>
            {comparisonMetrics && <DiffIndicator diff={latencyDiff} isLowerBetter={true} />}
          </div>
          {comparisonMetrics && (
            <span className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
              vs {formatDuration(comparisonMetrics.retrieval_duration_ms)}
            </span>
          )}
        </div>

        {/* Similarity */}
        <div className="flex flex-col">
          <div className="flex items-center gap-1 text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>
            <Activity className="w-3 h-3" />
            <span>Avg Similarity</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              {formatScore(metrics.avg_similarity_score)}
            </span>
            {comparisonMetrics && <DiffIndicator diff={similarityDiff} isLowerBetter={false} />}
          </div>
          {comparisonMetrics && (
            <span className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
              vs {formatScore(comparisonMetrics.avg_similarity_score)}
            </span>
          )}
        </div>
      </div>

      {/* Detailed Stats (Expandable Details) */}
      <div className="mt-3 pt-3 border-t border-gray-200 dark:border-border-dark">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
          <div>
            <span style={{ color: 'var(--color-text-muted)' }}>Query Tokens:</span>
            <span className="ml-1 font-medium" style={{ color: 'var(--color-text-primary)' }}>{metrics.query_tokens}</span>
          </div>
          <div>
            <span style={{ color: 'var(--color-text-muted)' }}>Top-K:</span>
            <span className="ml-1 font-medium" style={{ color: 'var(--color-text-primary)' }}>{metrics.top_k}</span>
          </div>
          <div>
            <span style={{ color: 'var(--color-text-muted)' }}>Max Similarity:</span>
            <span className="ml-1 font-medium" style={{ color: 'var(--color-text-primary)' }}>{formatScore(metrics.max_similarity_score)}</span>
          </div>
          <div>
            <span style={{ color: 'var(--color-text-muted)' }}>Min Similarity:</span>
            <span className="ml-1 font-medium" style={{ color: 'var(--color-text-primary)' }}>{formatScore(metrics.min_similarity_score)}</span>
          </div>
        </div>
      </div>

      {/* Comparison Summary (if comparing) */}
      {comparisonMetrics && tokenDiff && (
        <div className="mt-3 pt-3 border-t border-gray-200 dark:border-border-dark">
          <div className="text-xs font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>Difference Summary:</div>
          <div className="space-y-1 text-xs">
            <div className="flex items-center justify-between">
              <span style={{ color: 'var(--color-text-muted)' }}>Tokens:</span>
              <span className={tokenDiff.diff < 0 ? 'text-green-600 dark:text-green-400 font-medium' : 'text-red-600 dark:text-red-400 font-medium'}>
                {tokenDiff.diff < 0 ? '' : '+'}{tokenDiff.diff.toLocaleString()} ({tokenDiff.percentDiff > 0 ? '+' : ''}{tokenDiff.percentDiff.toFixed(1)}%)
              </span>
            </div>
            {latencyDiff && (
              <div className="flex items-center justify-between">
                <span style={{ color: 'var(--color-text-muted)' }}>Latency:</span>
                <span className={latencyDiff.diff < 0 ? 'text-green-600 dark:text-green-400 font-medium' : 'text-red-600 dark:text-red-400 font-medium'}>
                  {latencyDiff.diff > 0 ? '+' : ''}{latencyDiff.diff.toFixed(0)}ms ({latencyDiff.percentDiff > 0 ? '+' : ''}{latencyDiff.percentDiff.toFixed(1)}%)
                </span>
              </div>
            )}
            {similarityDiff && (
              <div className="flex items-center justify-between">
                <span style={{ color: 'var(--color-text-muted)' }}>Similarity:</span>
                <span className={similarityDiff.diff > 0 ? 'text-green-600 dark:text-green-400 font-medium' : 'text-red-600 dark:text-red-400 font-medium'}>
                  {similarityDiff.diff > 0 ? '+' : ''}{(similarityDiff.diff * 100).toFixed(2)}% ({similarityDiff.percentDiff > 0 ? '+' : ''}{similarityDiff.percentDiff.toFixed(1)}%)
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
