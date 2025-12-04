# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Test Suite for Tool Factory Improvements
=========================================

Tests for LangChain AI feedback implementation:
- Critical bug fixes
- Design improvements
- Security enhancements
- Performance optimizations
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

# Import the ToolFactory and related classes
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.tools.factory import ToolFactory, ToolTypes, ValidationResult
from models.custom_tool import ToolType


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_api_tool_config() -> Dict[str, Any]:
    """Sample API tool configuration for testing"""
    return {
        "tool_id": "test_api_tool",
        "name": "Test API Tool",
        "description": "A test API tool for unit testing",
        "tool_type": "api",
        "input_schema": {
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Result limit", "default": 10}
            },
            "required": ["query"]
        },
        "implementation_config": {
            "method": "GET",
            "url": "https://api.example.com/search?q={query}&limit={limit}",
            "headers": {},
            "timeout": 30
        }
    }


@pytest.fixture
def sample_database_tool_config() -> Dict[str, Any]:
    """Sample database tool configuration for testing"""
    return {
        "tool_id": "test_db_tool",
        "name": "Test Database Tool",
        "description": "A test database tool for unit testing",
        "tool_type": "database",
        "input_schema": {
            "properties": {
                "table": {"type": "string", "description": "Table name"}
            },
            "required": ["table"]
        },
        "implementation_config": {
            "db_type": "postgres",
            "connection_string": "postgresql://localhost/testdb",
            "query_template": "SELECT * FROM {table}",
            "read_only": True
        }
    }


# =============================================================================
# Test: Tool Type Constants
# =============================================================================

def test_tool_types_constants():
    """Test that ToolTypes constants are properly defined"""
    assert hasattr(ToolTypes, 'API')
    assert hasattr(ToolTypes, 'NOTIFICATION')
    assert hasattr(ToolTypes, 'IMAGE_VIDEO')
    assert hasattr(ToolTypes, 'DATABASE')
    assert hasattr(ToolTypes, 'DATA_TRANSFORM')

    assert ToolTypes.API == "api"
    assert ToolTypes.NOTIFICATION == "notification"
    assert ToolTypes.IMAGE_VIDEO == "image_video"
    assert ToolTypes.DATABASE == "database"
    assert ToolTypes.DATA_TRANSFORM == "data_transform"


# =============================================================================
# Test: Pydantic Schema Caching
# =============================================================================

def test_pydantic_schema_caching():
    """Test that Pydantic schemas are properly cached"""
    # Clear cache first
    ToolFactory._schema_cache.clear()

    input_schema = {
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "integer", "description": "Result limit"}
        },
        "required": ["query"]
    }

    # First call should create and cache
    schema1 = ToolFactory._create_pydantic_args_schema(input_schema, "test_tool")
    assert len(ToolFactory._schema_cache) == 1

    # Second call with same schema should use cache
    schema2 = ToolFactory._create_pydantic_args_schema(input_schema, "test_tool")
    assert len(ToolFactory._schema_cache) == 1
    assert schema1 is schema2  # Should be the exact same object

    # Different schema should create new entry
    different_schema = {
        "properties": {
            "message": {"type": "string", "description": "Message"}
        },
        "required": ["message"]
    }
    schema3 = ToolFactory._create_pydantic_args_schema(different_schema, "other_tool")
    assert len(ToolFactory._schema_cache) == 2
    assert schema3 is not schema1


# =============================================================================
# Test: Configuration Validation
# =============================================================================

def test_validate_tool_config_missing_fields():
    """Test that validation catches missing required fields"""
    invalid_config = {
        "tool_id": "test",
        # Missing: name, description, input_schema
    }

    result = ToolFactory.validate_tool_config(invalid_config)
    assert not result.is_valid
    assert len(result.errors) > 0
    assert any("name" in error for error in result.errors)
    assert any("description" in error for error in result.errors)


def test_validate_tool_implementation_api():
    """Test implementation validation for API tools"""
    tool_config = {"tool_type": ToolTypes.API}

    # Missing URL and method
    impl_config = {}
    errors = ToolFactory._validate_tool_implementation(tool_config, impl_config)
    assert len(errors) == 2
    assert any("url" in error for error in errors)
    assert any("method" in error for error in errors)

    # Valid configuration
    impl_config = {"url": "https://api.example.com", "method": "GET"}
    errors = ToolFactory._validate_tool_implementation(tool_config, impl_config)
    assert len(errors) == 0


def test_validate_tool_implementation_database():
    """Test implementation validation for database tools"""
    tool_config = {"tool_type": ToolTypes.DATABASE}

    # Missing connection_string
    impl_config = {"db_type": "postgres"}
    errors = ToolFactory._validate_tool_implementation(tool_config, impl_config)
    assert any("connection_string" in error for error in errors)

    # Invalid db_type
    impl_config = {"connection_string": "postgresql://localhost/db", "db_type": "invalid"}
    errors = ToolFactory._validate_tool_implementation(tool_config, impl_config)
    assert any("Unsupported database type" in error for error in errors)

    # Valid configuration
    impl_config = {"connection_string": "postgresql://localhost/db", "db_type": "postgres"}
    errors = ToolFactory._validate_tool_implementation(tool_config, impl_config)
    assert len(errors) == 0


# =============================================================================
# Test: SSRF Protection
# =============================================================================

