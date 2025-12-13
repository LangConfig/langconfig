/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, ReactNode } from 'react';
import SettingsSidebar from './SettingsSidebar';

export type SettingsCategory =
  | 'api-keys'
  | 'local-models'
  | 'local-workspace'
  | 'model-defaults'
  | 'backend'
  | 'workflow'
  | 'general'
  | 'appearance'
  | 'about';

interface SettingsLayoutProps {
  children: ReactNode;
  currentCategory: SettingsCategory;
  onCategoryChange: (category: SettingsCategory) => void;
}

export default function SettingsLayout({
  children,
  currentCategory,
  onCategoryChange
}: SettingsLayoutProps) {
  return (
    <div className="flex h-full w-full overflow-hidden bg-background-light dark:bg-background-dark">
      {/* Centered Container for Sidebar + Content */}
      <div className="flex max-w-[1200px] w-full mx-auto h-full overflow-hidden">
        {/* Left Sidebar - 240px fixed */}
        <SettingsSidebar
          currentCategory={currentCategory}
          onCategoryChange={onCategoryChange}
        />

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Scrollable Content */}
          <div className="flex-1 overflow-y-auto">
            <div className="px-6 py-6">
              {children}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
