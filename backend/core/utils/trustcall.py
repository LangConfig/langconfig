# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Trustcall Validator for LangConfig.

Implements LangGraph's Trustcall pattern: "Patch Don't Post"
Instead of regenerating entire JSON on validation errors, generates minimal
JSON Patch operations to fix specific issues.

This achieves 10x token savings on error correction:
- Full regeneration: 1000 tokens per retry
- Patch generation: ~50-100 tokens per retry

Inspired by LangGraph's trustcall pattern.
"""

import json
import jsonpatch
import logging
from typing import Type, Dict, Any, List, Optional
from pydantic import BaseModel, ValidationError
from datetime import datetime

logger = logging.getLogger(__name__)


class ValidationAttempt:
    """Record of a validation attempt."""

    def __init__(
        self,
        attempt_number: int,
        success: bool,
        error: Optional[str] = None,
        patch_applied: Optional[List[Dict]] = None,
        tokens_used: int = 0
    ):
        self.attempt_number = attempt_number
        self.success = success
        self.error = error
        self.patch_applied = patch_applied
        self.tokens_used = tokens_used
        self.timestamp = datetime.utcnow()


class TrustcallValidator:
    """
    Resilient structured output validator using JSON Patch correction.

    When structured output fails validation, instead of asking the LLM to
    regenerate the entire (potentially large) object, we:
    1. Identify the specific validation error
    2. Generate a minimal JSON Patch to fix only that error
    3. Apply the patch and retry validation

    This is:
    - 10x more token-efficient
    - Faster (smaller prompts/responses)
    - More accurate (focused corrections)
    - Less likely to break correct parts

    Example Usage:
        >>> validator = TrustcallValidator(llm_client=litellm)
        >>> result = await validator.extract_with_validation(
        ...     prompt="Decompose this task...",
        ...     schema=TaskDecomposition,
        ...     context="project context"
        ... )
        >>> # Result is guaranteed to match schema or raise after max retries
    """

    def __init__(
        self,
        llm_client,
        max_retries: int = 3,
        patch_model: str = "gpt-4o-mini",  # Use cheap model for patches
        extraction_model: str = "gpt-4o"
    ):
        """
        Initialize Trustcall validator.

        Args:
            llm_client: LiteLLM client for API calls
            max_retries: Maximum validation retry attempts
            patch_model: Model for generating patches (cheap/fast)
            extraction_model: Model for initial extraction (quality)
        """
        self.llm_client = llm_client
        self.max_retries = max_retries
        self.patch_model = patch_model
        self.extraction_model = extraction_model
        self._validation_history: List[ValidationAttempt] = []
        self._total_tokens_saved = 0

    async def extract_with_validation(
        self,
        prompt: str,
        schema: Type[BaseModel],
        context: str = "",
        initial_json: Optional[Dict[str, Any]] = None
    ) -> BaseModel:
        """
        Extract structured data with automatic patch-based error correction.

        Args:
            prompt: Instruction for LLM
            schema: Pydantic model to validate against
            context: Additional context for extraction
            initial_json: Optional pre-generated JSON to validate

        Returns:
            Validated Pydantic model instance

        Raises:
            ValidationError: If validation fails after max_retries
        """
        self._validation_history = []

        # Step 1: Initial extraction (or use provided JSON)
        if initial_json is None:
            logger.info(f"Extracting structured data with {self.extraction_model}")
            current_json = await self._generate_json(prompt, schema, context)
            initial_tokens = self._estimate_tokens(prompt) + self._estimate_tokens(str(current_json))
        else:
            logger.info("Using provided JSON for validation")
            current_json = initial_json
            initial_tokens = self._estimate_tokens(str(initial_json))

        # Step 2: Try to validate
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(f"Validation attempt {attempt + 1}/{self.max_retries + 1}")
                validated = schema(**current_json)

                # Success!
                self._validation_history.append(
                    ValidationAttempt(
                        attempt_number=attempt + 1,
                        success=True,
                        tokens_used=initial_tokens if attempt == 0 else 0
                    )
                )

                logger.info(
                    f"Validation successful on attempt {attempt + 1}. "
                    f"Total attempts: {attempt + 1}"
                )

                return validated

            except ValidationError as e:
                logger.warning(f"Validation failed on attempt {attempt + 1}: {e}")

                if attempt >= self.max_retries:
                    # Max retries exceeded
                    self._validation_history.append(
                        ValidationAttempt(
                            attempt_number=attempt + 1,
                            success=False,
                            error=str(e)
                        )
                    )
                    logger.error(
                        f"Validation failed after {self.max_retries} retries. "
                        f"Final error: {e}"
                    )
                    raise

                # Generate patch to fix the error
                logger.info(f"Generating patch to fix validation error...")
                patch = await self._generate_patch(
                    current_json=current_json,
                    validation_error=e,
                    schema=schema,
                    original_prompt=prompt
                )

                # Calculate token savings
                # Full regeneration would use ~same tokens as initial
                # Patch uses much less
                patch_tokens = self._estimate_tokens(str(patch))
                tokens_saved = initial_tokens - patch_tokens
                self._total_tokens_saved += tokens_saved

                logger.info(
                    f"Patch generated ({patch_tokens} tokens vs {initial_tokens} for full regen, "
                    f"saved {tokens_saved} tokens)"
                )

                # Apply patch
                try:
                    current_json = jsonpatch.apply_patch(current_json, patch)
                    logger.debug(f"Patch applied successfully: {patch}")
                except Exception as patch_error:
                    logger.error(f"Failed to apply patch: {patch_error}")
                    # If patch fails, try full regeneration as fallback
                    logger.info("Falling back to full regeneration")
                    current_json = await self._generate_json(prompt, schema, context)

                self._validation_history.append(
                    ValidationAttempt(
                        attempt_number=attempt + 1,
                        success=False,
                        error=str(e),
                        patch_applied=patch,
                        tokens_used=patch_tokens
                    )
                )

        # Should not reach here due to raise in except block
        raise ValidationError("Validation failed after maximum retries")

    async def _generate_json(
        self,
        prompt: str,
        schema: Type[BaseModel],
        context: str
    ) -> Dict[str, Any]:
        """
        Generate initial JSON from LLM.

        Args:
            prompt: User instruction
            schema: Pydantic schema to match
            context: Additional context

        Returns:
            JSON dictionary
        """
        system_message = f"""Generate valid JSON matching this schema:

