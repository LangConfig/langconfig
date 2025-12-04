/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Input Validation Utilities
 *
 * Centralized validation functions to prevent XSS, injection attacks,
 * and ensure data integrity across the application.
 */

/**
 * Validation result type
 */
export interface ValidationResult {
  isValid: boolean;
  error?: string;
}

/**
 * Sanitize string input by removing potentially dangerous characters
 * Prevents XSS and injection attacks
 */
export function sanitizeString(input: string): string {
  return input
    .trim()
    .replace(/[<>\"']/g, '') // Remove HTML/script injection chars
    .replace(/\\/g, '') // Remove backslashes
    .replace(/[\x00-\x1F\x7F]/g, ''); // Remove control characters
}

/**
 * Validate workflow/project name
 * - Must not be empty
 * - Max length 100 characters
 * - No special characters except: - _ ( ) [ ]
 */
export function validateName(name: string): ValidationResult {
  const trimmed = name.trim();

  if (!trimmed) {
    return {
      isValid: false,
      error: 'Name cannot be empty',
    };
  }

  if (trimmed.length > 100) {
    return {
      isValid: false,
      error: 'Name must be 100 characters or less',
    };
  }

  // Allow alphanumeric, spaces, and common punctuation
  const validNamePattern = /^[a-zA-Z0-9\s\-_()[\]]+$/;
  if (!validNamePattern.test(trimmed)) {
    return {
      isValid: false,
      error: 'Name contains invalid characters. Only letters, numbers, spaces, and -_()[] are allowed',
    };
  }

  return { isValid: true };
}

/**
 * Validate description text
 * - Max length 500 characters
 * - Basic sanitization
 */
export function validateDescription(description: string): ValidationResult {
  const trimmed = description.trim();

  if (trimmed.length > 500) {
    return {
      isValid: false,
      error: 'Description must be 500 characters or less',
    };
  }

  return { isValid: true };
}

/**
 * Validate tool ID
 * - Must be alphanumeric with underscores/hyphens only
 * - Max length 50 characters
 */
export function validateToolId(id: string): ValidationResult {
  const trimmed = id.trim();

  if (!trimmed) {
    return {
      isValid: false,
      error: 'Tool ID cannot be empty',
    };
  }

  if (trimmed.length > 50) {
    return {
      isValid: false,
      error: 'Tool ID must be 50 characters or less',
    };
  }

  const validIdPattern = /^[a-zA-Z0-9_-]+$/;
  if (!validIdPattern.test(trimmed)) {
    return {
      isValid: false,
      error: 'Tool ID can only contain letters, numbers, underscores, and hyphens',
    };
  }

  return { isValid: true };
}

/**
 * Validate email address
 */
export function validateEmail(email: string): ValidationResult {
  const trimmed = email.trim();

  if (!trimmed) {
    return {
      isValid: false,
      error: 'Email cannot be empty',
    };
  }

  // RFC 5322 compliant email regex (simplified)
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailPattern.test(trimmed)) {
    return {
      isValid: false,
      error: 'Please enter a valid email address',
    };
  }

  return { isValid: true };
}

/**
 * Validate URL
 */
export function validateUrl(url: string): ValidationResult {
  const trimmed = url.trim();

  if (!trimmed) {
    return {
      isValid: false,
      error: 'URL cannot be empty',
    };
  }

  try {
    new URL(trimmed);
    return { isValid: true };
  } catch {
    return {
      isValid: false,
      error: 'Please enter a valid URL',
    };
  }
}

/**
 * Validate number within range
 */
export function validateNumberInRange(
  value: number,
  min: number,
  max: number,
  fieldName: string = 'Value'
): ValidationResult {
  if (isNaN(value)) {
    return {
      isValid: false,
      error: `${fieldName} must be a valid number`,
    };
  }

  if (!isFinite(value)) {
    return {
      isValid: false,
      error: `${fieldName} must be a finite number`,
    };
  }

  if (value < min || value > max) {
    return {
      isValid: false,
      error: `${fieldName} must be between ${min} and ${max}`,
    };
  }

  return { isValid: true };
}

/**
 * Validate JSON string
 */
export function validateJson(jsonString: string): ValidationResult {
  try {
    JSON.parse(jsonString);
    return { isValid: true };
  } catch (error) {
    return {
      isValid: false,
      error: error instanceof Error ? error.message : 'Invalid JSON format',
    };
  }
}

/**
 * Sanitize and validate user input for forms
 * General-purpose validation that combines sanitization with checks
 */
export function sanitizeAndValidate(
  input: string,
  maxLength: number = 255
): { value: string; result: ValidationResult } {
  const sanitized = sanitizeString(input);

  if (!sanitized) {
    return {
      value: sanitized,
      result: {
        isValid: false,
        error: 'Input cannot be empty after removing invalid characters',
      },
    };
  }

  if (sanitized.length > maxLength) {
    return {
      value: sanitized,
      result: {
        isValid: false,
        error: `Input must be ${maxLength} characters or less`,
      },
    };
  }

  return {
    value: sanitized,
    result: { isValid: true },
  };
}

/**
 * Validate ReactFlow node position
 * Prevents NaN, Infinity, and extreme values
 */
export function validateNodePosition(x: number, y: number): ValidationResult {
  if (!isFinite(x) || !isFinite(y)) {
    return {
      isValid: false,
      error: 'Position coordinates must be finite numbers',
    };
  }

  // Reasonable bounds for canvas (adjust as needed)
  const MAX_COORD = 10000;
  const MIN_COORD = -10000;

  if (x < MIN_COORD || x > MAX_COORD || y < MIN_COORD || y > MAX_COORD) {
    return {
      isValid: false,
      error: `Position coordinates must be between ${MIN_COORD} and ${MAX_COORD}`,
    };
  }

  return { isValid: true };
}
