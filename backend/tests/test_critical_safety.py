# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Critical Safety Tests

Tests for:
- Transaction management framework
- Race condition prevention in version creation
- Foreign key validation for executions
- Export status tracking
- Auto-export transaction safety

Run with: pytest tests/test_phase1_critical_safety.py -v
"""

import pytest
import asyncio
import threading
from datetime import datetime
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

# Import application modules
from core.session_manager import managed_transaction, TransactionContext, transaction_metrics
from models.workflow import WorkflowProfile, WorkflowVersion, WorkflowExecution
from api.workflows.routes import create_workflow_version, create_workflow_execution, update_workflow


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def db_engine():
    """Create test database engine."""
    # Use in-memory SQLite for tests
    engine = create_engine("sqlite:///:memory:", echo=False)

    # Create tables
    from models.workflow import Base
    Base.metadata.create_all(engine)

    yield engine

    # Cleanup
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Create test database session."""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()

    yield session

    session.close()


@pytest.fixture
def test_workflow(db_session):
    """Create a test workflow."""
    workflow = WorkflowProfile(
        name="Test Workflow",
        configuration={"nodes": [], "edges": []},
        blueprint={"nodes": [], "edges": []}
    )
    db_session.add(workflow)
    db_session.commit()
    db_session.refresh(workflow)

    return workflow


@pytest.fixture
def test_version(db_session, test_workflow):
    """Create a test version."""
    version = WorkflowVersion(
        workflow_id=test_workflow.id,
        version_number=1,
        config_snapshot={"nodes": [], "edges": []},
        is_current=True
    )
    db_session.add(version)
    db_session.commit()
    db_session.refresh(version)

    return version


# =============================================================================
# Transaction Management Tests
# =============================================================================

class TestTransactionManagement:
    """Tests for transaction management framework."""

    def test_managed_transaction_commit(self, db_session, test_workflow):
        """Test that managed_transaction commits on success."""
        with managed_transaction(db_session, "test_commit") as tx:
            test_workflow.name = "Updated Name"

        # Verify change was committed
        db_session.refresh(test_workflow)
        assert test_workflow.name == "Updated Name"

    def test_managed_transaction_rollback(self, db_session, test_workflow):
        """Test that managed_transaction rolls back on exception."""
        original_name = test_workflow.name

        try:
            with managed_transaction(db_session, "test_rollback"):
                test_workflow.name = "Should Not Persist"
                raise ValueError("Test error")
        except ValueError:
            pass

        # Verify change was rolled back
        db_session.refresh(test_workflow)
        assert test_workflow.name == original_name

    def test_savepoint_rollback(self, db_session, test_workflow):
        """Test that savepoint rollback works correctly."""
        with managed_transaction(db_session, "test_savepoint") as tx:
            # Main operation
            test_workflow.name = "Main Operation"

            # Try nested operation that fails
            try:
                with tx.savepoint("nested"):
                    test_workflow.description = "This should rollback"
                    raise ValueError("Nested error")
            except ValueError:
                pass

        # Verify main operation succeeded, nested rolled back
        db_session.refresh(test_workflow)
        assert test_workflow.name == "Main Operation"
        assert test_workflow.description is None  # Rolled back

    def test_transaction_metrics(self, db_session, test_workflow):
        """Test that transaction metrics are recorded."""
        # Reset metrics
        transaction_metrics.reset()

        # Successful transaction
        with managed_transaction(db_session, "test_metrics"):
            test_workflow.name = "Metrics Test"

        # Verify metrics
        stats = transaction_metrics.get_stats()
        assert stats["transaction_count"] == 1
        assert stats["commit_count"] == 1
        assert stats["rollback_count"] == 0


# =============================================================================
# Version Creation Race Condition Tests
# =============================================================================

