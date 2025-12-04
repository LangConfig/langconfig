/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { ReactNode } from 'react';

interface SettingsSectionProps {
  title: string;
  description?: string;
  children: ReactNode;
  icon?: string;
}

export default function SettingsSection({
  title,
  description,
  children,
  icon
}: SettingsSectionProps) {
  return (
    <section className="bg-white dark:bg-panel-dark border border-gray-200 dark:border-border-dark rounded-lg p-5 mb-4">
      {/* Section Header */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-1">
          {icon && (
            <span className="material-symbols-outlined text-lg" style={{ color: 'var(--color-primary)' }}>
              {icon}
            </span>
          )}
          <h2 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            {title}
          </h2>
        </div>
        {description && (
          <p className="text-sm leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
            {description}
          </p>
        )}
      </div>

      {/* Section Content */}
      <div className="space-y-3">
        {children}
      </div>
    </section>
  );
}

// Reusable input field component for settings
interface SettingsInputProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: 'text' | 'password' | 'number' | 'url';
  placeholder?: string;
  description?: string;
  required?: boolean;
  disabled?: boolean;
}

export function SettingsInput({
  label,
  value,
  onChange,
  type = 'text',
  placeholder,
  description,
  required = false,
  disabled = false
}: SettingsInputProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className="px-3 py-1.5 text-sm border border-gray-300 dark:border-border-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
        style={{
          backgroundColor: 'var(--color-input-background)',
          color: 'var(--color-text-primary)'
        }}
      />
      {description && (
        <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
          {description}
        </p>
      )}
    </div>
  );
}

// Reusable select/dropdown component
interface SettingsSelectProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  description?: string;
  required?: boolean;
  disabled?: boolean;
}

export function SettingsSelect({
  label,
  value,
  onChange,
  options,
  description,
  required = false,
  disabled = false
}: SettingsSelectProps) {
  return (
    <div className="flex flex-col gap-2">
      <label className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="px-3 py-2 border border-gray-300 dark:border-border-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
        style={{
          backgroundColor: 'var(--color-input-background)',
          color: 'var(--color-text-primary)'
        }}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {description && (
        <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          {description}
        </p>
      )}
    </div>
  );
}

// Reusable checkbox component
interface SettingsCheckboxProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  description?: string;
  disabled?: boolean;
}

export function SettingsCheckbox({
  label,
  checked,
  onChange,
  description,
  disabled = false
}: SettingsCheckboxProps) {
  return (
    <div className="flex items-start gap-2.5">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
        className="mt-0.5 w-4 h-4 text-primary bg-white dark:bg-background-dark border-gray-300 dark:border-border-dark rounded focus:ring-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
      />
      <div className="flex-1">
        <label className="text-sm font-medium cursor-pointer" style={{ color: 'var(--color-text-primary)' }}>
          {label}
        </label>
        {description && (
          <p className="text-xs mt-0.5 leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
            {description}
          </p>
        )}
      </div>
    </div>
  );
}
