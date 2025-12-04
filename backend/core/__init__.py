# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Core infrastructure modules for LangConfig backend.

This package contains foundational components used throughout the application:

- session_manager: Transaction management with automatic commit/rollback
- validation: Input validation and field permission framework
- model_validators: Pre-configured validators for all models
- task_queue: Background job processing infrastructure
- errors: Standardized error handling
- versioning: Optimistic locking for concurrent updates
"""

from .session_manager import (
    managed_transaction,
    TransactionContext,
    is_in_transaction,
    get_transaction_isolation_level,
    transaction_isolation,
    transaction_metrics
)

from .validation import (
    ModelValidator,
    PermissionLevel,
    ValidationError,
    PermissionError,
    get_validator,
    registry
)

from .model_validators import (
    workflow_validator,
    deepagent_validator,
    customtool_validator,
    project_validator
)

__all__ = [
    # Transaction management
    "managed_transaction",
    "TransactionContext",
    "is_in_transaction",
    "get_transaction_isolation_level",
    "transaction_isolation",
    "transaction_metrics",
    # Validation framework
    "ModelValidator",
    "PermissionLevel",
    "ValidationError",
    "PermissionError",
    "get_validator",
    "registry",
    # Model validators
    "workflow_validator",
    "deepagent_validator",
    "customtool_validator",
    "project_validator"
]
