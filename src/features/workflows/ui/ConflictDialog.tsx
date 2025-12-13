/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState } from 'react';
import { AlertTriangle, RefreshCw, X, Code } from 'lucide-react';

/**
 * Conflict Dialog Component
 *
 *
 * Displays when a resource has been modified by another user/tab
 * and provides options for resolving the conflict.
 */

interface ConflictDialogProps {
  open: boolean;
  resourceType: string;  // e.g., "Workflow", "Agent"
  resourceName: string;
  localData: any;
  remoteData: any;
  onResolve: (resolution: 'reload' | 'force' | 'cancel') => void;
  onClose: () => void;
}

export default function ConflictDialog({
  open,
  resourceType,
  resourceName,
  localData,
  remoteData,
  onResolve,
  onClose
}: ConflictDialogProps) {
  const [showDetails, setShowDetails] = useState(false);

  if (!open) return null;

  const handleReload = () => {
    onResolve('reload');
    onClose();
  };

  const handleForce = () => {
    if (confirm(
      `Are you sure you want to overwrite the current version?\n\n` +
      `This will discard changes made by another user or in another tab.`
    )) {
      onResolve('force');
      onClose();
    }
  };

  const handleCancel = () => {
    onResolve('cancel');
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full mx-4 max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 bg-amber-50">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-100 rounded-full">
              <AlertTriangle className="w-6 h-6 text-amber-600" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900">
                {resourceType} Modified
              </h2>
              <p className="text-sm text-gray-600">
                "{resourceName}" was changed by another user or tab
              </p>
            </div>
          </div>
          <button
            onClick={handleCancel}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-200px)]">
          <div className="mb-6">
            <p className="text-gray-700 mb-4">
              This {resourceType.toLowerCase()} was modified while you were editing it.
              You need to choose how to resolve this conflict:
            </p>

            <div className="grid gap-3">
              {/* Option 1: Reload */}
              <button
                onClick={handleReload}
                className="flex items-start gap-3 p-4 border-2 border-blue-200 rounded-lg hover:border-blue-400 hover:bg-blue-50 transition-all text-left"
              >
                <RefreshCw className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
                <div>
                  <div className="font-semibold text-gray-900 mb-1">
                    Reload and Discard My Changes (Recommended)
                  </div>
                  <div className="text-sm text-gray-600">
                    Reload the latest version from the server and discard your local changes.
                    This is the safest option to avoid overwriting someone else's work.
                  </div>
                </div>
              </button>

              {/* Option 2: Force Save */}
              <button
                onClick={handleForce}
                className="flex items-start gap-3 p-4 border-2 border-orange-200 rounded-lg hover:border-orange-400 hover:bg-orange-50 transition-all text-left"
              >
                <AlertTriangle className="w-5 h-5 text-orange-600 mt-0.5 flex-shrink-0" />
                <div>
                  <div className="font-semibold text-gray-900 mb-1">
                    Overwrite Current Version (Force Save)
                  </div>
                  <div className="text-sm text-gray-600">
                    Save your changes and overwrite the current version.
                    <span className="text-orange-700 font-medium"> This will discard the other user's changes.</span>
                  </div>
                </div>
              </button>

              {/* Option 3: Cancel */}
              <button
                onClick={handleCancel}
                className="flex items-start gap-3 p-4 border-2 border-gray-200 rounded-lg hover:border-gray-400 hover:bg-gray-50 transition-all text-left"
              >
                <X className="w-5 h-5 text-gray-600 mt-0.5 flex-shrink-0" />
                <div>
                  <div className="font-semibold text-gray-900 mb-1">
                    Cancel
                  </div>
                  <div className="text-sm text-gray-600">
                    Close this dialog and keep editing. Your changes remain unsaved.
                  </div>
                </div>
              </button>
            </div>
          </div>

          {/* Show Details Toggle */}
          <div className="border-t border-gray-200 pt-4">
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
            >
              <Code className="w-4 h-4" />
              {showDetails ? 'Hide' : 'Show'} Technical Details
            </button>

            {showDetails && (
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Your Changes */}
                <div>
                  <h3 className="font-semibold text-sm text-gray-900 mb-2">
                    Your Changes (Local)
                  </h3>
                  <pre className="bg-gray-100 p-3 rounded text-xs overflow-auto max-h-60">
                    {JSON.stringify(localData, null, 2)}
                  </pre>
                </div>

                {/* Current Version */}
                <div>
                  <h3 className="font-semibold text-sm text-gray-900 mb-2">
                    Current Version (Remote)
                  </h3>
                  <pre className="bg-blue-100 p-3 rounded text-xs overflow-auto max-h-60">
                    {JSON.stringify(remoteData, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </div>

          {/* Version Info */}
          <div className="mt-4 p-3 bg-gray-50 rounded text-xs text-gray-600">
            <div className="flex justify-between">
              <span>Your version: {localData.lock_version || 'unknown'}</span>
              <span>Current version: {remoteData.lock_version || 'unknown'}</span>
            </div>
            {remoteData.updated_at && (
              <div className="mt-1">
                Last modified: {new Date(remoteData.updated_at).toLocaleString()}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-4 border-t border-gray-200 bg-gray-50">
          <button
            onClick={handleCancel}
            className="px-4 py-2 text-gray-700 hover:bg-gray-200 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleReload}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Reload Latest
          </button>
        </div>
      </div>
    </div>
  );
}
