/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Brain,
  CheckCircle2,
  CircleStop,
  FileCode2,
  Play,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  Terminal,
  XCircle,
} from 'lucide-react';
import apiClient from '@/lib/api-client';
import { useProject } from '@/contexts/ProjectContext';

type HermesDraft = {
  id: number;
  project_id?: number | null;
  artifact_type: string;
  title: string;
  payload_json: Record<string, unknown>;
  status: string;
  validation_result?: any;
  source_session_id?: string | null;
  codex_run_id?: string | null;
  apply_result?: any;
  rejection_reason?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

type CodexRun = {
  id: string;
  mode: string;
  status: string;
  sandbox_dir?: string;
  last_message?: string | null;
  command_preview?: string[];
};

const defaultWorkflowPayload = {
  name: 'Hermes Draft Workflow',
  description: 'Drafted from Hermes workspace',
  configuration: {
    nodes: [
      {
        id: 'start',
        type: 'START',
        data: { label: 'Start', agentType: 'START', config: {} },
        config: {},
      },
      {
        id: 'end',
        type: 'END',
        data: { label: 'End', agentType: 'END', config: {} },
        config: {},
      },
    ],
    edges: [{ id: 'start-end', source: 'start', target: 'end' }],
  },
  blueprint: {
    nodes: [
      {
        id: 'start',
        type: 'custom',
        data: { label: 'Start', agentType: 'START', config: {} },
        config: {},
      },
      {
        id: 'end',
        type: 'custom',
        data: { label: 'End', agentType: 'END', config: {} },
        config: {},
      },
    ],
    edges: [{ id: 'start-end', source: 'start', target: 'end' }],
  },
};

function parsePayload(text: string) {
  const parsed = JSON.parse(text);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('Payload must be a JSON object');
  }
  return parsed as Record<string, unknown>;
}

function formatJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

function StatusMark({ status }: { status?: string }) {
  const normalized = (status || '').toLowerCase();
  if (normalized === 'validated' || normalized === 'completed' || normalized === 'applied') {
    return <CheckCircle2 className="h-4 w-4 text-green-700 dark:text-green-400" />;
  }
  if (normalized === 'validation_failed' || normalized === 'failed' || normalized === 'rejected') {
    return <XCircle className="h-4 w-4 text-red-700 dark:text-red-400" />;
  }
  return <ShieldCheck className="h-4 w-4 text-primary" />;
}

