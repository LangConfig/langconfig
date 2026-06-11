import { useCallback, useEffect, useState } from 'react';
import { apiClient } from '@/lib/api-client';
import SettingsSection from './SettingsSection';

// ─── Types ─────────────────────────────────────────────────────────────────

interface CustomPIIType {
  name: string;
  trigger_phrases: string[];
  value_regex: string;
}

interface PIIProfile {
  id: number;
  name: string;
  description: string | null;
  project_id: number | null;
  blocklist: string[];
  allowlist: string[];
  custom_types: CustomPIIType[];
  enabled_builtin_types: string[];
  created_at: string;
  updated_at: string;
}

interface EditablePIIProfile {
  id?: number;
  name: string;
  description: string;
  blocklist: string[];
  allowlist: string[];
  custom_types: CustomPIIType[];
  enabled_builtin_types: string[];
}

const EMPTY_PROFILE: EditablePIIProfile = {
  name: '',
  description: '',
  blocklist: [],
  allowlist: [],
  custom_types: [],
  enabled_builtin_types: [],
};

// ─── Tag input ─────────────────────────────────────────────────────────────

function TagInput({
  value,
  onChange,
  placeholder,
}: {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder: string;
}) {
  const [input, setInput] = useState('');

  const addTag = () => {
    const trimmed = input.trim();
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed]);
      setInput('');
    }
  };

  return (
    <div>
      <div className="flex flex-wrap gap-1.5 mb-2">
        {value.map((tag, i) => (
          <span
            key={i}
            className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs bg-gray-100 dark:bg-white/10"
            style={{ color: 'var(--color-text-primary)' }}
          >
            {tag}
            <button
              onClick={() => onChange(value.filter((_, j) => j !== i))}
              className="text-gray-500 hover:text-red-500"
            >
              ×
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              addTag();
            }
          }}
          placeholder={placeholder}
          className="flex-1 px-3 py-2 text-sm border rounded"
          style={{
            backgroundColor: 'var(--color-input-background)',
            borderColor: 'var(--color-border)',
            color: 'var(--color-text-primary)',
          }}
        />
        <button
          onClick={addTag}
          type="button"
          className="px-3 py-2 text-sm rounded"
          style={{ backgroundColor: 'var(--color-primary)', color: 'white' }}
        >
          Add
        </button>
      </div>
    </div>
  );
}

// ─── Profile editor modal ──────────────────────────────────────────────────

