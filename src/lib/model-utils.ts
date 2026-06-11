/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Model display name mappings for user-friendly presentation
 */
export const MODEL_DISPLAY_NAMES: Record<string, string> = {
  // OpenAI - selectable current models
  'gpt-5.5': 'GPT-5.5',
  'gpt-5.4': 'GPT-5.4',
  'gpt-5.4-mini': 'GPT-5.4 Mini',
  'gpt-5.4-nano': 'GPT-5.4 Nano',

  // Claude - selectable current models
  'claude-opus-4-8': 'Claude Opus 4.8',
  'claude-sonnet-4-6': 'Claude Sonnet 4.6',
  'claude-haiku-4-5': 'Claude Haiku 4.5',

  // Legacy display only. These should not be returned by the selectable model API.
  'gpt-5.2': 'GPT-5.2',
  'gpt-5.1': 'GPT-5.1',
  'gpt-5': 'GPT-5',
  'gpt-5-pro': 'GPT-5 Pro',
  'gpt-4o': 'GPT-4o',
  'gpt-4o-mini': 'GPT-4o Mini',
  'claude-opus-4-5': 'Claude Opus 4.5',
  'claude-sonnet-4-5': 'Claude Sonnet 4.5',
  'claude-sonnet-4-5-20250929': 'Claude Sonnet 4.5',
  'claude-3-5-sonnet-20241022': 'Claude 3.5 Sonnet',
  'claude-3-5-haiku-20241022': 'Claude 3.5 Haiku',
  'claude-3-opus-20240229': 'Claude 3 Opus',

  // Gemini
  'gemini-2.5-pro': 'Gemini 2.5 Pro',
  'gemini-2.5-flash': 'Gemini 2.5 Flash',
  'gemini-2.5-flash-lite': 'Gemini 2.5 Flash Lite',
  'gemini-2.0-flash-exp': 'Gemini 2.0 Flash (Experimental)',
  'gemini-2.0-flash': 'Gemini 2.0 Flash',
};

/**
 * Get a user-friendly display name for a model
 * Falls back to the original model ID if no mapping exists
 */
export function getModelDisplayName(modelId: string | null | undefined): string {
  if (!modelId) return '';
  if (MODEL_DISPLAY_NAMES[modelId]) return MODEL_DISPLAY_NAMES[modelId];
  if (modelId.startsWith('local-')) return modelId.slice('local-'.length);
  return modelId;
}

/**
 * Get the API model ID from a display name
 * Falls back to the input if no reverse mapping exists
 */
export function getModelId(displayName: string): string {
  const entry = Object.entries(MODEL_DISPLAY_NAMES).find(
    ([_, display]) => display === displayName
  );
  return entry ? entry[0] : displayName;
}