{schema.schema_json(indent=2)}

Context:
{context}

IMPORTANT: Output ONLY valid JSON, no explanations or markdown.
Ensure all required fields are present and have correct types."""

        try:
            response = await self.llm_client.acompletion(
                model=self.extraction_model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )

            content = response.choices[0].message.content
            return json.loads(content)

        except Exception as e:
            logger.error(f"JSON generation failed: {e}", exc_info=True)
            raise

    async def _generate_patch(
        self,
        current_json: Dict[str, Any],
        validation_error: ValidationError,
        schema: Type[BaseModel],
        original_prompt: str
    ) -> List[Dict]:
        """
        Generate JSON Patch to fix validation errors.

        This is the core of the Trustcall pattern - instead of regenerating
        the entire object, we generate a minimal patch to fix specific errors.

        Args:
            current_json: Current JSON with errors
            validation_error: Pydantic validation error
            schema: Target schema
            original_prompt: Original user prompt (for context)

        Returns:
            JSON Patch array (list of patch operations)
        """
        # Format error for LLM
        error_details = self._format_validation_error(validation_error)

        system_message = f"""You are a JSON repair expert. Your job is to generate a minimal JSON Patch (RFC 6902) to fix validation errors.

Current JSON (with errors):
{json.dumps(current_json, indent=2)}

Validation Errors:
{error_details}

Target Schema:
{schema.schema_json(indent=2)}

Original Intent:
{original_prompt}

Generate a JSON Patch array to fix ONLY the errors. Use these operations:
- {{"op": "replace", "path": "/field_name", "value": "corrected_value"}}
- {{"op": "add", "path": "/missing_field", "value": "new_value"}}
- {{"op": "remove", "path": "/invalid_field"}}

IMPORTANT:
1. Make minimal changes - don't alter correct fields
2. Use correct JSON types (numbers as numbers, not strings)
3. Follow the path format: "/field" or "/nested/field"
4. Output ONLY the JSON Patch array, no explanations

