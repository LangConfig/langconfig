/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState } from 'react';
import {
  X,
  Download,
  Package,
  FileCode,
  Copy,
  Check,
  Loader,
  Globe,
  Container,
  TestTube,
  FileText
} from 'lucide-react';
import apiClient from '@/lib/api-client';
import { useTaskPolling } from '@/hooks/useTaskPolling';

interface ExportDialogProps {
  agentId: number;
  agentName: string;
  onClose: () => void;
}

export default function ExportDialog({
  agentId,
  agentName,
  onClose
}: ExportDialogProps) {
  const [exportType, setExportType] = useState<'standalone' | 'langconfig'>('standalone');
  const [options, setOptions] = useState({
    include_chat_ui: true,
    include_docker: false,
    include_tests: true,
    license: 'MIT'
  });
  const [isExporting, setIsExporting] = useState(false);
  const [exportComplete, setExportComplete] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copiedSnippet, setCopiedSnippet] = useState<string | null>(null);

  // Background task tracking
  const [taskId, setTaskId] = useState<number | null>(null);

  // Use task polling hook
  const { status, progress, error: taskError, result } = useTaskPolling({
    taskId: taskId || 0,
    enabled: taskId !== null,
    onComplete: (result: any) => {
      if (result?.download_url) {
        setDownloadUrl(result.download_url);
      }
      setExportComplete(true);
      setIsExporting(false);
    },
    onError: (error: any) => {
      console.error('[ExportDialog] Export failed:', error);
      setError(`Export failed: ${error}`);
      setIsExporting(false);
    }
  });

  const handleExport = async () => {
    setIsExporting(true);
    setError(null);
    setExportComplete(false);
    setTaskId(null);

    try {
      // Export now returns immediately with a task_id
      // Export now returns immediately with a task_id
      const response = await apiClient.exportDeepAgent(agentId, {
        export_type: exportType,
        include_chat_ui: options.include_chat_ui,
        include_docker: options.include_docker
      });

      // Axios throws on non-2xx status, so if we get here, it's successful
      const data = response.data;

      // Start polling for task completion
      if (data.task_id) {
        setTaskId(data.task_id);
      } else if (data.download_url) {
        // Fallback: If export completed immediately (shouldn't happen with background tasks)
        setDownloadUrl(data.download_url);
        setExportComplete(true);
        setIsExporting(false);
      }

    } catch (err) {
      setError('Failed to start export. Please try again.');
      console.error(err);
      setIsExporting(false);
    }
  };

  const handleDownload = () => {
    if (!downloadUrl) return;

    window.location.href = downloadUrl;
  };

  const copyToClipboard = (text: string, snippetId: string) => {
    navigator.clipboard.writeText(text);
    setCopiedSnippet(snippetId);
    setTimeout(() => setCopiedSnippet(null), 2000);
  };

  const codeSnippets = {
    setup: `# Extract and setup
unzip ${agentName.toLowerCase().replace(/\s+/g, '-')}.zip
cd ${agentName.toLowerCase().replace(/\s+/g, '-')}

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys`,

    cli: `# Run CLI chat interface
python main.py`,

    api: `# Run API server
python api_server.py

# Then access at http://localhost:8000`,

    python: `# Use in your Python code
from agent.agent import create_agent

agent = create_agent()
result = agent.invoke({
    "messages": [
        {"role": "user", "content": "Your message"}
    ]
})
print(result)`,

    docker: `# Build and run with Docker
docker-compose up --build

# Or with Docker directly
docker build -t ${agentName.toLowerCase().replace(/\s+/g, '-')} .
docker run -p 8000:8000 ${agentName.toLowerCase().replace(/\s+/g, '-')}`
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[#0a0a0a] border border-gray-800 rounded-xl w-full max-w-4xl max-h-[90vh] overflow-hidden shadow-2xl">

        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-800">
          <div>
            <h2 className="text-2xl font-semibold text-white">Export Agent</h2>
            <p className="text-sm text-gray-400 mt-1">
              Export {agentName} as standalone code or shareable format
            </p>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 overflow-y-auto max-h-[calc(90vh-180px)]">

          {/* Export Type Selection */}
          <div className="mb-6">
            <h3 className="text-lg font-semibold text-white mb-3">Export Format</h3>

            <div className="grid grid-cols-2 gap-4">
              <button
                onClick={() => setExportType('standalone')}
                className={`p-4 rounded-lg border-2 transition-all ${exportType === 'standalone'
                  ? 'border-blue-500 bg-blue-600/20'
                  : 'border-gray-700 hover:border-gray-600'
                  }`}
              >
                <Package className="w-8 h-8 mb-2 text-blue-400" />
                <div className="font-semibold text-white mb-1">Standalone Repository</div>
                <div className="text-sm text-gray-400">
                  Complete Python project with CLI, API, and UI
                </div>
              </button>

              <button
                onClick={() => setExportType('langconfig')}
                className={`p-4 rounded-lg border-2 transition-all ${exportType === 'langconfig'
                  ? 'border-purple-500 bg-purple-600/20'
                  : 'border-gray-700 hover:border-gray-600'
                  }`}
              >
                <FileCode className="w-8 h-8 mb-2 text-purple-400" />
                <div className="font-semibold text-white mb-1">LangConfig Format</div>
                <div className="text-sm text-gray-400">
                  JSON format for import/export between instances
                </div>
              </button>
            </div>
          </div>

          {/* Standalone Options */}
          {exportType === 'standalone' && (
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-white mb-3">Include Options</h3>

              <div className="space-y-3">
                <label className="flex items-center gap-3 p-3 bg-gray-900/50 rounded-lg cursor-pointer hover:bg-gray-900 transition-colors">
                  <input
                    type="checkbox"
                    checked={options.include_chat_ui}
                    onChange={(e) => setOptions(prev => ({ ...prev, include_chat_ui: e.target.checked }))}
                    className="w-4 h-4"
                  />
                  <Globe className="w-5 h-5 text-blue-400" />
                  <div className="flex-1">
                    <div className="font-medium text-white">Web Chat Interface</div>
                    <div className="text-sm text-gray-400">Include HTML/JS chat UI</div>
                  </div>
                </label>

                <label className="flex items-center gap-3 p-3 bg-gray-900/50 rounded-lg cursor-pointer hover:bg-gray-900 transition-colors">
                  <input
                    type="checkbox"
                    checked={options.include_docker}
                    onChange={(e) => setOptions(prev => ({ ...prev, include_docker: e.target.checked }))}
                    className="w-4 h-4"
                  />
                  <Container className="w-5 h-5 text-cyan-400" />
                  <div className="flex-1">
                    <div className="font-medium text-white">Docker Support</div>
                    <div className="text-sm text-gray-400">Dockerfile and docker-compose.yml</div>
                  </div>
                </label>

                <label className="flex items-center gap-3 p-3 bg-gray-900/50 rounded-lg cursor-pointer hover:bg-gray-900 transition-colors">
                  <input
                    type="checkbox"
                    checked={options.include_tests}
                    onChange={(e) => setOptions(prev => ({ ...prev, include_tests: e.target.checked }))}
                    className="w-4 h-4"
                  />
                  <TestTube className="w-5 h-5 text-green-400" />
                  <div className="flex-1">
                    <div className="font-medium text-white">Test Files</div>
                    <div className="text-sm text-gray-400">Basic test suite with pytest</div>
                  </div>
                </label>
              </div>
            </div>
          )}


          {isExporting && taskId && (
            <div className="mb-6 p-4 bg-blue-600/10 border border-blue-600/50 rounded-lg">
              <div className="flex items-center gap-3 mb-3">
                <Loader className="w-5 h-5 text-blue-400 animate-spin" />
                <div>
                  <div className="font-semibold text-blue-400">Exporting Agent...</div>
                  <div className="text-sm text-gray-400">Status: {status}</div>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-gray-800 rounded-full h-2.5 overflow-hidden">
                <div
                  className="bg-blue-600 h-2.5 transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="text-xs text-gray-500 mt-2 text-right">{progress}%</div>
            </div>
          )}

          {/* Export Result */}
          {exportComplete && (
            <div className="mb-6 p-4 bg-green-600/10 border border-green-600/50 rounded-lg">
              <div className="flex items-center gap-3 mb-3">
                <Check className="w-5 h-5 text-green-400" />
                <div>
                  <div className="font-semibold text-green-400">Export Complete!</div>
                  <div className="text-sm text-gray-400">Your agent has been exported successfully</div>
                </div>
              </div>

              <button
                onClick={handleDownload}
                className="w-full py-2 px-4 bg-green-600 hover:bg-green-700 rounded-lg transition-colors flex items-center justify-center gap-2 text-white font-medium"
              >
                <Download className="w-5 h-5" />
                Download {exportType === 'standalone' ? 'ZIP File' : 'JSON File'}
              </button>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mb-6 p-4 bg-red-600/10 border border-red-600/50 rounded-lg text-red-400">
              {error}
            </div>
          )}

          {/* Integration Examples (only for standalone) */}
          {exportType === 'standalone' && !exportComplete && (
            <div>
              <h3 className="text-lg font-semibold text-white mb-3">Usage Examples</h3>

              <div className="space-y-4">
                <CodeSnippet
                  title="Setup & Installation"
                  icon={<FileText className="w-4 h-4" />}
                  code={codeSnippets.setup}
                  snippetId="setup"
                  copied={copiedSnippet === 'setup'}
                  onCopy={() => copyToClipboard(codeSnippets.setup, 'setup')}
                />

                <CodeSnippet
                  title="CLI Chat"
                  icon={<FileCode className="w-4 h-4" />}
                  code={codeSnippets.cli}
                  snippetId="cli"
                  copied={copiedSnippet === 'cli'}
                  onCopy={() => copyToClipboard(codeSnippets.cli, 'cli')}
                />

                <CodeSnippet
                  title="API Server"
                  icon={<Globe className="w-4 h-4" />}
                  code={codeSnippets.api}
                  snippetId="api"
                  copied={copiedSnippet === 'api'}
                  onCopy={() => copyToClipboard(codeSnippets.api, 'api')}
                />

                <CodeSnippet
                  title="Python Integration"
                  icon={<FileCode className="w-4 h-4" />}
                  code={codeSnippets.python}
                  snippetId="python"
                  copied={copiedSnippet === 'python'}
                  onCopy={() => copyToClipboard(codeSnippets.python, 'python')}
                />

                {options.include_docker && (
                  <CodeSnippet
                    title="Docker Deployment"
                    icon={<Container className="w-4 h-4" />}
                    code={codeSnippets.docker}
                    snippetId="docker"
                    copied={copiedSnippet === 'docker'}
                    onCopy={() => copyToClipboard(codeSnippets.docker, 'docker')}
                  />
                )}
              </div>
            </div>
          )}

          {/* LangConfig Info */}
          {exportType === 'langconfig' && !exportComplete && (
            <div className="p-4 bg-purple-600/10 border border-purple-600/30 rounded-lg">
              <h4 className="font-semibold text-purple-400 mb-2">About LangConfig Format</h4>
              <div className="text-sm text-gray-300 space-y-2">
                <p>
                  The .langconfig format is a JSON interchange format that allows you to:
                </p>
                <ul className="list-disc list-inside space-y-1 text-gray-400">
                  <li>Share agent configurations between LangConfig instances</li>
                  <li>Version control your agent configurations</li>
                  <li>Build a library of reusable agents</li>
                  <li>Import community-created agents</li>
                </ul>
                <p className="text-xs text-gray-500 mt-3">
                  Use the import feature to load .langconfig files into another LangConfig instance.
                </p>
              </div>
            </div>
          )}

        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-800">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-400 hover:text-white transition-colors"
          >
            Cancel
          </button>

          {!exportComplete && (
            <button
              onClick={handleExport}
              disabled={isExporting}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-lg transition-colors flex items-center gap-2 text-white font-medium"
            >
              {isExporting ? (
                <>
                  <Loader className="w-5 h-5 animate-spin" />
                  Exporting...
                </>
              ) : (
                <>
                  <Download className="w-5 h-5" />
                  Export Agent
                </>
              )}
            </button>
          )}
        </div>

      </div>
    </div>
  );
}

function CodeSnippet({
  title,
  icon,
  code,
  snippetId,
  copied,
  onCopy
}: {
  title: string;
  icon: React.ReactNode;
  code: string;
  snippetId: string;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <div className="border border-gray-800 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between p-3 bg-gray-900/50 border-b border-gray-800">
        <div className="flex items-center gap-2 text-gray-300">
          {icon}
          <span className="text-sm font-medium">{title}</span>
        </div>

        <button
          onClick={onCopy}
          className="flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-white transition-colors"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3" />
              Copied!
            </>
          ) : (
            <>
              <Copy className="w-3 h-3" />
              Copy
            </>
          )}
        </button>
      </div>

      <pre className="p-4 bg-gray-950 overflow-x-auto">
        <code className="text-sm text-gray-300 font-mono">{code}</code>
      </pre>
    </div>
  );
}
