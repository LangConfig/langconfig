/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import apiClient from '../lib/api-client';

interface Project {
  id: number;
  name: string;
  description?: string;
  status: string;
  created_at: string;
  updated_at: string;
}

interface ProjectContextType {
  activeProjectId: number | null;
  activeProject: Project | null;
  projects: Project[];
  setActiveProjectId: (id: number) => void;
  refreshProjects: () => Promise<void>;
  loading: boolean;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [activeProjectId, setActiveProjectIdState] = useState<number | null>(() => {
    const stored = localStorage.getItem('activeProjectId');
    return stored ? parseInt(stored, 10) : null;
  });
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  // Fetch projects on mount
  const refreshProjects = async () => {
    try {
      setLoading(true);
      const response = await apiClient.listProjects();
      const projectList = response.data || [];
      setProjects(projectList);

      // If no active project set, default to first project
      if (!activeProjectId && projectList.length > 0) {
        setActiveProjectIdState(projectList[0].id);
        localStorage.setItem('activeProjectId', projectList[0].id.toString());
      }
    } catch (error) {
      console.error('Failed to fetch projects:', error);
      setProjects([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshProjects();
  }, []);

  const setActiveProjectId = (id: number) => {
    setActiveProjectIdState(id);
    localStorage.setItem('activeProjectId', id.toString());
  };

  const activeProject = projects.find(p => p.id === activeProjectId) || null;

  return (
    <ProjectContext.Provider
      value={{
        activeProjectId,
        activeProject,
        projects,
        setActiveProjectId,
        refreshProjects,
        loading,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  const context = useContext(ProjectContext);
  if (context === undefined) {
    throw new Error('useProject must be used within a ProjectProvider');
  }
  return context;
}
