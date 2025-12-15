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
    <header className="flex items-center justify-between whitespace-nowrap border-b px-4 py-4 z-20 shrink-0 h-20" style={{ backgroundColor: 'var(--color-primary)', borderBottomColor: 'var(--color-border-dark)' }}>
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
          {/* GhostPeony Avatar Icon - rotated 45deg right */}
          <img
            src="/GhostPeony.png"
            alt="GhostPeony"
            style={{
              height: '68px',
              width: '68px',
              display: 'block',
              borderRadius: '14px',
              objectFit: 'cover',
              transform: 'rotate(-45deg)', // 45 degrees to the right
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
              filter: 'brightness(0) invert(1)', // Makes the logo white
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
          className={`px-4 py-2 text-sm rounded-lg transition-all border ${currentView === 'studio'
            ? 'bg-white/30 text-white font-semibold border-white/40'
            : 'text-white/90 font-medium hover:bg-white/15 hover:text-white border-transparent hover:border-white/20'
            } `}
          style={{
            textShadow: currentView === 'studio' ? '0 1px 2px rgba(0, 0, 0, 0.25)' : '0 1px 2px rgba(0, 0, 0, 0.15)',
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
          className={`px-4 py-2 text-sm rounded-lg transition-all border ${currentView === 'agents'
            ? 'bg-white/30 text-white font-semibold border-white/40'
            : 'text-white/90 font-medium hover:bg-white/15 hover:text-white border-transparent hover:border-white/20'
            } `}
          style={{
            textShadow: currentView === 'agents' ? '0 1px 2px rgba(0, 0, 0, 0.25)' : '0 1px 2px rgba(0, 0, 0, 0.15)',
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
          className={`px-4 py-2 text-sm rounded-lg transition-all border ${currentView === 'library'
            ? 'bg-white/30 text-white font-semibold border-white/40'
            : 'text-white/90 font-medium hover:bg-white/15 hover:text-white border-transparent hover:border-white/20'
            } `}
          style={{
            textShadow: currentView === 'library' ? '0 1px 2px rgba(0, 0, 0, 0.25)' : '0 1px 2px rgba(0, 0, 0, 0.15)',
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
          className={`px-4 py-2 text-sm rounded-lg transition-all border ${currentView === 'knowledge'
            ? 'bg-white/30 text-white font-semibold border-white/40'
            : 'text-white/90 font-medium hover:bg-white/15 hover:text-white border-transparent hover:border-white/20'
            }`}
          style={{
            textShadow: currentView === 'knowledge' ? '0 1px 2px rgba(0, 0, 0, 0.25)' : '0 1px 2px rgba(0, 0, 0, 0.15)',
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
          className={`px-4 py-2 text-sm rounded-lg transition-all border ${currentView === 'community'
            ? 'bg-white/30 text-white font-semibold border-white/40'
            : 'text-white/90 font-medium hover:bg-white/15 hover:text-white border-transparent hover:border-white/20'
            }`}
          style={{
            textShadow: currentView === 'community' ? '0 1px 2px rgba(0, 0, 0, 0.25)' : '0 1px 2px rgba(0, 0, 0, 0.15)',
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
          className="flex items-center justify-center h-10 w-10 rounded-lg hover:bg-white/15 transition-all text-white/90 hover:text-white border border-transparent hover:border-white/20"
          title="Chat (Ctrl+K)"
          style={{
            textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)'
          }}
        >
          <MessageSquare className="w-5 h-5" />
        </button>

        {/* Project Selector */}
        <div className="relative">
          <button
            onClick={() => setShowProjectDropdown(!showProjectDropdown)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/15 transition-all text-white/90 hover:text-white border border-white/20 hover:border-white/40"
            style={{
              textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)',
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
                className="absolute right-0 mt-2 w-64 rounded-lg shadow-lg border z-40 max-h-96 overflow-auto"
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
          className="flex items-center justify-center h-10 w-10 rounded-lg hover:bg-white/15 transition-all text-white/90 hover:text-white border border-transparent hover:border-white/20"
          title="Settings"
          style={{
            textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)'
          }}
        >
          <span className="material-symbols-outlined text-base">settings</span>
        </button>
      </div>
    </header>
  );
}
