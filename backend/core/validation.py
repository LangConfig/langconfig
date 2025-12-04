# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Validation Framework

Provides declarative validation for model updates with permission levels,
custom validators, and field whitelisting.

Features:
- Permission-based field access control (PUBLIC, PROTECTED, SYSTEM, IMMUTABLE)
- Custom validation functions
- Value transformation/normalization
- Comprehensive error messages
- Prevents unauthorized field updates

Usage:
    from core.validation import ModelValidator, PermissionLevel

    # Define validator for a model
    workflow_validator = ModelValidator("WorkflowProfile")

    # Register fields with permissions and validators
    workflow_validator.register_field(
        "name",
        permission=PermissionLevel.PUBLIC,
        validator=lambda v: 0 < len(v.strip()) <= 100,
        transform=lambda v: v.strip()
    )

    # Use in endpoint
    @router.patch("/{id}")
    async def update_model(id: int, data: dict, db: Session = Depends(get_db)):
        validated_data = workflow_validator.validate_update(data)
        workflow_validator.apply_update(instance, validated_data)
"""

import logging
from enum import Enum
from typing import Dict, Any, Callable, Optional, List, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# =============================================================================
# Permission Levels
# =============================================================================

class PermissionLevel(str, Enum):
    """
    Field permission levels for model validation.

    Permission hierarchy (most to least permissive):
    PUBLIC -> PROTECTED -> SYSTEM -> IMMUTABLE
    """
    PUBLIC = "public"  # Anyone can modify (e.g., workflow.name)
    PROTECTED = "protected"  # Requires specific permission (future: role-based auth)
    SYSTEM = "system"  # Only backend can modify (e.g., usage_count, timestamps)
    IMMUTABLE = "immutable"  # Cannot be modified after creation (e.g., id, created_at)


# =============================================================================
# Field Configuration
# =============================================================================

@dataclass
class FieldConfig:
    """
    Configuration for a single model field.

    Attributes:
        name: Field name
        permission: Permission level required to modify
        validator: Optional validation function (value) -> bool
        transform: Optional transformation function (value) -> value
        error_message: Custom error message for validation failures
    """
    name: str
    permission: PermissionLevel
    validator: Optional[Callable[[Any], bool]] = None
    transform: Optional[Callable[[Any], Any]] = None
    error_message: Optional[str] = None


# =============================================================================
# Validation Errors
# =============================================================================

class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, field: str, message: str, details: Optional[Dict] = None):
        """
        Initialize validation error.

        Args:
            field: Field name that failed validation
            message: Error message
            details: Additional error details
        """
        self.field = field
        self.message = message
        self.details = details or {}
        super().__init__(f"Validation failed for field '{field}': {message}")


class PermissionError(Exception):
    """Raised when attempting to modify a field without permission."""

    def __init__(self, field: str, permission: PermissionLevel):
        """
        Initialize permission error.

        Args:
            field: Field name
            permission: Required permission level
        """
        self.field = field
        self.permission = permission
        super().__init__(
            f"Permission denied for field '{field}': "
            f"requires {permission.value} level"
        )


# =============================================================================
# Model Validator
# =============================================================================

class ModelValidator:
    """
    Validates and applies updates to model instances.

    Provides declarative validation with permission checks, custom validators,
    and field whitelisting.
    """

    def __init__(self, model_name: str):
        """
        Initialize model validator.

        Args:
            model_name: Name of the model (for logging)
        """
        self.model_name = model_name
        self._fields: Dict[str, FieldConfig] = {}
        self._public_fields: Set[str] = set()
        self._protected_fields: Set[str] = set()
        self._system_fields: Set[str] = set()
        self._immutable_fields: Set[str] = set()

    def register_field(
        self,
        field_name: str,
        permission: PermissionLevel,
        validator: Optional[Callable[[Any], bool]] = None,
        transform: Optional[Callable[[Any], Any]] = None,
        error_message: Optional[str] = None
    ):
        """
        Register a field with its validation configuration.

        Args:
            field_name: Name of the field
            permission: Permission level required to modify
            validator: Optional validation function
            transform: Optional transformation function
            error_message: Custom error message for validation failures

        Example:
            validator.register_field(
                "name",
                permission=PermissionLevel.PUBLIC,
                validator=lambda v: len(v.strip()) > 0,
                transform=lambda v: v.strip(),
                error_message="Name cannot be empty"
            )
        """
        config = FieldConfig(
            name=field_name,
            permission=permission,
            validator=validator,
            transform=transform,
            error_message=error_message
        )

        self._fields[field_name] = config

        # Add to permission-specific sets for quick lookup
        if permission == PermissionLevel.PUBLIC:
            self._public_fields.add(field_name)
        elif permission == PermissionLevel.PROTECTED:
            self._protected_fields.add(field_name)
        elif permission == PermissionLevel.SYSTEM:
            self._system_fields.add(field_name)
        elif permission == PermissionLevel.IMMUTABLE:
            self._immutable_fields.add(field_name)

        logger.debug(
            f"Registered field '{field_name}' for {self.model_name} "
            f"with permission {permission.value}"
        )

    def register_fields(self, fields: Dict[str, Dict[str, Any]]):
        """
        Register multiple fields at once.

        Args:
            fields: Dictionary of field configurations
                    {field_name: {permission, validator, transform, error_message}}

        Example:
            validator.register_fields({
                "name": {
                    "permission": PermissionLevel.PUBLIC,
                    "validator": lambda v: len(v) > 0,
                    "transform": lambda v: v.strip()
                },
                "id": {
                    "permission": PermissionLevel.IMMUTABLE
                }
            })
        """
        for field_name, config in fields.items():
            self.register_field(
                field_name,
                permission=config["permission"],
                validator=config.get("validator"),
                transform=config.get("transform"),
                error_message=config.get("error_message")
            )

    def validate_update(
        self,
        update_data: Dict[str, Any],
        current_permission: PermissionLevel = PermissionLevel.PUBLIC,
        strict: bool = True
    ) -> Dict[str, Any]:
        """
        Validate update data against registered field configurations.

        Args:
            update_data: Dictionary of field updates
            current_permission: Current user's permission level (default: PUBLIC)
            strict: If True, reject unknown fields; if False, filter them out

        Returns:
            Dict[str, Any]: Validated and transformed data

        Raises:
            ValidationError: If validation fails
            PermissionError: If permission check fails

        Example:
            validated = validator.validate_update(
                {"name": "  Updated Name  ", "id": 999},
                current_permission=PermissionLevel.PUBLIC
            )
            # Returns: {"name": "Updated Name"}
            # Rejects: id (immutable)
        """
        validated_data = {}
        rejected_fields = []
        permission_denied = []

        for field_name, value in update_data.items():
            # Check if field is registered
            if field_name not in self._fields:
                if strict:
                    rejected_fields.append(field_name)
                    logger.warning(
                        f"Rejected unknown field '{field_name}' for {self.model_name}"
                    )
                continue

            config = self._fields[field_name]

            # Check permission
            if not self._check_permission(config.permission, current_permission):
                permission_denied.append((field_name, config.permission))
                logger.warning(
                    f"Permission denied for field '{field_name}' "
                    f"(requires {config.permission.value}, "
                    f"current: {current_permission.value})"
                )
                continue

            # Apply transformation if defined
            if config.transform:
                try:
                    value = config.transform(value)
                except Exception as e:
                    raise ValidationError(
                        field_name,
                        f"Transformation failed: {str(e)}",
                        {"original_value": value}
                    )

            # Run validation if defined
            if config.validator:
                try:
                    is_valid = config.validator(value)
                    if not is_valid:
                        error_msg = config.error_message or "Validation failed"
                        raise ValidationError(
                            field_name,
                            error_msg,
                            {"value": value}
                        )
                except ValidationError:
                    raise
                except Exception as e:
                    raise ValidationError(
                        field_name,
                        f"Validator error: {str(e)}",
                        {"value": value}
                    )

            # Field passed all checks
            validated_data[field_name] = value

        # Report rejected fields
        if rejected_fields:
            logger.warning(
                f"Rejected {len(rejected_fields)} unknown fields for {self.model_name}: "
                f"{', '.join(rejected_fields)}"
            )

        # Report permission denials
        if permission_denied:
            denied_list = [f"{field} ({perm.value})" for field, perm in permission_denied]
            logger.warning(
                f"Permission denied for {len(permission_denied)} fields: "
                f"{', '.join(denied_list)}"
            )

        return validated_data

    def apply_update(self, instance: Any, validated_data: Dict[str, Any]):
        """
        Apply validated data to a model instance.

        Args:
            instance: Model instance to update
            validated_data: Validated data from validate_update()

        Example:
            validated_data = validator.validate_update(update_data)
            validator.apply_update(workflow, validated_data)
        """
        for field_name, value in validated_data.items():
            setattr(instance, field_name, value)
            logger.debug(
                f"Updated {self.model_name}.{field_name}",
                extra={"field": field_name, "value_type": type(value).__name__}
            )

        logger.info(
            f"Applied {len(validated_data)} field updates to {self.model_name}",
            extra={"fields_updated": list(validated_data.keys())}
        )

    def _check_permission(
        self,
        required: PermissionLevel,
        current: PermissionLevel
    ) -> bool:
        """
        Check if current permission level satisfies required level.

        Permission hierarchy:
        PUBLIC -> PROTECTED -> SYSTEM -> IMMUTABLE

        Args:
            required: Required permission level
            current: Current user's permission level

        Returns:
            bool: True if permission granted, False otherwise
        """
        # Define permission hierarchy (higher = more permissive)
        hierarchy = {
            PermissionLevel.IMMUTABLE: 0,
            PermissionLevel.SYSTEM: 1,
            PermissionLevel.PROTECTED: 2,
            PermissionLevel.PUBLIC: 3
        }

        # Grant if current permission is >= required
        return hierarchy.get(current, 0) >= hierarchy.get(required, 0)

    def get_public_fields(self) -> Set[str]:
        """Get set of publicly modifiable fields."""
        return self._public_fields.copy()

    def get_protected_fields(self) -> Set[str]:
        """Get set of protected fields."""
        return self._protected_fields.copy()

    def get_system_fields(self) -> Set[str]:
        """Get set of system-only fields."""
        return self._system_fields.copy()

    def get_immutable_fields(self) -> Set[str]:
        """Get set of immutable fields."""
        return self._immutable_fields.copy()

    def get_all_fields(self) -> Set[str]:
        """Get set of all registered fields."""
        return set(self._fields.keys())

    def get_field_info(self, field_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific field.

        Args:
            field_name: Name of the field

        Returns:
            Dict with field configuration or None if not found
        """
        if field_name not in self._fields:
            return None

        config = self._fields[field_name]
        return {
            "name": config.name,
            "permission": config.permission.value,
            "has_validator": config.validator is not None,
            "has_transform": config.transform is not None,
            "error_message": config.error_message
        }


# =============================================================================
# Global Validator Registry
# =============================================================================

class ValidatorRegistry:
    """
    Global registry for model validators.

    Allows centralized management of all validators.
    """

    def __init__(self):
        """Initialize validator registry."""
        self._validators: Dict[str, ModelValidator] = {}

    def register(self, model_name: str, validator: ModelValidator):
        """
        Register a validator for a model.

        Args:
            model_name: Name of the model
            validator: ModelValidator instance
        """
        self._validators[model_name] = validator
        logger.info(f"Registered validator for {model_name}")

    def get(self, model_name: str) -> Optional[ModelValidator]:
        """
        Get validator for a model.

        Args:
            model_name: Name of the model

        Returns:
            ModelValidator instance or None if not found
        """
        return self._validators.get(model_name)

    def list_models(self) -> List[str]:
        """Get list of models with registered validators."""
        return list(self._validators.keys())


# Global registry instance
registry = ValidatorRegistry()


def get_validator(model_name: str) -> ModelValidator:
    """
    Get or create validator for a model.

    Args:
        model_name: Name of the model

    Returns:
        ModelValidator instance
    """
    validator = registry.get(model_name)
    if validator is None:
        validator = ModelValidator(model_name)
        registry.register(model_name, validator)

    return validator
