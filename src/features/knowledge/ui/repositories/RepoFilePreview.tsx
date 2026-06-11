/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useEffect, useState } from 'react';
import { BookOpen, Check, FileText, Loader2 } from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import apiClient from '@/lib/api-client';

interface RepoFilePreviewProps {
  repoId: number | null;
  path: string | null;
}

type PreviewState =
  | { kind: 'empty' }
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'binary'; path: string; size: number }
  | { kind: 'too_large'; path: string; size: number }
  | { kind: 'text'; path: string; size: number; content: string };

const EXT_TO_LANG: Record<string, string> = {
  ts: 'typescript', tsx: 'tsx', js: 'javascript', jsx: 'jsx',
  py: 'python', rb: 'ruby', go: 'go', rs: 'rust', java: 'java',
  kt: 'kotlin', swift: 'swift', sh: 'bash', yml: 'yaml', yaml: 'yaml',
  json: 'json', toml: 'toml', html: 'html', css: 'css', sql: 'sql',
  md: 'markdown', xml: 'xml', r: 'r', ini: 'ini', conf: 'ini',
};

function languageFor(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase() ?? '';
  return EXT_TO_LANG[ext] ?? 'text';
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function RepoFilePreview({ repoId, path }: RepoFilePreviewProps) {
  const [state, setState] = useState<PreviewState>({ kind: 'empty' });

  useEffect(() => {
    if (!repoId || !path) {
      setState({ kind: 'empty' });
      return;
    }
    const ac = new AbortController();
    setState({ kind: 'loading' });
    apiClient
      .getRepositoryFile(repoId, path, { signal: ac.signal })
      .then((res) => {
        const data = res.data;
        if (data.binary) setState({ kind: 'binary', path: data.path, size: data.size });
        else if (data.too_large) setState({ kind: 'too_large', path: data.path, size: data.size });
        else setState({ kind: 'text', path: data.path, size: data.size, content: data.content });
      })
      .catch((err: any) => {
        if (err?.name === 'AbortError' || err?.name === 'CanceledError') return;
        const detail = err?.response?.data?.detail;
        setState({ kind: 'error', message: typeof detail === 'string' ? detail : 'Failed to load file' });
      });
    return () => ac.abort();
  }, [repoId, path]);

  if (state.kind === 'empty') {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-2 px-6 text-center">
        <FileText size={36} className="text-text-muted opacity-40" />
        <p className="text-sm font-semibold uppercase tracking-wide text-text-primary">
          Select a file to preview
        </p>
        <p className="text-xs text-text-muted">
          Choose any file from the tree on the left.
        </p>
      </div>
    );
  }

  if (state.kind === 'loading') {
    return (
      <div className="h-full flex items-center justify-center gap-2 text-sm text-text-muted">
        <Loader2 size={16} className="animate-spin" />
        Loading file...
      </div>
    );
  }

  if (state.kind === 'error') {
    return (
      <div className="h-full flex items-center justify-center text-sm" style={{ color: '#B3402F' }}>
        {state.message}
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 px-4 py-2 border-b-2 border-border-dark bg-panel-dark shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <FileText size={14} className="text-text-muted shrink-0" />
          <span className="text-xs font-mono truncate text-text-primary">
            {state.path}
          </span>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span className="text-xs font-mono text-text-muted">
            {formatBytes(state.size)}
          </span>
          {repoId !== null && state.kind === 'text' && (
            <AddToKnowledgeButton repoId={repoId} path={state.path} kind="file" />
          )}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto bg-background-light">
        {state.kind === 'binary' && (
          <PlaceholderMessage
            title="Binary file"
            body="This file isn't previewable as text."
          />
        )}
        {state.kind === 'too_large' && (
          <PlaceholderMessage
            title="File too large"
            body={`Preview is capped at 2 MB. This file is ${formatBytes(state.size)}.`}
          />
        )}
        {state.kind === 'text' && (
          <SyntaxHighlighter
            language={languageFor(state.path)}
            style={oneLight}
            showLineNumbers
            customStyle={{ margin: 0, fontSize: '0.8em', background: 'transparent' }}
          >
            {state.content}
          </SyntaxHighlighter>
        )}
      </div>
    </div>
  );
}

function PlaceholderMessage({ title, body }: { title: string; body: string }) {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-1 px-6 text-center">
      <p className="text-sm font-semibold uppercase tracking-wide text-text-primary">
        {title}
      </p>
      <p className="text-xs text-text-muted">
        {body}
      </p>
    </div>
  );
}