export default function HermesWorkspace() {
  const { activeProject } = useProject();
  const [intent, setIntent] = useState('Draft a LangConfig workflow automation');
  const [artifactType, setArtifactType] = useState('workflow');
  const [draftTitle, setDraftTitle] = useState('Hermes Draft Workflow');
  const [payloadText, setPayloadText] = useState(formatJson(defaultWorkflowPayload));
  const [drafts, setDrafts] = useState<HermesDraft[]>([]);
  const [selectedDraft, setSelectedDraft] = useState<HermesDraft | null>(null);
  const [brainStatus, setBrainStatus] = useState<any>(null);
  const [codexStatus, setCodexStatus] = useState<any>(null);
  const [brainResults, setBrainResults] = useState<any[]>([]);
  const [validationResult, setValidationResult] = useState<any>(null);
  const [targetId, setTargetId] = useState('');
  const [lockVersion, setLockVersion] = useState('');
  const [codexPrompt, setCodexPrompt] = useState('Inspect this LangConfig automation task and draft implementation notes.');
  const [codexRun, setCodexRun] = useState<CodexRun | null>(null);
  const [codexEvents, setCodexEvents] = useState<any[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [experimentalDisabled, setExperimentalDisabled] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  const selectedResult = selectedDraft?.status === 'applied'
    ? selectedDraft.apply_result
    : selectedDraft?.validation_result || validationResult;
  const codexReady = Boolean(codexStatus?.installed && codexStatus?.logged_in);

  const invalidateDraftSelection = () => {
    setSelectedDraft(null);
    setValidationResult(null);
  };

  const refresh = useCallback(async () => {
    setBusy('refresh');
    setError(null);
    try {
      // Probe one guarded endpoint first so a default-disabled clone renders a
      // single intentional opt-in state instead of firing three rejected calls.
      const brain = await apiClient.getPlatformBrainStatus();
      const [codex, draftList] = await Promise.all([
        apiClient.getCodexStatus(),
        apiClient.listHermesDrafts({ project_id: activeProject?.id, limit: 25 }),
      ]);
      setCodexStatus(codex.data);
      setBrainStatus(brain.data);
      setDrafts(draftList.data);
      setExperimentalDisabled(false);
      // Reconcile the current selection so a completed create or editor change
      // cannot be overwritten by the selection captured before the request.
      setSelectedDraft((current) => current
        ? draftList.data.find((draft: HermesDraft) => draft.id === current.id) || null
        : null);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const isDisabled = err?.response?.status === 403 && detail === 'Experimental local APIs are disabled';
      setExperimentalDisabled(isDisabled);
      setError(isDisabled ? null : detail || err.message || 'Refresh failed');
    } finally {
      setBusy(null);
    }
  }, [activeProject?.id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => () => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
  }, []);

  const searchBrain = async () => {
    setBusy('search');
    setError(null);
    try {
      const response = await apiClient.queryPlatformBrain({
        query: intent,
        top_k: 8,
        project_id: activeProject?.id,
      });
      setBrainResults(response.data.results || []);
      setBrainStatus(response.data.status || brainStatus);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Search failed');
    } finally {
      setBusy(null);
    }
  };

  const reindexBrain = async () => {
    setBusy('reindex');
    setError(null);
    try {
      const response = await apiClient.reindexPlatformBrain();
      setBrainStatus(response.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Reindex failed');
    } finally {
      setBusy(null);
    }
  };

  const createDraft = async () => {
    setBusy('create-draft');
    setError(null);
    try {
      const payload = parsePayload(payloadText);
      const response = await apiClient.createHermesDraft({
        artifact_type: artifactType,
        title: draftTitle,
        payload_json: payload,
        project_id: activeProject?.id || null,
        codex_run_id: codexRun?.id || null,
        validate_on_create: true,
      });
      setSelectedDraft(response.data);
      setValidationResult(response.data.validation_result);
      await refresh();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Draft create failed');
    } finally {
      setBusy(null);
    }
  };

  const validateSelectedDraft = async () => {
    if (!selectedDraft) return;
    setBusy('validate');
    setError(null);
    try {
      const response = await apiClient.validateHermesDraft(selectedDraft.id);
      setSelectedDraft(response.data.draft);
      setValidationResult(response.data.validation_result);
      await refresh();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Validation failed');
    } finally {
      setBusy(null);
    }
  };

  const applySelectedDraft = async () => {
    if (!selectedDraft) return;
    setBusy('apply');
    setError(null);
    try {
      const response = await apiClient.applyHermesDraft(selectedDraft.id, {
        target_id: targetId ? Number(targetId) : null,
        lock_version: lockVersion ? Number(lockVersion) : null,
        approval_note: 'Approved in Hermes workspace',
      });
      setSelectedDraft(response.data.draft);
      await refresh();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Apply failed');
    } finally {
      setBusy(null);
    }
  };

  const rejectSelectedDraft = async () => {
    if (!selectedDraft) return;
    setBusy('reject');
    setError(null);
    try {
      const response = await apiClient.rejectHermesDraft(selectedDraft.id, 'Rejected in Hermes workspace');
      setSelectedDraft(response.data);
      await refresh();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Reject failed');
    } finally {
      setBusy(null);
    }
  };

  const startCodexRun = async () => {
    setBusy('codex');
    setError(null);
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    try {
      const response = await apiClient.startCodexRun({
        prompt: codexPrompt,
        mode: 'exec',
        metadata: { source: 'hermes_workspace', project_id: activeProject?.id },
      });
      setCodexRun(response.data);
      setCodexEvents([]);
      const source = new EventSource(apiClient.getCodexRunEventsUrl(response.data.id));
      eventSourceRef.current = source;
      source.onmessage = (event) => {
        if (eventSourceRef.current !== source) return;
        try {
          const parsed = JSON.parse(event.data);
          setCodexEvents((events) => [...events, parsed].slice(-80));
          const terminalType = String(parsed.type || '');
          if (terminalType === 'run.completed' || terminalType === 'run.failed' || terminalType === 'run.cancelled') {
            source.close();
            apiClient.getCodexRunEvents(response.data.id).then((eventsResponse) => {
              if (eventSourceRef.current !== source) return;
              const events = eventsResponse.data.events || [];
              setCodexEvents(events);
              const last = events[events.length - 1];
              if (last) {
                setCodexRun((run) => run ? { ...run, status: String(last.type || '').replace('run.', '') } : run);
              }
            });
          }
        } catch {
          setCodexEvents((events) => [...events, { message: event.data }].slice(-80));
        }
      };
      source.onerror = () => {
        source.close();
      };
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Codex run failed');
    } finally {
      setBusy(null);
    }
  };

  const cancelCodexRun = async () => {
    if (!codexRun) return;
    setBusy('cancel-codex');
    setError(null);
    try {
      const response = await apiClient.cancelCodexRun(codexRun.id);
      setCodexRun(response.data);
      eventSourceRef.current?.close();
      const eventsResponse = await apiClient.getCodexRunEvents(codexRun.id);
      setCodexEvents(eventsResponse.data.events || []);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Cancel failed');
    } finally {
      setBusy(null);
    }
  };

  const sourceCounts = useMemo(() => {
    const counts = brainStatus?.source_counts || {};
    return Object.entries(counts)
      .map(([key, value]) => `${key}: ${value}`)
      .join(', ');
  }, [brainStatus]);

  if (experimentalDisabled) {
    return (
      <div className="flex h-full items-center justify-center bg-background-light p-6 dark:bg-background-dark">
        <section className="max-w-2xl rounded-[4px] border-2 border-border-dark bg-panel-dark p-6 shadow-[5px_5px_0_var(--color-border-dark)]">
          <h1 className="font-serif text-3xl font-semibold text-text-primary">Hermes is disabled by default</h1>
          <p className="mt-3 text-base leading-7 text-text-muted">
            Hermes, Platform Brain, and the local Codex harness can mutate local data or launch a locally authenticated CLI.
            Enable them only for a loopback-only development backend.
          </p>
          <div className="mt-5 rounded-[4px] border-2 border-border-dark bg-white p-4 font-mono text-sm text-text-primary">
            ENABLE_EXPERIMENTAL_LOCAL_APIS=true
          </div>
          <p className="mt-4 text-sm text-text-muted">
            Add the setting to the root <code>.env</code>, restart the backend, then refresh this page. See <code>docs/SETUP.md</code> for the trust-boundary warning.
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-background-light dark:bg-background-dark">
      <div className="flex items-center justify-between border-b-2 border-border-dark bg-panel-dark px-5 py-4">
        <div>
          <h1 className="font-serif text-3xl font-semibold text-text-primary">Hermes</h1>
          <p className="mt-1 text-sm text-text-muted">Project: {activeProject?.name || 'No Project'}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={refresh}
            disabled={Boolean(busy)}
            className="flex h-10 items-center gap-2 rounded-[4px] border-2 border-border-dark bg-white px-3 font-mono text-sm font-semibold text-text-primary shadow-[3px_3px_0_var(--color-border-dark)] transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[1px_1px_0_var(--color-border-dark)]"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="border-b-2 border-red-800 bg-red-50 px-5 py-3 text-sm font-semibold text-red-900 dark:bg-red-950 dark:text-red-100">
          {typeof error === 'string' ? error : formatJson(error)}
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-auto p-5 xl:grid-cols-[minmax(280px,0.95fr)_minmax(360px,1.2fr)_minmax(320px,1fr)]">
        <section className="flex min-h-[640px] flex-col rounded-[4px] border-2 border-border-dark bg-panel-dark shadow-[4px_4px_0_var(--color-border-dark)]">
          <div className="flex items-center justify-between border-b-2 border-border-dark px-4 py-3">
            <div className="flex items-center gap-2 font-semibold text-text-primary">
              <Brain className="h-5 w-5 text-primary" />
              Intent
            </div>
            <div className="text-xs font-mono text-text-muted">{brainStatus?.source_count || 0} sources</div>
          </div>

          <div className="flex flex-1 flex-col gap-4 overflow-auto p-4">
            <textarea
              value={intent}
              onChange={(event) => setIntent(event.target.value)}
              className="min-h-[116px] resize-none rounded-[4px] border-2 border-border-dark bg-white p-3 text-sm text-text-primary outline-none focus:ring-2 focus:ring-primary"
            />
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={searchBrain}
                disabled={Boolean(busy)}
                className="flex h-10 items-center justify-center gap-2 rounded-[4px] border-2 border-border-dark bg-primary px-3 font-mono text-sm font-semibold text-white shadow-[3px_3px_0_var(--color-border-dark)] transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[1px_1px_0_var(--color-border-dark)] disabled:opacity-60"
              >
                <Search className="h-4 w-4" />
                Search
              </button>
              <button
                type="button"
                onClick={reindexBrain}
                disabled={Boolean(busy)}
                className="flex h-10 items-center justify-center gap-2 rounded-[4px] border-2 border-border-dark bg-white px-3 font-mono text-sm font-semibold text-text-primary shadow-[3px_3px_0_var(--color-border-dark)] transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[1px_1px_0_var(--color-border-dark)] disabled:opacity-60"
              >
                <RefreshCw className="h-4 w-4" />
                Reindex
              </button>
            </div>

            {sourceCounts && (
              <div className="rounded-[4px] border-2 border-border-dark bg-white p-3 text-xs font-mono text-text-muted">
                {sourceCounts}
              </div>
            )}

            <div className="space-y-3">
              {brainResults.map((result) => (
                <button
                  key={result.source_id}
                  type="button"
                  onClick={() => setIntent(`${intent}\n\n${result.title}\n${result.highlights?.[0] || ''}`.trim())}
                  className="block w-full rounded-[4px] border-2 border-border-dark bg-white p-3 text-left font-mono shadow-[3px_3px_0_var(--color-border-dark)] transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[1px_1px_0_var(--color-border-dark)]"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-semibold text-text-primary">{result.title}</span>
                    <span className="font-mono text-xs text-text-muted">{Number(result.score || 0).toFixed(0)}</span>
                  </div>
                  <p className="mt-2 line-clamp-3 text-xs leading-5 text-text-muted">{result.highlights?.[0] || result.source_type}</p>
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="flex min-h-[640px] flex-col rounded-[4px] border-2 border-border-dark bg-panel-dark shadow-[4px_4px_0_var(--color-border-dark)]">
          <div className="flex items-center justify-between border-b-2 border-border-dark px-4 py-3">
            <div className="flex items-center gap-2 font-semibold text-text-primary">
              <FileCode2 className="h-5 w-5 text-primary" />
              Draft
            </div>
            <div className="text-xs font-mono text-text-muted">{drafts.length} recent</div>
          </div>

          <div className="grid min-h-0 flex-1 grid-rows-[auto_1fr_auto] gap-4 overflow-hidden p-4">
            <div className="grid grid-cols-[1fr_160px] gap-3">
              <input
                value={draftTitle}
                disabled={Boolean(busy)}
                onChange={(event) => {
                  setDraftTitle(event.target.value);
                  invalidateDraftSelection();
                }}
                className="h-10 rounded-[4px] border-2 border-border-dark bg-white px-3 text-sm font-semibold text-text-primary outline-none focus:ring-2 focus:ring-primary"
              />
              <select
                value={artifactType}
                disabled={Boolean(busy)}
                onChange={(event) => {
                  setArtifactType(event.target.value);
                  invalidateDraftSelection();
                }}
                className="h-10 rounded-[4px] border-2 border-border-dark bg-white px-3 text-sm font-semibold text-text-primary outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="workflow">Workflow</option>
                <option value="deep_agent">DeepAgent</option>
                <option value="custom_tool">Custom Tool</option>
                <option value="schedule">Schedule</option>
                <option value="trigger">Trigger</option>
              </select>
            </div>

            <div className="grid min-h-0 grid-cols-[1fr_220px] gap-3">
              <textarea
                value={payloadText}
                disabled={Boolean(busy)}
                onChange={(event) => {
                  setPayloadText(event.target.value);
                  invalidateDraftSelection();
                }}
                className="min-h-0 resize-none rounded-[4px] border-2 border-border-dark bg-[#1f1b24] p-3 font-mono text-xs leading-5 text-[#f8f0e8] outline-none focus:ring-2 focus:ring-primary"
                spellCheck={false}
              />
              <div className="min-h-0 space-y-2 overflow-auto">
                {drafts.map((draft) => (
                  <button
                    key={draft.id}
                    type="button"
                    disabled={Boolean(busy)}
                    onClick={() => {
                      setSelectedDraft(draft);
                      setDraftTitle(draft.title);
                      setArtifactType(draft.artifact_type);
                      setPayloadText(formatJson(draft.payload_json));
                      setValidationResult(draft.validation_result);
                    }}
                    className={`block w-full rounded-[4px] border-2 p-3 text-left font-mono transition-all ${
                      selectedDraft?.id === draft.id
                        ? 'border-primary bg-primary/10'
                        : 'border-border-dark bg-white hover:bg-background-light'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <StatusMark status={draft.status} />
                      <span className="truncate text-sm font-semibold text-text-primary">{draft.title}</span>
                    </div>
                    <div className="mt-2 font-mono text-xs text-text-muted">#{draft.id} {draft.artifact_type}</div>
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={createDraft}
                disabled={Boolean(busy)}
                className="flex h-10 items-center justify-center gap-2 rounded-[4px] border-2 border-border-dark bg-primary px-3 font-mono text-sm font-semibold text-white shadow-[3px_3px_0_var(--color-border-dark)] transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[1px_1px_0_var(--color-border-dark)] disabled:opacity-60"
              >
                <Send className="h-4 w-4" />
                Draft
              </button>
              <button
                type="button"
                onClick={validateSelectedDraft}
                disabled={!selectedDraft || Boolean(busy)}
                className="flex h-10 items-center justify-center gap-2 rounded-[4px] border-2 border-border-dark bg-white px-3 font-mono text-sm font-semibold text-text-primary shadow-[3px_3px_0_var(--color-border-dark)] transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[1px_1px_0_var(--color-border-dark)] disabled:opacity-60"
              >
                <ShieldCheck className="h-4 w-4" />
                Validate
              </button>
              <button
                type="button"
                onClick={rejectSelectedDraft}
                disabled={!selectedDraft || Boolean(busy)}
                className="flex h-10 items-center justify-center gap-2 rounded-[4px] border-2 border-border-dark bg-white px-3 font-mono text-sm font-semibold text-text-primary shadow-[3px_3px_0_var(--color-border-dark)] transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[1px_1px_0_var(--color-border-dark)] disabled:opacity-60"
              >
                <XCircle className="h-4 w-4" />
                Reject
              </button>
            </div>

            <div className="grid grid-cols-[1fr_1fr_130px] gap-2">
              <input
                value={targetId}
                disabled={Boolean(busy)}
                onChange={(event) => setTargetId(event.target.value)}
                placeholder="target id"
                className="h-10 rounded-[4px] border-2 border-border-dark bg-white px-3 text-sm text-text-primary outline-none focus:ring-2 focus:ring-primary"
              />
              <input
                value={lockVersion}
                disabled={Boolean(busy)}
                onChange={(event) => setLockVersion(event.target.value)}
                placeholder="lock version"
                className="h-10 rounded-[4px] border-2 border-border-dark bg-white px-3 text-sm text-text-primary outline-none focus:ring-2 focus:ring-primary"
              />
              <button
                type="button"
                onClick={applySelectedDraft}
                disabled={!selectedDraft || Boolean(busy)}
                className="flex h-10 items-center justify-center gap-2 rounded-[4px] border-2 border-border-dark bg-green-700 px-3 font-mono text-sm font-semibold text-white shadow-[3px_3px_0_var(--color-border-dark)] transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[1px_1px_0_var(--color-border-dark)] disabled:opacity-60"
              >
                <CheckCircle2 className="h-4 w-4" />
                Apply
              </button>
            </div>

            {selectedResult && (
              <pre className="max-h-44 overflow-auto rounded-[4px] border-2 border-border-dark bg-white p-3 font-mono text-xs leading-5 text-text-primary">
                {formatJson(selectedResult)}
              </pre>
            )}
          </div>
        </section>

        <section className="flex min-h-[640px] flex-col rounded-[4px] border-2 border-border-dark bg-panel-dark shadow-[4px_4px_0_var(--color-border-dark)]">
          <div className="flex items-center justify-between border-b-2 border-border-dark px-4 py-3">
            <div className="flex items-center gap-2 font-semibold text-text-primary">
              <Terminal className="h-5 w-5 text-primary" />
              Codex
            </div>
            <div className="flex items-center gap-2 text-xs font-mono text-text-muted">
              <StatusMark status={codexReady ? 'validated' : 'failed'} />
              {codexStatus?.version || 'unknown'}
            </div>
          </div>

          <div className="flex flex-1 flex-col gap-4 overflow-auto p-4">
            <pre className="max-h-36 overflow-auto rounded-[4px] border-2 border-border-dark bg-white p-3 font-mono text-xs leading-5 text-text-primary">
              {formatJson(codexStatus || {})}
            </pre>
            <textarea
              value={codexPrompt}
              onChange={(event) => setCodexPrompt(event.target.value)}
              className="min-h-[140px] resize-none rounded-[4px] border-2 border-border-dark bg-white p-3 text-sm text-text-primary outline-none focus:ring-2 focus:ring-primary"
            />
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={startCodexRun}
                disabled={Boolean(busy) || !codexPrompt.trim()}
                className="flex h-10 items-center justify-center gap-2 rounded-[4px] border-2 border-border-dark bg-primary px-3 font-mono text-sm font-semibold text-white shadow-[3px_3px_0_var(--color-border-dark)] transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[1px_1px_0_var(--color-border-dark)] disabled:opacity-60"
              >
                <Play className="h-4 w-4" />
                Run
              </button>
              <button
                type="button"
                onClick={cancelCodexRun}
                disabled={!codexRun || Boolean(busy)}
                className="flex h-10 items-center justify-center gap-2 rounded-[4px] border-2 border-border-dark bg-white px-3 font-mono text-sm font-semibold text-text-primary shadow-[3px_3px_0_var(--color-border-dark)] transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[1px_1px_0_var(--color-border-dark)] disabled:opacity-60"
              >
                <CircleStop className="h-4 w-4" />
                Cancel
              </button>
            </div>

            {codexRun && (
              <div className="rounded-[4px] border-2 border-border-dark bg-white p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-mono text-xs text-text-muted">{codexRun.id}</div>
                  <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
                    <StatusMark status={codexRun.status} />
                    {codexRun.status}
                  </div>
                </div>
                {codexRun.sandbox_dir && (
                  <div className="mt-2 break-all font-mono text-xs text-text-muted">{codexRun.sandbox_dir}</div>
                )}
              </div>
            )}

            <div className="min-h-[260px] rounded-[4px] border-2 border-border-dark bg-[#1f1b24] p-3 font-mono text-xs leading-5 text-[#f8f0e8]">
              {codexEvents.length === 0 ? (
                <div className="text-[#b8aebe]">No events</div>
              ) : (
                codexEvents.map((event, index) => (
                  <div key={`${event.index ?? index}-${event.type || 'event'}`} className="mb-2 border-b border-white/10 pb-2">
                    <span className="text-primary">{event.type || event.event?.type || 'event'}</span>
                    <pre className="mt-1 whitespace-pre-wrap break-words">{formatJson(event.event || event.message || event)}</pre>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
