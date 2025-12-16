/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { memo, useState } from 'react';
import { X, Play, Image, FileText, Clock, Database, ChevronDown, Upload, Plus, Trash2, Settings } from 'lucide-react';
import { Attachment } from '@/components/common/AttachmentUploader';

interface WorkflowExecutionContext {
  directive: string;
  query: string;
  task: string;
  classification: 'GENERAL' | 'BACKEND' | 'FRONTEND' | 'DEVOPS_IAC' | 'DATABASE' | 'API' | 'TESTING' | 'DOCUMENTATION' | 'CONFIGURATION';
  executor_type: 'default' | 'devops' | 'frontend' | 'database' | 'testing';
  max_retries: number;
  max_events?: number;
  timeout_seconds?: number;
}

interface Document {
  id: number;
  name: string;
  document_type: string;
}

interface ExecutionConfigDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onExecute: () => void;
  executionConfig: WorkflowExecutionContext;
  setExecutionConfig: React.Dispatch<React.SetStateAction<WorkflowExecutionContext>>;
  showAdvancedOptions: boolean;
  setShowAdvancedOptions: React.Dispatch<React.SetStateAction<boolean>>;
  additionalContext: string;
  setAdditionalContext: React.Dispatch<React.SetStateAction<string>>;
  contextDocuments: number[];
  setContextDocuments: React.Dispatch<React.SetStateAction<number[]>>;
  availableDocuments: Document[];
  attachments?: Attachment[];
  onAttachmentsChange?: (attachments: Attachment[]) => void;
}

/**
 * Run Workflow Dialog - Studio Style
 *
 * Clean white background with primary color header
 */
