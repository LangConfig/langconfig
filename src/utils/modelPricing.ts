/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Model Pricing Database
 *
 * Accurate per-token pricing for different AI models.
 * Prices are per 1M tokens (input and output separately).
 * Updated December 2025.
 *
 * Sources:
 * - OpenAI: https://openai.com/api/pricing/
 * - Anthropic: https://docs.anthropic.com/en/docs/about-claude/models/overview
 * - Google: https://ai.google.dev/pricing
 */

export interface ModelPricing {
  input: number;  // Cost per 1M input tokens
  output: number; // Cost per 1M output tokens
}

export const MODEL_PRICING: Record<string, ModelPricing> = {
  // OpenAI Reasoning Models
  'o3': { input: 20.00, output: 80.00 },
  'o3-mini': { input: 4.00, output: 16.00 },
  'o4-mini': { input: 3.00, output: 12.00 },

  // OpenAI GPT-4o Series
  'gpt-4o': { input: 2.50, output: 10.00 },
  'gpt-4o-mini': { input: 0.15, output: 0.60 },

  // Anthropic Claude 4.5
  'claude-opus-4-5': { input: 15.00, output: 75.00 },
  'claude-sonnet-4-5': { input: 3.00, output: 15.00 },
  'claude-sonnet-4-5-20250929': { input: 3.00, output: 15.00 },
  'claude-haiku-4-5': { input: 1.00, output: 5.00 },

  // Google Gemini 3
  'gemini-3-pro-preview': { input: 2.00, output: 12.00 },

  // Google Gemini 2.5
  'gemini-2.5-flash': { input: 0.075, output: 0.30 },

  // Google Gemini 2.0
  'gemini-2.0-flash': { input: 0.075, output: 0.30 },

  // Default fallback
  'default': { input: 1.00, output: 3.00 }
};

/**
 * Get pricing for a specific model
 */
export function getModelPricing(modelName: string): ModelPricing {
  // Normalize model name
  const normalized = modelName.toLowerCase().trim();

  // Try exact match first
  if (MODEL_PRICING[normalized]) {
    return MODEL_PRICING[normalized];
  }

  // Try partial matches
  for (const [key, pricing] of Object.entries(MODEL_PRICING)) {
    if (normalized.includes(key) || key.includes(normalized)) {
      return pricing;
    }
  }

  // Fallback to default
  console.warn(`Unknown model "${modelName}", using default pricing`);
  return MODEL_PRICING['default'];
}

/**
 * Calculate cost for token usage
 */
export function calculateCost(
  inputTokens: number,
  outputTokens: number,
  modelName: string
): number {
  const pricing = getModelPricing(modelName);

  // Prices are per 1M tokens, so divide by 1,000,000
  const inputCost = (inputTokens / 1_000_000) * pricing.input;
  const outputCost = (outputTokens / 1_000_000) * pricing.output;

  return inputCost + outputCost;
}

/**
 * Format cost for display
 */
export function formatCost(cost: number): string {
  if (cost < 0.001) {
    return '< $0.001';
  }

  if (cost < 0.01) {
    return `$${cost.toFixed(4)}`;
  }

  if (cost < 1.00) {
    return `$${cost.toFixed(3)}`;
  }

  return `$${cost.toFixed(2)}`;
}

/**
 * Calculate and format cost in one call
 */
export function calculateAndFormatCost(
  inputTokens: number,
  outputTokens: number,
  modelName: string
): string {
  const cost = calculateCost(inputTokens, outputTokens, modelName);
  return formatCost(cost);
}
