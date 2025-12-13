/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState } from 'react';
import SettingsSection, { SettingsInput, SettingsCheckbox } from './SettingsSection';

interface LocalWorkspaceSettingsProps {
  settings: {
    workspacePath: string;
    allowRead: boolean;
    allowWrite: boolean;
    requireApproval: boolean;
    autoDetectGit: boolean;
    backupBeforeEdit: boolean;
  };
  onSettingsChange: (settings: any) => void;
}

export default function LocalWorkspaceSettings({
  settings,
  onSettingsChange
}: LocalWorkspaceSettingsProps) {
  const [isSelectingFolder, setIsSelectingFolder] = useState(false);

  const handleBrowse = async () => {
    setIsSelectingFolder(true);
    try {
      // Use the native file dialog via Tauri
      // @ts-ignore - Tauri API
      if (window.__TAURI__) {
        // @ts-ignore
        const { open } = await import('@tauri-apps/plugin-dialog');
        const selected = await open({
          directory: true,
          multiple: false,
          defaultPath: settings.workspacePath || undefined
        });

        if (selected && typeof selected === 'string') {
          onSettingsChange({ ...settings, workspacePath: selected });
        }
      } else {
        // Fallback for web development mode
        alert('Folder selection is only available in the desktop app. Please enter the path manually.');
      }
    } catch (error) {
      console.error('Error selecting folder:', error);
    } finally {
      setIsSelectingFolder(false);
    }
  };

  return (
    <div>
      <SettingsSection
        title="Local Workspace"
        description="Configure workspace access for coding agents. Agents can read and write files in your workspace to help with development tasks."
        icon="folder_open"
      >
        {/* Workspace Path */}
        <div className="flex gap-2">
          <div className="flex-1">
            <SettingsInput
              label="Workspace Directory"
              value={settings.workspacePath}
              onChange={(value) => onSettingsChange({ ...settings, workspacePath: value })}
              placeholder="C:\Users\YourName\projects\myapp"
              description="The root directory where agents can access files. Only files within this directory will be accessible."
              required
            />
          </div>
          <div className="pt-6">
            <button
              onClick={handleBrowse}
              disabled={isSelectingFolder}
              className="px-4 py-2 text-sm font-medium bg-white dark:bg-background-dark border border-gray-300 dark:border-border-dark rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors disabled:opacity-50"
              style={{ color: 'var(--color-text-primary)' }}
            >
              {isSelectingFolder ? 'Selecting...' : 'Browse...'}
            </button>
          </div>
        </div>

        {/* File Permissions */}
        <div className="border-t border-gray-200 dark:border-border-dark pt-4 mt-4">
          <h4 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-text-primary)' }}>
            Agent File Permissions
          </h4>
          <div className="space-y-3">
            <SettingsCheckbox
              label="Allow agents to read files"
              checked={settings.allowRead}
              onChange={(checked) => onSettingsChange({ ...settings, allowRead: checked })}
              description="Agents can read file contents to understand your codebase and provide context-aware suggestions."
            />

            <SettingsCheckbox
              label="Allow agents to create/edit files"
              checked={settings.allowWrite}
              onChange={(checked) => onSettingsChange({ ...settings, allowWrite: checked })}
              description="Agents can propose changes to existing files or create new files. Changes will be shown for review before applying."
            />

            <SettingsCheckbox
              label="Require approval before writing files"
              checked={settings.requireApproval}
              onChange={(checked) => onSettingsChange({ ...settings, requireApproval: checked })}
              disabled={!settings.allowWrite}
              description="Show a diff viewer and require manual approval before any file modifications are applied."
            />
          </div>
        </div>

        {/* Git Integration */}
        <div className="border-t border-gray-200 dark:border-border-dark pt-4 mt-4">
          <h4 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-text-primary)' }}>
            Version Control
          </h4>
          <div className="space-y-3">
            <SettingsCheckbox
              label="Auto-detect git repository"
              checked={settings.autoDetectGit}
              onChange={(checked) => onSettingsChange({ ...settings, autoDetectGit: checked })}
              description="Automatically detect if the workspace is a git repository and show repository information."
            />

            <SettingsCheckbox
              label="Backup files before agent edits"
              checked={settings.backupBeforeEdit}
              onChange={(checked) => onSettingsChange({ ...settings, backupBeforeEdit: checked })}
              description="Create automatic backups of files before applying agent modifications. Backups are stored in .langconfig/backups/"
            />
          </div>
        </div>

        {/* Warning Notice */}
        {settings.allowWrite && !settings.requireApproval && (
          <div className="flex gap-3 p-4 bg-yellow-50 dark:bg-yellow-500/10 border border-yellow-200 dark:border-yellow-500/30 rounded-lg">
            <span className="material-symbols-outlined text-yellow-600 dark:text-yellow-400 text-xl">
              warning
            </span>
            <div>
              <h5 className="text-sm font-semibold text-yellow-800 dark:text-yellow-400 mb-1">
                Security Warning
              </h5>
              <p className="text-xs text-yellow-700 dark:text-yellow-400/80">
                Agents can modify files without approval. It's strongly recommended to enable "Require approval before writing files"
                and keep "Backup files before agent edits" enabled to prevent accidental data loss.
              </p>
            </div>
          </div>
        )}
      </SettingsSection>

      {/* Usage Instructions */}
      <SettingsSection
        title="How It Works"
        icon="info"
      >
        <div className="space-y-3 text-sm" style={{ color: 'var(--color-text-muted)' }}>
          <div>
            <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
              Coding Agent Workflow:
            </h4>
            <ol className="list-decimal list-inside space-y-1 ml-2">
              <li>Create a workflow with coding agent nodes</li>
              <li>Agents will have access to the "local_files" tool</li>
              <li>Agents can read your code for context and understanding</li>
              <li>When agents propose changes, you'll see a diff viewer</li>
              <li>Review and approve/reject each change individually</li>
              <li>Changes are applied to your workspace directory</li>
              <li>Commit changes to git yourself using your IDE or terminal</li>
            </ol>
          </div>

          <div>
            <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
              Security & Privacy:
            </h4>
            <ul className="list-disc list-inside space-y-1 ml-2">
              <li>Agents can only access files within the configured workspace directory</li>
              <li>All file operations require explicit permission</li>
              <li>File contents are only sent to LLM providers when needed for context</li>
              <li>Backups are created locally before any modifications</li>
              <li>You maintain full control - commit changes yourself when ready</li>
            </ul>
          </div>

          <div>
            <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
              Best Practices:
            </h4>
            <ul className="list-disc list-inside space-y-1 ml-2">
              <li>Always have your workspace under version control (git)</li>
              <li>Enable approval requirement for write operations</li>
              <li>Review all diffs carefully before applying changes</li>
              <li>Keep backup enabled to prevent accidental data loss</li>
              <li>Use specific agent prompts to limit scope of changes</li>
            </ul>
          </div>
        </div>
      </SettingsSection>
    </div>
  );
}