Example output:
[
  {{"op": "replace", "path": "/status", "value": "active"}},
  {{"op": "add", "path": "/count", "value": 0}}
]"""

        try:
            response = await self.llm_client.acompletion(
                model=self.patch_model,  # Use cheap model for patches
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": "Generate the minimal patch to fix these errors."}
                ],
                response_format={"type": "json_object"},
                temperature=0.3  # Lower temperature for precise corrections
            )

            content = response.choices[0].message.content
            patch_data = json.loads(content)

            # Handle different possible response formats
            if isinstance(patch_data, list):
                patch = patch_data
            elif isinstance(patch_data, dict) and 'patch' in patch_data:
                patch = patch_data['patch']
            elif isinstance(patch_data, dict) and 'operations' in patch_data:
                patch = patch_data['operations']
            else:
                logger.warning(f"Unexpected patch format: {patch_data}")
                # Wrap single operation in array
                patch = [patch_data] if patch_data else []

            return patch

        except Exception as e:
            logger.error(f"Patch generation failed: {e}", exc_info=True)
            # Return empty patch to trigger fallback
            return []

    def _format_validation_error(self, error: ValidationError) -> str:
        """
        Format validation error in human-readable way for LLM.

        Args:
            error: Pydantic ValidationError

        Returns:
            Formatted error string
        """
        formatted_errors = []
        for err in error.errors():
            field = '.'.join(str(loc) for loc in err['loc'])
            error_type = err['type']
            message = err['msg']
            formatted_errors.append(f"- Field '{field}': {error_type} - {message}")

        return '\n'.join(formatted_errors)

    def _estimate_tokens(self, text: str) -> int:
        """
        Rough estimate of token count.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        # Rough estimate: ~4 characters per token
        return len(text) // 4

    def get_validation_history(self) -> List[Dict[str, Any]]:
        """
        Get history of validation attempts.

        Returns:
            List of validation attempt records
        """
        return [
            {
                'attempt': attempt.attempt_number,
                'success': attempt.success,
                'error': attempt.error,
                'patch': attempt.patch_applied,
                'tokens_used': attempt.tokens_used,
                'timestamp': attempt.timestamp.isoformat()
            }
            for attempt in self._validation_history
        ]

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get validation metrics.

        Returns:
            Dictionary with validation statistics
        """
        total_attempts = len(self._validation_history)
        successful = sum(1 for a in self._validation_history if a.success)
        total_tokens = sum(a.tokens_used for a in self._validation_history)

        return {
            'total_attempts': total_attempts,
            'successful_validations': successful,
            'failed_validations': total_attempts - successful,
            'total_tokens_used': total_tokens,
            'total_tokens_saved': self._total_tokens_saved,
            'average_tokens_per_attempt': (
                total_tokens / total_attempts if total_attempts > 0 else 0
            ),
            'success_rate': (
                successful / total_attempts if total_attempts > 0 else 0.0
            )
        }

    def reset_metrics(self):
        """Reset validation metrics."""
        self._validation_history = []
        self._total_tokens_saved = 0


# Convenience functions for common use cases

async def validate_task_decomposition(
    llm_client,
    directive: str,
    context: str,
    task_schema: Type[BaseModel]
) -> BaseModel:
    """
    Validate task decomposition with automatic error correction.

    Convenience function for Supreme Commander integration.

    Args:
        llm_client: LiteLLM client
        directive: User directive to decompose
        context: Project context
        task_schema: Pydantic schema for tasks

    Returns:
        Validated task decomposition
    """
    validator = TrustcallValidator(llm_client)

    prompt = f"""Decompose this directive into tasks:

Directive: {directive}

Break it down into clear, actionable subtasks."""

    return await validator.extract_with_validation(
        prompt=prompt,
        schema=task_schema,
        context=context
    )


async def validate_blueprint_config(
    llm_client,
    blueprint_json: Dict[str, Any],
    blueprint_schema: Type[BaseModel]
) -> BaseModel:
    """
    Validate blueprint configuration with patch-based correction.

    Convenience function for blueprint validation.

    Args:
        llm_client: LiteLLM client
        blueprint_json: Blueprint JSON to validate
        blueprint_schema: Pydantic schema

    Returns:
        Validated blueprint
    """
    validator = TrustcallValidator(llm_client)

    return await validator.extract_with_validation(
        prompt="Validate and correct this blueprint",
        schema=blueprint_schema,
        context="Blueprint configuration",
        initial_json=blueprint_json
    )
