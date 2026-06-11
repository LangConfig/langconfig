import { useEffect, useState } from 'react';
import { apiClient } from '@/lib/api-client';

interface PIIProfileLite {
  id: number;
  name: string;
  description: string | null;
}

interface Props {
  currentValue: number | null;
  onChange: (profileId: number | null) => void;
}

export default function PIIProfileSelector({ currentValue, onChange }: Props) {
  const [profiles, setProfiles] = useState<PIIProfileLite[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchProfiles = async () => {
      try {
        const res = await fetch(`${apiClient.baseURL}/api/pii-profiles`);
        const data = await res.json();
        setProfiles(Array.isArray(data) ? data : []);
      } catch (e) {
        console.error('Failed to load PII profiles', e);
      } finally {
        setLoading(false);
      }
    };
    fetchProfiles();
  }, []);

  return (
    <div className="mt-4">
      <label
        className="block text-sm font-medium mb-1"
        style={{ color: 'var(--color-text-primary)' }}
      >
        PII Profile
      </label>
      <p className="text-xs mb-2" style={{ color: 'var(--color-text-muted)' }}>
        Apply a named set of redaction rules. Manage profiles in Settings / PII Profiles.
      </p>
      <select
        value={currentValue ?? ''}
        onChange={(e) => {
          const val = e.target.value;
          onChange(val === '' ? null : parseInt(val, 10));
        }}
        disabled={loading}
        onMouseDown={(e) => e.stopPropagation()}
        onWheel={(e) => e.stopPropagation()}
        className="w-full px-3 py-2 border rounded-lg"
        style={{
          backgroundColor: 'var(--color-input-background)',
          borderColor: 'var(--color-border-dark)',
          color: 'var(--color-text-primary)',
        }}
      >
        <option value="">None (all built-in types)</option>
        {profiles.map((p) => {
          const description = p.description
            ? ` - ${p.description.slice(0, 40)}${p.description.length > 40 ? '...' : ''}`
            : '';
          return (
            <option key={p.id} value={p.id}>
              {p.name}
              {description}
            </option>
          );
        })}
      </select>
      {!loading && profiles.length === 0 && (
        <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
          No profiles yet. Create one in Settings / PII Profiles.
        </p>
      )}
    </div>
  );
}
