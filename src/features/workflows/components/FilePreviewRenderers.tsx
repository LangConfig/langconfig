/**
 * File Preview Renderers
 *
 * Shared preview components for CSV tables, JSON tree views, and SVG images.
 * Used by InlineFilePreview and FilesLibraryTab.
 *
 * Performance optimizations:
 * - React.memo prevents re-renders when content hasn't changed
 * - useMemo caches parsed data (CSV rows, JSON objects)
 * - Virtual rendering for large CSV tables (first 500 rows)
 */

import { useState, useMemo, memo } from 'react';
import { ChevronRight, ChevronDown } from 'lucide-react';

// ============================================================================
// CSV Table Preview
// ============================================================================

interface CsvPreviewProps {
  content: string;
  delimiter?: string;
}

function CsvPreviewComponent({ content, delimiter }: CsvPreviewProps) {
  const [sortColumn, setSortColumn] = useState<number | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  const { headers, rows } = useMemo(() => {
    // Auto-detect delimiter if not provided
    const firstLine = content.split('\n')[0] || '';
    const detectedDelimiter = delimiter || (firstLine.includes('\t') ? '\t' : ',');

    const lines = content.split('\n').filter(line => line.trim());
    if (lines.length === 0) return { headers: [], rows: [] };

    // Parse CSV properly handling quoted values
    const parseLine = (line: string): string[] => {
      const result: string[] = [];
      let current = '';
      let inQuotes = false;

      for (let i = 0; i < line.length; i++) {
        const char = line[i];
        if (char === '"') {
          inQuotes = !inQuotes;
        } else if (char === detectedDelimiter && !inQuotes) {
          result.push(current.trim());
          current = '';
        } else {
          current += char;
        }
      }
      result.push(current.trim());
      return result;
    };

    const headers = parseLine(lines[0]);
    const rows = lines.slice(1).map(parseLine);

    return { headers, rows };
  }, [content, delimiter]);

  const sortedRows = useMemo(() => {
    if (sortColumn === null) return rows;

    return [...rows].sort((a, b) => {
      const aVal = a[sortColumn] || '';
      const bVal = b[sortColumn] || '';

      // Try numeric sort first
      const aNum = parseFloat(aVal);
      const bNum = parseFloat(bVal);
      if (!isNaN(aNum) && !isNaN(bNum)) {
        return sortDirection === 'asc' ? aNum - bNum : bNum - aNum;
      }

      // Fall back to string sort
      return sortDirection === 'asc'
        ? aVal.localeCompare(bVal)
        : bVal.localeCompare(aVal);
    });
  }, [rows, sortColumn, sortDirection]);

  const handleSort = (columnIndex: number) => {
    if (sortColumn === columnIndex) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(columnIndex);
      setSortDirection('asc');
    }
  };

  if (headers.length === 0) {
    return <div className="text-gray-500 dark:text-text-muted p-4">Empty or invalid CSV file</div>;
  }

  return (
    <div className="overflow-auto h-full">
      <table className="min-w-full border-collapse text-sm">
        <thead className="sticky top-0 z-10">
          <tr>
            {headers.map((header, i) => (
              <th
                key={i}
                onClick={() => handleSort(i)}
                className="px-3 py-2 text-left font-semibold cursor-pointer hover:bg-gray-100 dark:hover:bg-white/5 transition-colors border-b border-gray-200 dark:border-border-dark bg-gray-50 dark:bg-black/30"
                style={{ color: 'var(--color-text-primary)' }}
              >
                <div className="flex items-center gap-1">
                  {header || `Column ${i + 1}`}
                  {sortColumn === i && (
                    <span className="text-xs opacity-60">
                      {sortDirection === 'asc' ? '↑' : '↓'}
                    </span>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedRows.slice(0, 500).map((row, rowIndex) => (
            <tr
              key={rowIndex}
              className="hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
            >
              {headers.map((_, colIndex) => (
                <td
                  key={colIndex}
                  className="px-3 py-2 border-b border-gray-100 dark:border-border-dark/50"
                  style={{ color: 'var(--color-text-primary)' }}
                >
                  {row[colIndex] || ''}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 500 && (
        <div className="p-3 text-center text-sm text-gray-500 dark:text-text-muted bg-gray-50 dark:bg-black/20 border-t border-gray-200 dark:border-border-dark">
          Showing first 500 of {rows.length} rows
        </div>
      )}
    </div>
  );
}

// Memoized export - only re-renders when content changes
export const CsvPreview = memo(CsvPreviewComponent);

// ============================================================================
// JSON Tree View
// ============================================================================

interface JsonNodeProps {
  name: string;
  value: any;
  depth: number;
  defaultExpanded?: boolean;
}

// Memoized JSON node to prevent re-renders of unchanged subtrees
const JsonNode = memo(function JsonNode({ name, value, depth, defaultExpanded = true }: JsonNodeProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded && depth < 2);

  const isObject = value !== null && typeof value === 'object';
  const isArray = Array.isArray(value);
  const isEmpty = isObject && Object.keys(value).length === 0;

  const getValueDisplay = () => {
    if (value === null) return <span className="text-gray-500">null</span>;
    if (value === undefined) return <span className="text-gray-500">undefined</span>;
    if (typeof value === 'boolean') return <span className="text-purple-500">{value.toString()}</span>;
    if (typeof value === 'number') return <span className="text-blue-500">{value}</span>;
    if (typeof value === 'string') {
      const truncated = value.length > 100 ? value.slice(0, 100) + '...' : value;
      return <span className="text-green-600 dark:text-green-400">"{truncated}"</span>;
    }
    return null;
  };

  const getBrackets = () => {
    if (isArray) return isEmpty ? '[]' : ['[', ']'];
    if (isObject) return isEmpty ? '{}' : ['{', '}'];
    return null;
  };

  const brackets = getBrackets();
  const entries = isObject ? Object.entries(value) : [];

  return (
    <div className="font-mono text-sm" style={{ marginLeft: depth > 0 ? '1rem' : 0 }}>
      <div className="flex items-start gap-1 py-0.5 hover:bg-gray-100 dark:hover:bg-white/5 rounded px-1 -mx-1">
        {isObject && !isEmpty ? (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex-shrink-0 w-4 h-4 flex items-center justify-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >
            {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          </button>
        ) : (
          <span className="w-4" />
        )}

        {name && (
          <span className="text-red-600 dark:text-red-400">"{name}"</span>
        )}
        {name && <span className="text-gray-500">: </span>}

        {isObject ? (
          <>
            <span className="text-gray-500">
              {typeof brackets === 'string' ? brackets : brackets?.[0]}
            </span>
            {!isExpanded && !isEmpty && (
              <span className="text-gray-400 text-xs">
                {isArray ? `${entries.length} items` : `${entries.length} keys`}
              </span>
            )}
            {!isExpanded && !isEmpty && (
              <span className="text-gray-500">{brackets?.[1]}</span>
            )}
          </>
        ) : (
          getValueDisplay()
        )}
      </div>

      {isObject && !isEmpty && isExpanded && (
        <div>
          {entries.map(([key, val]) => (
            <JsonNode
              key={key}
              name={isArray ? '' : key}
              value={val}
              depth={depth + 1}
              defaultExpanded={depth < 1}
            />
          ))}
          <div style={{ marginLeft: '1rem' }}>
            <span className="text-gray-500">{brackets?.[1]}</span>
          </div>
        </div>
      )}
    </div>
  );
});

interface JsonPreviewProps {
  content: string;
}

function JsonPreviewComponent({ content }: JsonPreviewProps) {
  const parsed = useMemo(() => {
    try {
      return { data: JSON.parse(content), error: null };
    } catch (e) {
      return { data: null, error: (e as Error).message };
    }
  }, [content]);

  if (parsed.error) {
    return (
      <div className="p-4">
        <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/30 rounded text-sm text-red-800 dark:text-red-200">
          Invalid JSON: {parsed.error}
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 overflow-auto h-full">
      <JsonNode name="" value={parsed.data} depth={0} />
    </div>
  );
}

// Memoized export
export const JsonPreview = memo(JsonPreviewComponent);

// ============================================================================
// SVG Preview
// ============================================================================

interface SvgPreviewProps {
  content: string;
}

function SvgPreviewComponent({ content }: SvgPreviewProps) {
  // Create a data URL for the SVG
  const svgDataUrl = useMemo(() => {
    // Encode the SVG content properly
    const encoded = encodeURIComponent(content);
    return `data:image/svg+xml,${encoded}`;
  }, [content]);

  return (
    <div className="h-full flex items-center justify-center p-4 bg-white dark:bg-gray-900">
      <div className="max-w-full max-h-full overflow-auto bg-white dark:bg-white/10 rounded-lg p-4 shadow-sm border border-gray-200 dark:border-border-dark">
        <img
          src={svgDataUrl}
          alt="SVG Preview"
          className="max-w-full max-h-[70vh] object-contain"
          style={{ minWidth: '100px', minHeight: '100px' }}
        />
      </div>
    </div>
  );
}

// Memoized export
export const SvgPreview = memo(SvgPreviewComponent);