function ProfileEditor({
  profile,
  availableTypes,
  onSave,
  onCancel,
}: {
  profile: EditablePIIProfile;
  availableTypes: string[];
  onSave: (profile: EditablePIIProfile) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState<EditablePIIProfile>(profile);
  const [testText, setTestText] = useState('');
  const [testResult, setTestResult] = useState<{
    redacted_text: string;
    items_detected: number;
    types_detected: string[];
  } | null>(null);

  const toggleBuiltin = (type: string) => {
    if (draft.enabled_builtin_types.includes(type)) {
      setDraft({
        ...draft,
        enabled_builtin_types: draft.enabled_builtin_types.filter((t) => t !== type),
      });
    } else {
      setDraft({
        ...draft,
        enabled_builtin_types: [...draft.enabled_builtin_types, type],
      });
    }
  };

  const addCustomType = () => {
    setDraft({
      ...draft,
      custom_types: [
        ...draft.custom_types,
        { name: '', trigger_phrases: [], value_regex: '' },
      ],
    });
  };

  const updateCustomType = (index: number, field: keyof CustomPIIType, value: unknown) => {
    const updated = [...draft.custom_types];
    updated[index] = { ...updated[index], [field]: value };
    setDraft({ ...draft, custom_types: updated });
  };

  const removeCustomType = (index: number) => {
    setDraft({ ...draft, custom_types: draft.custom_types.filter((_, i) => i !== index) });
  };

  const runTest = useCallback(async () => {
    if (!draft.id || !testText.trim()) return;
    try {
      const res = await fetch(`${apiClient.baseURL}/api/pii-profiles/${draft.id}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: testText, strategy: 'redact' }),
      });
      const data = await res.json();
      setTestResult(data);
    } catch (e) {
      console.error(e);
    }
  }, [draft.id, testText]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}
      onClick={onCancel}
    >
      <div
        className="bg-white dark:bg-panel-dark rounded-xl shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-4 border-b border-gray-200 dark:border-border-dark">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            {draft.id ? 'Edit PII Profile' : 'New PII Profile'}
          </h2>
        </div>

        <div className="p-6 space-y-5">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
              Name
            </label>
            <input
              type="text"
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              placeholder="e.g. Internal Review"
              className="w-full px-3 py-2 border rounded"
              style={{
                backgroundColor: 'var(--color-input-background)',
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-primary)',
              }}
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
              Description
            </label>
            <textarea
              value={draft.description}
              onChange={(e) => setDraft({ ...draft, description: e.target.value })}
              placeholder="What this profile is for"
              rows={2}
              className="w-full px-3 py-2 border rounded text-sm"
              style={{
                backgroundColor: 'var(--color-input-background)',
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-primary)',
              }}
            />
          </div>

          {/* Blocklist */}
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
              Blocklist — always redacted
            </label>
            <p className="text-xs mb-2" style={{ color: 'var(--color-text-muted)' }}>
              Literal terms to redact regardless of context (e.g. internal project names, private labels)
            </p>
            <TagInput
              value={draft.blocklist}
              onChange={(tags) => setDraft({ ...draft, blocklist: tags })}
              placeholder="Type a term and press Enter"
            />
          </div>

          {/* Allowlist */}
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
              Allowlist — never redacted
            </label>
            <p className="text-xs mb-2" style={{ color: 'var(--color-text-muted)' }}>
              Terms that should pass through even if a detector would flag them
            </p>
            <TagInput
              value={draft.allowlist}
              onChange={(tags) => setDraft({ ...draft, allowlist: tags })}
              placeholder="Type a term and press Enter"
            />
          </div>

          {/* Custom types */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div>
                <label className="block text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                  Custom PII Types
                </label>
                <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  Define your own types with trigger phrases and value patterns
                </p>
              </div>
              <button
                onClick={addCustomType}
                type="button"
                className="text-xs px-3 py-1.5 rounded border"
                style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}
              >
                + Add type
              </button>
            </div>
            <div className="space-y-3">
              {draft.custom_types.map((ct, i) => (
                <div
                  key={i}
                  className="p-3 rounded border space-y-2"
                  style={{ borderColor: 'var(--color-border)' }}
                >
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={ct.name}
                      onChange={(e) => updateCustomType(i, 'name', e.target.value)}
                      placeholder="type name (e.g. employee_id)"
                      className="flex-1 px-2 py-1 text-sm border rounded"
                      style={{
                        backgroundColor: 'var(--color-input-background)',
                        borderColor: 'var(--color-border)',
                        color: 'var(--color-text-primary)',
                      }}
                    />
                    <button
                      onClick={() => removeCustomType(i)}
                      type="button"
                      className="text-xs px-2 py-1 rounded text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10"
                    >
                      Remove
                    </button>
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>
                      Trigger phrases
                    </label>
                    <TagInput
                      value={ct.trigger_phrases}
                      onChange={(tags) => updateCustomType(i, 'trigger_phrases', tags)}
                      placeholder='e.g. "employee ID"'
                    />
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>
                      Value regex
                    </label>
                    <input
                      type="text"
                      value={ct.value_regex}
                      onChange={(e) => updateCustomType(i, 'value_regex', e.target.value)}
                      placeholder="e.g. EMP-\\d+"
                      className="w-full px-2 py-1 text-sm font-mono border rounded"
                      style={{
                        backgroundColor: 'var(--color-input-background)',
                        borderColor: 'var(--color-border)',
                        color: 'var(--color-text-primary)',
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Built-in types */}
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
              Built-in Types
            </label>
            <p className="text-xs mb-2" style={{ color: 'var(--color-text-muted)' }}>
              Leave all unchecked to enable all types. Check specific ones to enable ONLY those.
            </p>
            <div className="grid grid-cols-3 gap-2">
              {availableTypes.map((type) => (
                <label
                  key={type}
                  className="flex items-center gap-2 text-sm cursor-pointer"
                  style={{ color: 'var(--color-text-primary)' }}
                >
                  <input
                    type="checkbox"
                    checked={draft.enabled_builtin_types.includes(type)}
                    onChange={() => toggleBuiltin(type)}
                  />
                  <span>{type}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Test panel (only for saved profiles) */}
          {draft.id && (
            <div className="pt-4 border-t" style={{ borderColor: 'var(--color-border)' }}>
              <label className="block text-sm font-medium mb-2" style={{ color: 'var(--color-text-primary)' }}>
                Test
              </label>
              <textarea
                value={testText}
                onChange={(e) => setTestText(e.target.value)}
                placeholder="Paste sample text to see what this profile would redact..."
                rows={3}
                className="w-full px-3 py-2 border rounded text-sm font-mono"
                style={{
                  backgroundColor: 'var(--color-input-background)',
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text-primary)',
                }}
              />
              <button
                onClick={runTest}
                type="button"
                disabled={!testText.trim()}
                className="mt-2 px-3 py-1.5 text-sm rounded"
                style={{ backgroundColor: 'var(--color-primary)', color: 'white', opacity: testText.trim() ? 1 : 0.5 }}
              >
                Run test
              </button>
              {testResult && (
                <div className="mt-3 p-3 rounded bg-gray-50 dark:bg-white/5 text-sm">
                  <div className="font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                    Redacted output:
                  </div>
                  <pre
                    className="font-mono text-xs whitespace-pre-wrap mb-2"
                    style={{ color: 'var(--color-text-primary)' }}
                  >
                    {testResult.redacted_text}
                  </pre>
                  <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                    {testResult.items_detected} item(s) detected
                    {testResult.types_detected.length > 0 && ` — types: ${testResult.types_detected.join(', ')}`}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-gray-200 dark:border-border-dark flex justify-end gap-2">
          <button
            onClick={onCancel}
            type="button"
            className="px-4 py-2 text-sm rounded border"
            style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}
          >
            Cancel
          </button>
          <button
            onClick={() => onSave(draft)}
            type="button"
            disabled={!draft.name.trim()}
            className="px-4 py-2 text-sm rounded"
            style={{ backgroundColor: 'var(--color-primary)', color: 'white', opacity: draft.name.trim() ? 1 : 0.5 }}
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────────

export default function PIIProfilesSettings() {
  const [profiles, setProfiles] = useState<PIIProfile[]>([]);
  const [availableTypes, setAvailableTypes] = useState<string[]>([]);
  const [editing, setEditing] = useState<EditablePIIProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchProfiles = useCallback(async () => {
    try {
      const res = await fetch(`${apiClient.baseURL}/api/pii-profiles`);
      const data: PIIProfile[] = await res.json();
      setProfiles(data);
    } catch (e) {
      console.error('Failed to fetch profiles', e);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchTypes = useCallback(async () => {
    try {
      const res = await fetch(`${apiClient.baseURL}/api/pii-profiles/types/available`);
      const data = await res.json();
      setAvailableTypes(data.builtin_types || []);
    } catch (e) {
      console.error('Failed to fetch types', e);
    }
  }, []);

  useEffect(() => {
    fetchProfiles();
    fetchTypes();
  }, [fetchProfiles, fetchTypes]);

  const saveProfile = async (draft: EditablePIIProfile) => {
    try {
      const url = draft.id
        ? `${apiClient.baseURL}/api/pii-profiles/${draft.id}`
        : `${apiClient.baseURL}/api/pii-profiles`;
      const method = draft.id ? 'PUT' : 'POST';
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draft),
      });
      if (!res.ok) throw new Error(await res.text());
      await fetchProfiles();
      setEditing(null);
    } catch (e) {
      alert(`Save failed: ${e}`);
    }
  };

  const deleteProfile = async (id: number) => {
    if (!confirm('Delete this profile?')) return;
    try {
      await fetch(`${apiClient.baseURL}/api/pii-profiles/${id}`, { method: 'DELETE' });
      await fetchProfiles();
    } catch (e) {
      alert(`Delete failed: ${e}`);
    }
  };

  return (
    <SettingsSection
      title="PII Profiles"
      description="Named redaction rules that agents and workflow nodes can apply. Blocklists, allowlists, and custom PII types."
    >
      <div className="flex justify-end mb-4">
        <button
          onClick={() => setEditing({ ...EMPTY_PROFILE })}
          className="px-4 py-2 text-sm rounded"
          style={{ backgroundColor: 'var(--color-primary)', color: 'white' }}
        >
          + New Profile
        </button>
      </div>

      {loading ? (
        <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
          Loading...
        </p>
      ) : profiles.length === 0 ? (
        <div
          className="p-8 text-center rounded border"
          style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }}
        >
          <p className="text-sm">No profiles yet. Create one to get started.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {profiles.map((p) => (
            <div
              key={p.id}
              className="flex items-center justify-between p-3 rounded border hover:bg-gray-50 dark:hover:bg-white/5"
              style={{ borderColor: 'var(--color-border)' }}
            >
              <div className="flex-1 min-w-0">
                <div className="font-medium" style={{ color: 'var(--color-text-primary)' }}>
                  {p.name}
                </div>
                {p.description && (
                  <div className="text-sm truncate" style={{ color: 'var(--color-text-muted)' }}>
                    {p.description}
                  </div>
                )}
                <div className="text-xs mt-1 flex gap-3" style={{ color: 'var(--color-text-muted)' }}>
                  {p.blocklist.length > 0 && <span>Block: {p.blocklist.length}</span>}
                  {p.allowlist.length > 0 && <span>Allow: {p.allowlist.length}</span>}
                  {p.custom_types.length > 0 && <span>Custom: {p.custom_types.length}</span>}
                  <span>
                    Built-ins: {p.enabled_builtin_types.length === 0 ? 'all' : p.enabled_builtin_types.length}
                  </span>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() =>
                    setEditing({
                      id: p.id,
                      name: p.name,
                      description: p.description || '',
                      blocklist: p.blocklist,
                      allowlist: p.allowlist,
                      custom_types: p.custom_types,
                      enabled_builtin_types: p.enabled_builtin_types,
                    })
                  }
                  className="px-3 py-1.5 text-sm rounded border"
                  style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}
                >
                  Edit
                </button>
                <button
                  onClick={() => deleteProfile(p.id)}
                  className="px-3 py-1.5 text-sm rounded text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {editing && (
        <ProfileEditor
          profile={editing}
          availableTypes={availableTypes}
          onSave={saveProfile}
          onCancel={() => setEditing(null)}
        />
      )}
    </SettingsSection>
  );
}