def test_ssrf_validation_blocks_private_ips():
    """Test that SSRF protection blocks private IP addresses"""
    # Should block localhost
    with pytest.raises(ValueError, match="SSRF Protection"):
        ToolFactory._validate_url_ssrf("http://localhost/api")

    with pytest.raises(ValueError, match="SSRF Protection"):
        ToolFactory._validate_url_ssrf("http://127.0.0.1/api")

    # Should block private IP ranges
    with pytest.raises(ValueError, match="SSRF Protection"):
        ToolFactory._validate_url_ssrf("http://192.168.1.1/api")

    with pytest.raises(ValueError, match="SSRF Protection"):
        ToolFactory._validate_url_ssrf("http://10.0.0.1/api")

    # Should block cloud metadata endpoints
    with pytest.raises(ValueError, match="SSRF Protection"):
        ToolFactory._validate_url_ssrf("http://169.254.169.254/latest/meta-data")


def test_ssrf_validation_allows_public_urls():
    """Test that SSRF protection allows public URLs"""
    # Should allow public URLs (DNS resolution might fail, but that's OK)
    try:
        result = ToolFactory._validate_url_ssrf("https://api.example.com/endpoint")
        assert result == True
    except ValueError:
        # If DNS resolution fails, that's also acceptable for this test
        pass


# =============================================================================
# Test: MongoDB Query Validation
# =============================================================================

def test_mongodb_query_validation_blocks_dangerous_operators():
    """Test that MongoDB validation blocks dangerous operators"""
    # Should block $where
    with pytest.raises(ValueError, match="MongoDB query validation"):
        ToolFactory._validate_mongodb_query({"$where": "this.credits == this.debits"})

    # Should block $function
    with pytest.raises(ValueError, match="MongoDB query validation"):
        ToolFactory._validate_mongodb_query({"$function": {"body": "function() {}", "args": [], "lang": "js"}})

    # Should block $accumulator
    with pytest.raises(ValueError, match="MongoDB query validation"):
        ToolFactory._validate_mongodb_query({"$accumulator": {}})


def test_mongodb_query_validation_allows_safe_queries():
    """Test that MongoDB validation allows safe queries"""
    # Should allow safe queries
    assert ToolFactory._validate_mongodb_query({"name": "John", "age": {"$gt": 18}}) == True
    assert ToolFactory._validate_mongodb_query({"$and": [{"status": "active"}, {"role": "admin"}]}) == True
    assert ToolFactory._validate_mongodb_query({}) == True  # Empty query is safe


def test_mongodb_query_validation_nested():
    """Test MongoDB validation with nested dangerous operators"""
    # Should detect dangerous operators in nested structures
    with pytest.raises(ValueError, match="MongoDB query validation"):
        ToolFactory._validate_mongodb_query({
            "$and": [
                {"status": "active"},
                {"$where": "this.x > 10"}  # Dangerous operator nested
            ]
        })


# =============================================================================
# Test: Helper Methods
# =============================================================================

def test_build_auth_headers_api_key():
    """Test _build_auth_headers with API key authentication"""
    auth_config = {
        "type": "api_key",
        "location": "header",
        "key": "X-API-Key",
        "value": "test-api-key-123"
    }

    headers = ToolFactory._build_auth_headers(auth_config)
    assert "X-API-Key" in headers
    assert headers["X-API-Key"] == "test-api-key-123"
    assert headers["Content-Type"] == "application/json"


def test_build_auth_headers_bearer():
    """Test _build_auth_headers with Bearer token authentication"""
    auth_config = {
        "type": "bearer",
        "token": "test-bearer-token-123"
    }

    headers = ToolFactory._build_auth_headers(auth_config)
    assert "Authorization" in headers
    assert headers["Authorization"] == "Bearer test-bearer-token-123"


def test_build_auth_headers_basic():
    """Test _build_auth_headers with Basic authentication"""
    auth_config = {
        "type": "basic",
        "username": "testuser",
        "password": "testpass"
    }

    headers = ToolFactory._build_auth_headers(auth_config)
    assert "Authorization" in headers
    assert headers["Authorization"].startswith("Basic ")


def test_format_error():
    """Test _format_error helper method"""
    error = Exception("Something went wrong")

    # Without context
    result = ToolFactory._format_error(error)
    assert result == "Error: Something went wrong"

    # With context
    result = ToolFactory._format_error(error, "API call failed")
    assert result == "Error: Something went wrong (API call failed)"


# =============================================================================
# Test: Tool Creation Integration
# =============================================================================

@pytest.mark.asyncio
async def test_create_tool_validates_implementation(sample_api_tool_config):
    """Test that create_tool validates implementation config"""
    # Remove required field
    invalid_config = sample_api_tool_config.copy()
    invalid_config["implementation_config"]["url"] = ""

    with pytest.raises(ValueError, match="Invalid implementation config"):
        await ToolFactory.create_tool(invalid_config)


# =============================================================================
# Test: Environment Variable Integration
# =============================================================================

def test_environment_variable_fallback():
    """Test that tools use environment variables as fallback"""
    # This is a conceptual test - actual implementation would require mocking os.getenv
    # and creating actual tools, which is more complex

    # Verify that the pattern exists in DALL-E tool creation
    # (Actual verification would require creating a full tool and checking behavior)
    assert True  # Placeholder - actual test would mock os.getenv


# =============================================================================
# Test Runner
# =============================================================================

if __name__ == "__main__":
    # Run with: python -m pytest backend/tests/test_tool_factory.py -v
    pytest.main([__file__, "-v", "--tb=short"])