// =============================================================================
// AddToKnowledgeButton — shared between RepoFilePreview (file) and RepoFileTree (folder)
// =============================================================================

type SendStatus = 'idle' | 'sending' | 'sent' | 'error';

const SUCCESS_FG = '#2F7D52';
const SUCCESS_BG = '#DFF2E4';
const ERROR_FG = '#B3402F';
const ERROR_BG = '#FAE3DC';

export function AddToKnowledgeButton({
  repoId,
  path,
  kind,
  compact = false,
}: {
  repoId: number;
  path: string;
  kind: 'file' | 'folder';
  compact?: boolean;
}) {
  const [status, setStatus] = useState<SendStatus>('idle');
  const [message, setMessage] = useState<string | null>(null);

  const handleClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (status === 'sending') return;
    setStatus('sending');
    setMessage(null);
    try {
      const res = await apiClient.ingestRepositoryPath(repoId, path);
      const ingested = res.data?.ingested ?? 0;
      const skipped = res.data?.skipped ?? 0;
      setStatus('sent');
      setMessage(
        kind === 'folder'
          ? `Ingested ${ingested} file${ingested === 1 ? '' : 's'}${skipped ? ` (${skipped} skipped)` : ''}`
          : 'Added to Knowledge Base',
      );
      setTimeout(() => setStatus('idle'), 2500);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setStatus('error');
      setMessage(typeof detail === 'string' ? detail : 'Failed to ingest');
      setTimeout(() => setStatus('idle'), 3000);
    }
  };

  const label =
    status === 'sending' ? 'Adding to Knowledge Base...' :
    status === 'sent' ? (message || 'Added to Knowledge Base') :
    status === 'error' ? (message || 'Error') :
    kind === 'folder' ? 'Add folder to Knowledge Base' : 'Add to Knowledge Base';

  const Icon =
    status === 'sending' ? Loader2 :
    status === 'sent' ? Check :
    BookOpen;

  const iconClass = status === 'sending' ? 'animate-spin' : '';

  const fg = status === 'error' ? ERROR_FG : status === 'sent' ? SUCCESS_FG : 'var(--color-text-primary)';
  const bg = status === 'error' ? ERROR_BG : status === 'sent' ? SUCCESS_BG : 'var(--color-background-light)';

  if (compact) {
    return (
      <button
        onClick={handleClick}
        disabled={status === 'sending'}
        className="flex items-center gap-1 px-1.5 py-0.5 rounded-[3px] border-2 border-border-dark text-[9px] font-mono font-bold uppercase tracking-wide transition-all disabled:opacity-50 whitespace-nowrap shadow-[2px_2px_0_var(--color-border-dark)] hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-[1px_1px_0_var(--color-border-dark)]"
        style={{ backgroundColor: bg, color: fg }}
        title={label}
      >
        <Icon size={10} className={iconClass} />
        {status === 'sending' ? 'Adding' : status === 'sent' ? 'Added' : status === 'error' ? 'Error' : 'Ingest'}
      </button>
    );
  }

  return (
    <button
      onClick={handleClick}
      disabled={status === 'sending'}
      className="flex items-center gap-1.5 px-2.5 py-1 rounded-[3px] border-2 border-border-dark text-[10px] font-mono font-bold uppercase tracking-wide transition-all disabled:opacity-50 shadow-[2px_2px_0_var(--color-border-dark)] hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-[1px_1px_0_var(--color-border-dark)]"
      style={{ backgroundColor: bg, color: fg }}
      title={label}
    >
      <Icon size={12} className={iconClass} />
      {label}
    </button>
  );
}
