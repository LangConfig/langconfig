/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect } from 'react';
import { ChevronDown, Loader, Search, Clock } from 'lucide-react';
import type { DeepAgent } from '../types/chat';
import apiClient from '../../../lib/api-client';

interface AgentSelectorProps {
  selectedAgentId: number | null;
  onSelectAgent: (agentId: number) => void;
  onClose?: () => void;
}

export default function AgentSelector({
  selectedAgentId,
  onSelectAgent,
  onClose
}: AgentSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [agents, setAgents] = useState<DeepAgent[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [recentAgents, setRecentAgents] = useState<number[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const selectedAgent = agents.find(a => a.id === selectedAgentId);

  // Load recent agents from localStorage
  useEffect(() => {
    const stored = localStorage.getItem('chat_recentAgents');
    if (stored) {
      try {
        setRecentAgents(JSON.parse(stored));
      } catch (e) {
        console.error('Failed to parse recent agents:', e);
      }
    }
  }, []);

  // Fetch agents when dropdown opens
  useEffect(() => {
    if (isOpen && agents.length === 0) {
      fetchAgents();
    }
  }, [isOpen]);

  const fetchAgents = async () => {
    setIsLoading(true);
    try {
      // Use the correct API method with public_only=false to get all agents
      const response = await apiClient.listDeepAgents({ public_only: false });
      console.log('Fetched agents:', response.data);
      setAgents(response.data || []);
    } catch (error) {
      console.error('Failed to fetch agents:', error);
      setAgents([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectAgent = (agentId: number) => {
    onSelectAgent(agentId);

    // Add to recent agents
    const updated = [agentId, ...recentAgents.filter(id => id !== agentId)].slice(0, 5);
    setRecentAgents(updated);
    localStorage.setItem('chat_recentAgents', JSON.stringify(updated));

    setIsOpen(false);
    if (onClose) onClose();
  };

  // Get unique categories
  const categories = Array.from(new Set(agents.map(a => a.category).filter(Boolean)));

  // Filter agents
  const filteredAgents = agents.filter(agent => {
    const matchesSearch =
      agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.description?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = !selectedCategory || agent.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  // Get recent agents (that exist in the list)
  const recentAgentsList = recentAgents
    .map(id => agents.find(a => a.id === id))
    .filter(Boolean) as DeepAgent[];

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors hover:bg-gray-50"
        style={{
          borderColor: 'var(--color-border-dark)',
          backgroundColor: 'white',
          color: 'var(--color-text-primary)',
        }}
      >
        <span className="text-sm font-medium">
          {selectedAgent ? selectedAgent.name : 'Select Agent'}
        </span>
        <ChevronDown className="w-4 h-4" />
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />
          <div
            className="absolute left-0 mt-2 w-96 rounded-lg shadow-lg border z-50 max-h-[32rem] overflow-hidden flex flex-col"
            style={{
              backgroundColor: 'white',
              borderColor: 'var(--color-border-dark)',
            }}
          >
            {/* Search */}
            <div
              className="p-3 border-b"
              style={{ borderColor: 'var(--color-border-dark)' }}
            >
              <div className="relative">
                <Search
                  className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
                  style={{ color: 'var(--color-text-muted)' }}
                />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search agents..."
                  className="w-full pl-10 pr-3 py-2 rounded border text-sm focus:outline-none focus:ring-2"
                  style={{
                    backgroundColor: 'var(--color-input-background)',
                    borderColor: 'var(--color-border-dark)',
                    color: 'var(--color-text-primary)',
                  }}
                  autoFocus
                />
              </div>

              {/* Category Filter */}
              {categories.length > 0 && (
                <div className="flex gap-2 mt-2 overflow-x-auto pb-1">
                  <button
                    onClick={() => setSelectedCategory(null)}
                    className="px-2 py-1 text-xs rounded transition-colors whitespace-nowrap"
                    style={{
                      backgroundColor: !selectedCategory ? 'var(--color-primary)' : 'transparent',
                      color: !selectedCategory ? 'white' : 'var(--color-text-muted)',
                      border: `1px solid ${!selectedCategory ? 'var(--color-primary)' : 'var(--color-border-dark)'}`,
                    }}
                  >
                    All
                  </button>
                  {categories.map(category => (
                    <button
                      key={category}
                      onClick={() => setSelectedCategory(category)}
                      className="px-2 py-1 text-xs rounded transition-colors whitespace-nowrap"
                      style={{
                        backgroundColor: selectedCategory === category ? 'var(--color-primary)' : 'transparent',
                        color: selectedCategory === category ? 'white' : 'var(--color-text-muted)',
                        border: `1px solid ${selectedCategory === category ? 'var(--color-primary)' : 'var(--color-border-dark)'}`,
                      }}
                    >
                      {category}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Agent List */}
            <div className="overflow-y-auto flex-1">
              {isLoading ? (
                <div className="p-4 flex items-center justify-center gap-2" style={{ color: 'var(--color-text-muted)' }}>
                  <Loader className="w-4 h-4 animate-spin" />
                  <span className="text-sm">Loading agents...</span>
                </div>
              ) : agents.length === 0 ? (
                <div className="p-4 text-center text-sm" style={{ color: 'var(--color-text-muted)' }}>
                  No agents available. Create a deep agent first.
                </div>
              ) : (
                <>
                  {/* Recent Agents */}
                  {!searchQuery && !selectedCategory && recentAgentsList.length > 0 && (
                    <>
                      <div
                        className="px-4 py-2 text-xs font-semibold flex items-center gap-2"
                        style={{ color: 'var(--color-text-muted)' }}
                      >
                        <Clock className="w-3 h-3" />
                        RECENT
                      </div>
                      {recentAgentsList.map((agent) => (
                        <AgentItem
                          key={`recent-${agent.id}`}
                          agent={agent}
                          isSelected={selectedAgentId === agent.id}
                          onClick={() => handleSelectAgent(agent.id)}
                        />
                      ))}
                      <div
                        className="my-2 border-t"
                        style={{ borderColor: 'var(--color-border-dark)' }}
                      />
                    </>
                  )}

                  {/* All Agents */}
                  {filteredAgents.length === 0 ? (
                    <div className="p-4 text-center text-sm" style={{ color: 'var(--color-text-muted)' }}>
                      No agents found matching your search
                    </div>
                  ) : (
                    filteredAgents.map((agent) => (
                      <AgentItem
                        key={agent.id}
                        agent={agent}
                        isSelected={selectedAgentId === agent.id}
                        onClick={() => handleSelectAgent(agent.id)}
                      />
                    ))
                  )}
                </>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

interface AgentItemProps {
  agent: DeepAgent;
  isSelected: boolean;
  onClick: () => void;
}

function AgentItem({ agent, isSelected, onClick }: AgentItemProps) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className="w-full px-4 py-3 text-left transition-colors border-b"
      style={{
        borderColor: 'var(--color-border-dark)',
        backgroundColor: isHovered ? 'var(--color-primary)' : 'transparent',
      }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div
            className="text-sm font-medium truncate flex items-center gap-2"
            style={{
              color: isHovered ? 'white' : isSelected ? 'var(--color-primary)' : 'var(--color-text-primary)',
            }}
          >
            {agent.name}
          </div>
          {agent.description && (
            <div
              className="text-xs mt-1 line-clamp-2"
              style={{ color: isHovered ? 'white' : 'var(--color-text-muted)' }}
            >
              {agent.description}
            </div>
          )}
          {agent.category && (
            <div
              className="text-xs mt-1 px-2 py-0.5 rounded inline-block"
              style={{
                backgroundColor: isHovered ? 'rgba(255, 255, 255, 0.2)' : 'var(--color-category-background)',
                color: isHovered ? 'white' : 'var(--color-text-muted)',
              }}
            >
              {agent.category}
            </div>
          )}
        </div>
        {isSelected && (
          <span className="material-symbols-outlined text-base" style={{ color: isHovered ? 'white' : 'var(--color-primary)' }}>
            check
          </span>
        )}
      </div>
    </button>
  );
}
