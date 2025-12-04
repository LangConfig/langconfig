/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

interface Action {
  icon: string;
  label: string;
  description: string;
  color: 'primary' | 'blue' | 'purple' | 'green';
  onClick: () => void;
}

interface QuickActionsPanelProps {
  actions: Action[];
}

export default function QuickActionsPanel({ actions }: QuickActionsPanelProps) {
  const getColorClasses = (color: Action['color']) => {
    switch (color) {
      case 'primary':
        return {
          bg: 'bg-primary/10 group-hover:bg-primary/20',
          icon: 'text-primary'
        };
      case 'blue':
        return {
          bg: 'bg-blue-500/10 group-hover:bg-blue-500/20',
          icon: 'text-blue-600 dark:text-blue-400'
        };
      case 'purple':
        return {
          bg: 'bg-purple-500/10 group-hover:bg-purple-500/20',
          icon: 'text-purple-600 dark:text-purple-400'
        };
      case 'green':
        return {
          bg: 'bg-green-500/10 group-hover:bg-green-500/20',
          icon: 'text-green-600 dark:text-green-400'
        };
    }
  };

  return (
    <div className="p-6 rounded-lg border border-gray-200 dark:border-border-dark bg-gradient-to-br from-primary/5 to-transparent">
      <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--color-text-primary)' }}>
        Quick Actions
      </h3>
      <div className={`grid grid-cols-1 ${actions.length > 1 ? 'md:grid-cols-2' : ''} gap-3`}>
        {actions.map((action, index) => {
          const colors = getColorClasses(action.color);
          return (
            <button
              key={index}
              onClick={action.onClick}
              className="flex items-center gap-3 p-4 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark hover:border-primary transition-colors group"
            >
              <div className={`w-10 h-10 rounded-lg ${colors.bg} flex items-center justify-center transition-colors`}>
                <span className={`material-symbols-outlined text-xl ${colors.icon}`}>
                  {action.icon}
                </span>
              </div>
              <div className="text-left">
                <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  {action.label}
                </p>
                <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  {action.description}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