const ExecutionConfigDialog = memo(function ExecutionConfigDialog({
  isOpen,
  onClose,
  onExecute,
  executionConfig,
  setExecutionConfig,
  additionalContext,
  setAdditionalContext,
  contextDocuments,
  setContextDocuments,
  availableDocuments,
  attachments = [],
  onAttachmentsChange,
}: ExecutionConfigDialogProps) {
  const [localAttachments, setLocalAttachments] = useState<Attachment[]>([]);
  const currentAttachments = onAttachmentsChange ? attachments : localAttachments;
  const setAttachments = onAttachmentsChange || setLocalAttachments;
  const [showSettings, setShowSettings] = useState(false);

  if (!isOpen) return null;

  const hasAttachments = currentAttachments.length > 0;
  const hasDocuments = contextDocuments.length > 0;

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
      onClick={onClose}
    >
      <div
        className="rounded-xl shadow-2xl w-full max-w-xl mx-4 overflow-hidden bg-white"
        style={{ maxHeight: '90vh' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Primary Color Header */}
        <div className="px-6 py-4 flex items-center justify-between" style={{ backgroundColor: 'var(--color-primary)' }}>
          <div className="flex items-center gap-3">
            <Play size={22} className="text-white" />
            <h2 className="text-lg font-semibold text-white">
              Run Workflow
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-white/20 transition-colors text-white"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content - White Background */}
        <div className="p-6 overflow-y-auto bg-white" style={{ maxHeight: 'calc(90vh - 130px)' }}>
          {/* Prompt Input */}
          <div className="mb-5">
            <label className="block text-sm font-medium mb-2 text-gray-700">
              What should this workflow do?
            </label>
            <textarea
              className="w-full px-4 py-3 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all text-gray-800"
              style={{ borderColor: '#e5e7eb' }}
              rows={4}
              placeholder="Describe your task in detail..."
              value={executionConfig.directive}
              onChange={(e) => setExecutionConfig({
                ...executionConfig,
                directive: e.target.value,
                query: e.target.value,
                task: e.target.value,
              })}
              autoFocus
            />
          </div>

          {/* Attachments Section */}
          <div className="mb-5">
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-700 flex items-center gap-2">
                <Image size={16} className="text-gray-500" />
                Attachments
                {hasAttachments && (
                  <span className="px-2 py-0.5 text-xs rounded-full bg-primary text-white">
                    {currentAttachments.length}
                  </span>
                )}
              </label>
              <span className="text-xs text-gray-400">Images, documents, videos</span>
            </div>

            <div className="border rounded-lg p-3" style={{ borderColor: '#e5e7eb' }}>
              {hasAttachments ? (
                <div className="flex flex-wrap gap-2 mb-2">
                  {currentAttachments.map((att) => (
                    <div
                      key={att.id}
                      className="relative group w-16 h-16 rounded-lg overflow-hidden border bg-gray-50"
                      style={{ borderColor: '#e5e7eb' }}
                    >
                      {att.thumbnail ? (
                        <img src={att.thumbnail} alt={att.name} className="w-full h-full object-cover" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <FileText size={20} className="text-gray-400" />
                        </div>
                      )}
                      <button
                        onClick={() => setAttachments(currentAttachments.filter(a => a.id !== att.id))}
                        className="absolute top-0.5 right-0.5 p-0.5 rounded bg-red-500 text-white opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <Trash2 size={10} />
                      </button>
                    </div>
                  ))}
                  {currentAttachments.length < 5 && (
                    <label className="w-16 h-16 rounded-lg border-2 border-dashed flex items-center justify-center cursor-pointer hover:border-primary hover:bg-gray-50 transition-colors"
                      style={{ borderColor: '#d1d5db' }}
                    >
                      <Plus size={18} className="text-gray-400" />
                      <input type="file" accept="image/*,.pdf,.doc,.docx,.txt,.md,video/*" multiple className="hidden"
                        onChange={async (e) => {
                          if (!e.target.files) return;
                          const files = Array.from(e.target.files);
                          const newAttachments: Attachment[] = [];
                          for (const file of files) {
                            const reader = new FileReader();
                            const base64 = await new Promise<string>((resolve) => {
                              reader.onload = () => resolve((reader.result as string).split(',')[1]);
                              reader.readAsDataURL(file);
                            });
                            let thumbnail: string | undefined;
                            if (file.type.startsWith('image/')) {
                              const img = document.createElement('img');
                              const canvas = document.createElement('canvas');
                              thumbnail = await new Promise<string>((resolve) => {
                                img.onload = () => {
                                  const scale = Math.min(80 / img.width, 80 / img.height);
                                  canvas.width = img.width * scale;
                                  canvas.height = img.height * scale;
                                  canvas.getContext('2d')?.drawImage(img, 0, 0, canvas.width, canvas.height);
                                  resolve(canvas.toDataURL('image/jpeg', 0.7));
                                };
                                img.src = URL.createObjectURL(file);
                              });
                            }
                            newAttachments.push({
                              id: `att_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
                              type: file.type.startsWith('image/') ? 'image' : file.type.startsWith('video/') ? 'video' : 'document',
                              name: file.name, data: base64, mimeType: file.type, size: file.size, thumbnail,
                            });
                          }
                          setAttachments([...currentAttachments, ...newAttachments].slice(0, 5));
                          e.target.value = '';
                        }}
                      />
                    </label>
                  )}
                </div>
              ) : (
                <label className="flex items-center justify-center gap-2 py-6 cursor-pointer hover:bg-gray-50 rounded-lg transition-colors">
                  <Upload size={18} className="text-gray-400" />
                  <span className="text-sm text-gray-500">Drop files or click to upload</span>
                  <input type="file" accept="image/*,.pdf,.doc,.docx,.txt,.md,video/*" multiple className="hidden"
                    onChange={async (e) => {
                      if (!e.target.files) return;
                      const files = Array.from(e.target.files);
                      const newAttachments: Attachment[] = [];
                      for (const file of files) {
                        const reader = new FileReader();
                        const base64 = await new Promise<string>((resolve) => {
                          reader.onload = () => resolve((reader.result as string).split(',')[1]);
                          reader.readAsDataURL(file);
                        });
                        let thumbnail: string | undefined;
                        if (file.type.startsWith('image/')) {
                          const img = document.createElement('img');
                          const canvas = document.createElement('canvas');
                          thumbnail = await new Promise<string>((resolve) => {
                            img.onload = () => {
                              const scale = Math.min(80 / img.width, 80 / img.height);
                              canvas.width = img.width * scale;
                              canvas.height = img.height * scale;
                              canvas.getContext('2d')?.drawImage(img, 0, 0, canvas.width, canvas.height);
                              resolve(canvas.toDataURL('image/jpeg', 0.7));
                            };
                            img.src = URL.createObjectURL(file);
                          });
                        }
                        newAttachments.push({
                          id: `att_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
                          type: file.type.startsWith('image/') ? 'image' : file.type.startsWith('video/') ? 'video' : 'document',
                          name: file.name, data: base64, mimeType: file.type, size: file.size, thumbnail,
                        });
                      }
                      setAttachments(newAttachments.slice(0, 5));
                      e.target.value = '';
                    }}
                  />
                </label>
              )}
            </div>
          </div>

          {/* Additional Context */}
          <div className="mb-5">
            <label className="block text-sm font-medium mb-2 text-gray-700 flex items-center gap-2">
              <FileText size={16} className="text-gray-500" />
              Additional Context
              <span className="text-xs text-gray-400 font-normal">(Optional)</span>
            </label>
            <textarea
              className="w-full px-3 py-2 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all text-sm text-gray-800"
              style={{ borderColor: '#e5e7eb' }}
              rows={2}
              placeholder="Add background information or constraints..."
              value={additionalContext}
              onChange={(e) => setAdditionalContext(e.target.value)}
            />
          </div>

          {/* Knowledge Base */}
          {availableDocuments.length > 0 && (
            <div className="mb-5">
              <label className="block text-sm font-medium mb-2 text-gray-700 flex items-center gap-2">
                <Database size={16} className="text-gray-500" />
                Knowledge Base (RAG)
                {hasDocuments && (
                  <span className="px-2 py-0.5 text-xs rounded-full bg-primary text-white">
                    {contextDocuments.length}
                  </span>
                )}
              </label>
              <div className="border rounded-lg p-2 max-h-32 overflow-y-auto" style={{ borderColor: '#e5e7eb' }}>
                {availableDocuments.map((doc) => (
                  <label key={doc.id} className="flex items-center gap-2 py-1.5 px-2 rounded cursor-pointer hover:bg-gray-50">
                    <input
                      type="checkbox"
                      checked={contextDocuments.includes(doc.id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setContextDocuments([...contextDocuments, doc.id]);
                        } else {
                          setContextDocuments(contextDocuments.filter(id => id !== doc.id));
                        }
                      }}
                      className="rounded text-primary"
                    />
                    <span className="text-sm text-gray-700 flex-1 truncate">{doc.name}</span>
                    <span className="text-xs text-gray-400">{doc.document_type}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Execution Settings - Collapsible */}
          <div className="border rounded-lg" style={{ borderColor: '#e5e7eb' }}>
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors rounded-lg"
            >
              <div className="flex items-center gap-2">
                <Settings size={16} className="text-gray-500" />
                <span className="text-sm font-medium text-gray-700">Execution Settings</span>
              </div>
              <ChevronDown size={16} className={`text-gray-400 transition-transform ${showSettings ? 'rotate-180' : ''}`} />
            </button>
            {showSettings && (
              <div className="px-4 pb-4 border-t" style={{ borderColor: '#e5e7eb' }}>
                <div className="grid grid-cols-3 gap-4 pt-3">
                  <div>
                    <label className="text-xs font-medium text-gray-500 mb-1 block">Retries</label>
                    <input
                      type="number" min="0" max="10"
                      className="w-full px-2 py-1.5 border rounded text-sm text-gray-800 focus:outline-none focus:border-primary"
                      style={{ borderColor: '#e5e7eb' }}
                      value={executionConfig.max_retries}
                      onChange={(e) => setExecutionConfig({ ...executionConfig, max_retries: parseInt(e.target.value) || 0 })}
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-500 mb-1 block">Max Events</label>
                    <input
                      type="number" min="1000" max="100000" step="1000"
                      className="w-full px-2 py-1.5 border rounded text-sm text-gray-800 focus:outline-none focus:border-primary"
                      style={{ borderColor: '#e5e7eb' }}
                      value={executionConfig.max_events || 10000}
                      onChange={(e) => setExecutionConfig({ ...executionConfig, max_events: parseInt(e.target.value) || 10000 })}
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-500 mb-1 block">Timeout (min)</label>
                    <input
                      type="number" min="1" max="60"
                      className="w-full px-2 py-1.5 border rounded text-sm text-gray-800 focus:outline-none focus:border-primary"
                      style={{ borderColor: '#e5e7eb' }}
                      value={Math.round((executionConfig.timeout_seconds || 600) / 60)}
                      onChange={(e) => setExecutionConfig({ ...executionConfig, timeout_seconds: (parseInt(e.target.value) || 10) * 60 })}
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t bg-gray-50 flex items-center justify-end gap-3" style={{ borderColor: '#e5e7eb' }}>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-100 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onExecute}
            disabled={!executionConfig.directive.trim()}
            className="px-6 py-2 rounded-lg text-sm font-medium text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            style={{ backgroundColor: 'var(--color-primary)' }}
          >
            <Play size={16} />
            Run Workflow
          </button>
        </div>
      </div>
    </div>
  );
});

export default ExecutionConfigDialog;
