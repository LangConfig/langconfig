/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState } from 'react';
import { MessageSquare } from 'lucide-react';
import { useProject } from "../../contexts/ProjectContext";
import { useChat } from '../../features/chat/state/ChatContext';

interface ModernHeaderProps {
  currentView: 'studio' | 'library' | 'settings' | 'knowledge' | 'agents' | 'skills' | 'home' | 'community';
  onViewChange: (view: 'studio' | 'library' | 'settings' | 'knowledge' | 'agents' | 'skills' | 'home' | 'community') => void;
}

export default function ModernHeader({
  currentView,
  onViewChange
}: ModernHeaderProps) {
  const { activeProject, projects, setActiveProjectId, loading } = useProject();
  const { openChat } = useChat();
  const [showProjectDropdown, setShowProjectDropdown] = useState(false);

  return (
    <header className="flex items-center justify-between whitespace-nowrap border-b-2 px-4 py-4 z-20 shrink-0 h-20" style={{ backgroundColor: 'var(--color-panel-dark)', borderBottomColor: 'var(--color-border-dark)' }}>
      {/* Left: Logo - centered over agent library sidebar */}
      <div className="flex items-center h-full justify-center" style={{ width: '320px', marginLeft: '-16px' }}>

        <button
          onClick={() => onViewChange('home')}
          style={{
            backgroundColor: 'transparent',
            borderRadius: '0',
            padding: '0',
            boxShadow: 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '16px',
            overflow: 'visible',
            height: '70px',
            maxWidth: '280px',
            border: 'none',
            cursor: 'pointer',
          }}
        >
          {/* Peony brand mark */}
          <img
            src="/peony.png"
            alt="LangConfig Peony"
            style={{
              height: '62px',
              width: '62px',
              display: 'block',
              borderRadius: '4px',
              objectFit: 'cover',
              border: '2px solid rgba(255, 250, 240, 0.85)',
              boxShadow: '4px 4px 0 var(--color-border-dark)',
            }}
          />
          {/* LangConfig Logo */}
          <img
            src="/langconfignewlogo.png"
            alt="LangConfig"
            style={{
              height: '100px',
              width: 'auto',
              display: 'block',
              filter: 'brightness(0) saturate(100%) invert(15%) sepia(47%) saturate(923%) hue-rotate(166deg) brightness(90%) contrast(94%)',
              margin: '0',
              marginTop: '15px', // Shift logo down slightly
            }}
          />
        </button>
      </div>

      {/* Center: Navigation Tabs */}
      <nav className="flex items-center gap-2 absolute left-1/2 transform -translate-x-1/2">
        <button
          onClick={() => onViewChange('studio')}
          className={`px-4 py-2 text-sm rounded-[4px] transition-all border-2 ${currentView === 'studio'
            ? 'bg-background-light/70 font-semibold border-border-dark shadow-[3px_3px_0_var(--color-border-dark)]'
            : 'font-medium hover:bg-background-light/45 border-transparent hover:border-border-dark'
            } `}
          style={{
            color: 'var(--color-text-primary)',
            backdropFilter: currentView === 'studio' ? 'blur(8px)' : 'none'
          }}
        >
          <span className="flex items-center gap-2">
            <span className="material-symbols-outlined text-base">account_tree</span>
            Studio
          </span>
        </button>
        <button
          onClick={() => onViewChange('agents')}
          className={`px-4 py-2 text-sm rounded-[4px] transition-all border-2 ${currentView === 'agents'
            ? 'bg-background-light/70 font-semibold border-border-dark shadow-[3px_3px_0_var(--color-border-dark)]'
            : 'font-medium hover:bg-background-light/45 border-transparent hover:border-border-dark'
            } `}
          style={{
            color: 'var(--color-text-primary)',
            backdropFilter: currentView === 'agents' ? 'blur(8px)' : 'none'
          }}
        >
          <span className="flex items-center gap-2">
            <span className="material-symbols-outlined text-base">psychology</span>
            Agents
          </span>
        </button>
        <button
          onClick={() => onViewChange('library')}
          className={`px-4 py-2 text-sm rounded-[4px] transition-all border-2 ${currentView === 'library'
            ? 'bg-background-light/70 font-semibold border-border-dark shadow-[3px_3px_0_var(--color-border-dark)]'
            : 'font-medium hover:bg-background-light/45 border-transparent hover:border-border-dark'
            } `}
          style={{
            color: 'var(--color-text-primary)',
            backdropFilter: currentView === 'library' ? 'blur(8px)' : 'none'
          }}
        >
          <span className="flex items-center gap-2">
            <span className="material-symbols-outlined text-base">folder</span>
            Library
          </span>
        </button>
        <button
          onClick={() => onViewChange('knowledge')}
          className={`px-4 py-2 text-sm rounded-[4px] transition-all border-2 ${currentView === 'knowledge'
            ? 'bg-background-light/70 font-semibold border-border-dark shadow-[3px_3px_0_var(--color-border-dark)]'
            : 'font-medium hover:bg-background-light/45 border-transparent hover:border-border-dark'
            }`}
          style={{
            color: 'var(--color-text-primary)',
            backdropFilter: currentView === 'knowledge' ? 'blur(8px)' : 'none'
          }}
        >
          <span className="flex items-center gap-2">
            <span className="material-symbols-outlined text-base">database</span>
            Knowledge
          </span>
        </button>
        <button
          onClick={() => onViewChange('community')}
          className={`px-4 py-2 text-sm rounded-[4px] transition-all border-2 ${currentView === 'community'
            ? 'bg-background-light/70 font-semibold border-border-dark shadow-[3px_3px_0_var(--color-border-dark)]'
            : 'font-medium hover:bg-background-light/45 border-transparent hover:border-border-dark'
            }`}
          style={{
            color: 'var(--color-text-primary)',
            backdropFilter: currentView === 'community' ? 'blur(8px)' : 'none'
          }}
        >
          <span className="flex items-center gap-2">
            <span className="material-symbols-outlined text-base">groups</span>
            Community
          </span>
        </button>
      </nav>

      {/* Right: Project Selector & Action Buttons */}
      <div className="flex items-center gap-2">
        {/* Chat Button */}
        <button
          onClick={() => openChat()}
          className="flex items-center justify-center h-10 w-10 rounded-[4px] hover:bg-background-light/45 transition-all border-2 border-transparent hover:border-border-dark"
          title="Chat (Ctrl+K)"
          style={{
            color: 'var(--color-text-primary)'
          }}
        >
          <MessageSquare className="w-5 h-5" />
        </button>

        {/* Project Selector */}
        <div className="relative">
          <button
            onClick={() => setShowProjectDropdown(!showProjectDropdown)}
            className="flex items-center gap-2 px-3 py-2 rounded-[4px] hover:bg-background-light/45 transition-all border-2 border-border-dark"
            style={{
              color: 'var(--color-text-primary)',
              minWidth: '150px'
            }}
          >
            <span className="material-symbols-outlined text-base">folder_open</span>
            <span className="text-sm font-medium truncate">
              {loading ? 'Loading...' : activeProject?.name || 'No Project'}
            </span>
            <span className="material-symbols-outlined text-base ml-auto">
              {showProjectDropdown ? 'expand_less' : 'expand_more'}
            </span>
          </button>

          {/* Dropdown */}
          {showProjectDropdown && (
            <>
              <div
                className="fixed inset-0 z-30"
                onClick={() => setShowProjectDropdown(false)}
              />
              <div
                className="absolute right-0 mt-2 w-64 rounded-[4px] border-2 z-40 max-h-96 overflow-auto shadow-[4px_4px_0_var(--color-border-dark)]"
                style={{
                  backgroundColor: 'var(--color-panel-dark)',
                  borderColor: 'var(--color-border-dark)'
                }}
              >
                {projects.length === 0 ? (
                  <div className="px-4 py-3 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                    No projects found
                  </div>
                ) : (
                  projects.map(project => (
                    <button
                      key={project.id}
                      onClick={() => {
                        setActiveProjectId(project.id);
                        setShowProjectDropdown(false);
                      }}
                      className="w-full px-4 py-2 text-left hover:bg-white/5 transition-all flex items-center justify-between"
                    >
                      <div className="flex-1 min-w-0">
                        <div
                          className="text-sm font-medium truncate"
                          style={{ color: activeProject?.id === project.id ? 'var(--color-primary)' : 'var(--color-text-primary)' }}
                        >
                          {project.name}
                        </div>
                        {project.description && (
                          <div className="text-xs truncate" style={{ color: 'var(--color-text-muted)' }}>
                            {project.description}
                          </div>
                        )}
                      </div>
                      {activeProject?.id === project.id && (
                        <span className="material-symbols-outlined text-base ml-2" style={{ color: 'var(--color-primary)' }}>
                          check
                        </span>
                      )}
                    </button>
                  ))
                )}
              </div>
            </>
          )}
        </div>

        <button
          onClick={() => onViewChange('settings')}
          className="flex items-center justify-center h-10 w-10 rounded-[4px] hover:bg-background-light/45 transition-all border-2 border-transparent hover:border-border-dark"
          title="Settings"
          style={{
            color: 'var(--color-text-primary)'
          }}
        >
          <span className="material-symbols-outlined text-base">settings</span>
        </button>
      </div>
    </header>
  );
}
