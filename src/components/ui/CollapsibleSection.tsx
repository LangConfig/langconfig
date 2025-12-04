/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface CollapsibleSectionProps {
  title: string;
  badge?: string;
  defaultExpanded: boolean;
  hasError?: boolean;
  icon?: React.ReactNode;
  children: React.ReactNode;
  alwaysExpanded?: boolean;
}

export default function CollapsibleSection({
  title,
  badge,
  defaultExpanded,
  hasError = false,
  icon,
  children,
  alwaysExpanded = false
}: CollapsibleSectionProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const toggleExpanded = () => {
    if (!alwaysExpanded) {
      setIsExpanded(!isExpanded);
    }
  };

  return (
    <div className="border rounded-lg overflow-hidden shadow-sm" style={{
      borderColor: 'var(--color-border-dark)',
      backgroundColor: 'var(--color-panel-dark)'
    }}>
      {/* Section Header */}
      <button
        onClick={toggleExpanded}
        className={`w-full flex items-center justify-between p-4 transition-all ${
          alwaysExpanded
            ? 'cursor-default'
            : 'cursor-pointer'
        }`}
        style={{
          backgroundColor: isExpanded && !alwaysExpanded
            ? 'var(--color-background-light)'
            : 'transparent'
        }}
        disabled={alwaysExpanded}
        onMouseEnter={(e) => {
          if (!alwaysExpanded) {
            e.currentTarget.style.backgroundColor = 'var(--color-background-light)';
          }
        }}
        onMouseLeave={(e) => {
          if (!alwaysExpanded && !isExpanded) {
            e.currentTarget.style.backgroundColor = 'transparent';
          }
        }}
      >
        <div className="flex items-center gap-3">
          {/* Chevron Icon - only if not alwaysExpanded */}
          {!alwaysExpanded && (
            isExpanded ? (
              <ChevronDown className="w-5 h-5 transition-transform" style={{ color: 'var(--color-primary)' }} />
            ) : (
              <ChevronRight className="w-5 h-5 transition-transform" style={{ color: 'var(--color-text-muted)' }} />
            )
          )}

          {/* Custom Icon */}
          {icon && <div style={{ color: 'var(--color-primary)' }}>{icon}</div>}

          {/* Title */}
          <h3 className="text-base font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            {title}
          </h3>

          {/* Error Indicator */}
          {hasError && (
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium" style={{
              backgroundColor: 'rgba(239, 68, 68, 0.1)',
              color: '#dc2626'
            }}>
              <span className="material-symbols-outlined text-sm">error</span>
              <span>Errors</span>
            </div>
          )}
        </div>

        {/* Badge */}
        {badge && (
          <span className="text-xs font-medium px-2 py-1 rounded" style={{
            backgroundColor: 'var(--color-background-light)',
            color: 'var(--color-primary)'
          }}>
            {badge}
          </span>
        )}
      </button>

      {/* Section Content */}
      {isExpanded && (
        <div
          className="p-4 border-t"
          style={{
            backgroundColor: 'var(--color-background-light)',
            borderTopColor: 'var(--color-border-dark)'
          }}
        >
          {children}
        </div>
      )}
    </div>
  );
}
