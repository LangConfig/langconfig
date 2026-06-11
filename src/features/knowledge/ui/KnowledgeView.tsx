/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState } from 'react';
import { Database, GitBranch } from 'lucide-react';
import KnowledgeBaseView from './KnowledgeBaseView';
import RepositoriesPanel from './repositories/RepositoriesPanel';

type KnowledgeTab = 'documents' | 'repositories';

const TABS: { id: KnowledgeTab; label: string; icon: typeof Database }[] = [
  { id: 'documents', label: 'Documents', icon: Database },
  { id: 'repositories', label: 'Repositories', icon: GitBranch },
];

/**
 * Knowledge area wrapper — segmented toggle between the document-based
 * Knowledge Base and the read-only git repository browser.
 */
export default function KnowledgeView() {
  const [tab, setTab] = useState<KnowledgeTab>('documents');

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-background-light">
      {/* Segmented toggle */}
      <div className="flex items-center gap-2 px-6 py-3 border-b-2 border-border-dark bg-panel-dark shrink-0">
        <div className="inline-flex items-center gap-1 border-2 border-border-dark rounded-[4px] bg-background-light p-1">
          {TABS.map(({ id, label, icon: Icon }) => {
            const active = tab === id;
            return (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-[3px] text-[11px] font-mono font-bold uppercase tracking-wide transition-all border-2 ${
                  active
                    ? 'bg-white border-border-dark text-text-primary shadow-[2px_2px_0_var(--color-border-dark)]'
                    : 'border-transparent text-text-muted hover:text-text-primary hover:bg-black/[0.04]'
                }`}
              >
                <Icon size={13} />
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Active panel */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {tab === 'documents' ? <KnowledgeBaseView /> : <RepositoriesPanel />}
      </div>
    </div>
  );
}