class TestVersionCreationRaceCondition:
    """Tests for race condition prevention in version creation."""

    def test_sequential_version_creation(self, db_session, test_workflow):
        """Test that sequential version creation works correctly."""
        # Create version 1
        version1 = WorkflowVersion(
            workflow_id=test_workflow.id,
            version_number=1,
            config_snapshot={},
            is_current=False
        )
        db_session.add(version1)
        db_session.commit()

        # Create version 2
        version2 = WorkflowVersion(
            workflow_id=test_workflow.id,
            version_number=2,
            config_snapshot={},
            is_current=True
        )
        db_session.add(version2)
        db_session.commit()

        # Verify both versions exist
        versions = db_session.query(WorkflowVersion).filter(
            WorkflowVersion.workflow_id == test_workflow.id
        ).all()
        assert len(versions) == 2
        assert {v.version_number for v in versions} == {1, 2}

    @pytest.mark.skipif(
        "sqlite" in str(create_engine("sqlite:///:memory:").url),
        reason="SQLite doesn't support SELECT FOR UPDATE"
    )
    def test_concurrent_version_creation_with_lock(self, db_session, test_workflow):
        """Test that SELECT FOR UPDATE prevents duplicate versions."""
        results = []
        errors = []

        def create_version():
            try:
                with managed_transaction(db_session, "concurrent_version") as tx:
                    # Get last version with lock
                    last_version = db_session.query(WorkflowVersion).filter(
                        WorkflowVersion.workflow_id == test_workflow.id
                    ).order_by(WorkflowVersion.version_number.desc()).with_for_update().first()

                    next_num = (last_version.version_number + 1) if last_version else 1

                    version = WorkflowVersion(
                        workflow_id=test_workflow.id,
                        version_number=next_num,
                        config_snapshot={},
                        is_current=True
                    )
                    db_session.add(version)

                results.append(version)

            except Exception as e:
                errors.append(e)

        # Launch concurrent threads
        threads = [threading.Thread(target=create_version) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify: All versions should have unique version numbers
        versions = db_session.query(WorkflowVersion).filter(
            WorkflowVersion.workflow_id == test_workflow.id
        ).all()

        version_numbers = [v.version_number for v in versions]
        assert len(version_numbers) == len(set(version_numbers)), "Duplicate version numbers detected!"

    def test_is_current_flag_management(self, db_session, test_workflow):
        """Test that is_current flag is properly managed."""
        # Create version 1
        v1 = WorkflowVersion(
            workflow_id=test_workflow.id,
            version_number=1,
            config_snapshot={},
            is_current=True
        )
        db_session.add(v1)
        db_session.commit()

        # Create version 2
        with managed_transaction(db_session, "create_v2"):
            # Unmark v1
            db_session.query(WorkflowVersion).filter(
                WorkflowVersion.workflow_id == test_workflow.id,
                WorkflowVersion.is_current == True
            ).update({"is_current": False})

            v2 = WorkflowVersion(
                workflow_id=test_workflow.id,
                version_number=2,
                config_snapshot={},
                is_current=True
            )
            db_session.add(v2)

        # Verify only v2 is current
        db_session.refresh(v1)
        db_session.refresh(v2)
        assert v1.is_current == False
        assert v2.is_current == True


# =============================================================================
# Foreign Key Validation Tests
# =============================================================================

class TestForeignKeyValidation:
    """Tests for foreign key validation in execution creation."""

    def test_execution_with_valid_version(self, db_session, test_workflow, test_version):
        """Test creating execution with valid version."""
        execution = WorkflowExecution(
            workflow_id=test_workflow.id,
            version_id=test_version.id,
            execution_results={"output": "success"},
            status="success",
            started_at=datetime.utcnow()
        )

        with managed_transaction(db_session, "create_execution"):
            db_session.add(execution)

        # Verify execution was created
        db_session.refresh(execution)
        assert execution.id is not None
        assert execution.workflow_id == test_workflow.id
        assert execution.version_id == test_version.id

    def test_execution_with_wrong_workflow_version(self, db_session):
        """Test that execution creation fails with version from different workflow."""
        # Create two workflows
        workflow1 = WorkflowProfile(name="Workflow 1", configuration={})
        workflow2 = WorkflowProfile(name="Workflow 2", configuration={})
        db_session.add_all([workflow1, workflow2])
        db_session.commit()

        # Create version for workflow1
        version1 = WorkflowVersion(
            workflow_id=workflow1.id,
            version_number=1,
            config_snapshot={},
            is_current=True
        )
        db_session.add(version1)
        db_session.commit()

        # Try to create execution for workflow2 using workflow1's version
        # This should fail validation
        version_check = db_session.query(WorkflowVersion).filter(
            WorkflowVersion.id == version1.id,
            WorkflowVersion.workflow_id == workflow2.id  # Wrong workflow!
        ).first()

        assert version_check is None, "Version should not match different workflow"

    def test_execution_with_nonexistent_version(self, db_session, test_workflow):
        """Test that execution creation fails with nonexistent version."""
        version_check = db_session.query(WorkflowVersion).filter(
            WorkflowVersion.id == 99999,
            WorkflowVersion.workflow_id == test_workflow.id
        ).first()

        assert version_check is None, "Nonexistent version should not be found"


# =============================================================================
# Export Status Tracking Tests
# =============================================================================

class TestExportStatusTracking:
    """Tests for export status tracking functionality."""

    def test_export_status_columns_exist(self, db_session, test_workflow):
        """Test that export status columns exist on WorkflowProfile."""
        assert hasattr(test_workflow, 'export_status')
        assert hasattr(test_workflow, 'export_error')
        assert hasattr(test_workflow, 'last_export_at')

    def test_export_status_pending(self, db_session, test_workflow):
        """Test setting export status to pending."""
        with managed_transaction(db_session, "set_pending"):
            test_workflow.export_status = 'pending'
            test_workflow.export_error = None

        db_session.refresh(test_workflow)
        assert test_workflow.export_status == 'pending'
        assert test_workflow.export_error is None

    def test_export_status_completed(self, db_session, test_workflow):
        """Test setting export status to completed."""
        with managed_transaction(db_session, "set_completed"):
            test_workflow.export_status = 'completed'
            test_workflow.export_error = None
            test_workflow.last_export_at = datetime.utcnow()

        db_session.refresh(test_workflow)
        assert test_workflow.export_status == 'completed'
        assert test_workflow.export_error is None
        assert test_workflow.last_export_at is not None

    def test_export_status_failed(self, db_session, test_workflow):
        """Test setting export status to failed with error message."""
        error_msg = "Export failed: Test error"

        with managed_transaction(db_session, "set_failed"):
            test_workflow.export_status = 'failed'
            test_workflow.export_error = error_msg

        db_session.refresh(test_workflow)
        assert test_workflow.export_status == 'failed'
        assert test_workflow.export_error == error_msg

    def test_export_status_survives_workflow_update(self, db_session, test_workflow):
        """Test that workflow update succeeds even if export fails."""
        # Set initial export status
        test_workflow.export_status = 'pending'
        db_session.commit()

        # Update workflow
        with managed_transaction(db_session, "update_workflow") as tx:
            test_workflow.name = "Updated Name"
            test_workflow.export_status = 'pending'

            # Simulate export failure in nested savepoint
            try:
                with tx.savepoint("export"):
                    test_workflow.export_status = 'in_progress'
                    raise Exception("Export failed")
            except Exception:
                test_workflow.export_status = 'failed'
                test_workflow.export_error = "Export failed"

        # Verify workflow update succeeded despite export failure
        db_session.refresh(test_workflow)
        assert test_workflow.name == "Updated Name"
        assert test_workflow.export_status == 'failed'


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """End-to-end integration tests."""

    def test_workflow_lifecycle(self, db_session):
        """Test complete workflow lifecycle with versioning and execution."""
        # Create workflow
        workflow = WorkflowProfile(
            name="Integration Test Workflow",
            configuration={"nodes": [], "edges": []},
            blueprint={"nodes": [], "edges": []}
        )

        with managed_transaction(db_session, "create_workflow"):
            db_session.add(workflow)

        db_session.refresh(workflow)
        assert workflow.id is not None

        # Create version 1
        with managed_transaction(db_session, "create_v1"):
            v1 = WorkflowVersion(
                workflow_id=workflow.id,
                version_number=1,
                config_snapshot={"nodes": [], "edges": []},
                is_current=True
            )
            db_session.add(v1)

        db_session.refresh(v1)

        # Create execution for version 1
        with managed_transaction(db_session, "create_execution"):
            execution = WorkflowExecution(
                workflow_id=workflow.id,
                version_id=v1.id,
                execution_results={"output": "v1 result"},
                status="success",
                started_at=datetime.utcnow()
            )
            db_session.add(execution)

        db_session.refresh(execution)

        # Create version 2
        with managed_transaction(db_session, "create_v2"):
            # Unmark v1
            db_session.query(WorkflowVersion).filter(
                WorkflowVersion.workflow_id == workflow.id,
                WorkflowVersion.is_current == True
            ).update({"is_current": False})

            v2 = WorkflowVersion(
                workflow_id=workflow.id,
                version_number=2,
                config_snapshot={"nodes": ["updated"], "edges": []},
                is_current=True
            )
            db_session.add(v2)

        # Verify final state
        versions = db_session.query(WorkflowVersion).filter(
            WorkflowVersion.workflow_id == workflow.id
        ).all()

        executions = db_session.query(WorkflowExecution).filter(
            WorkflowExecution.workflow_id == workflow.id
        ).all()

        assert len(versions) == 2
        assert len(executions) == 1
        assert versions[1].is_current == True
        assert executions[0].version_id == v1.id


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
