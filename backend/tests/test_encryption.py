# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import pytest
import os
from services.encryption import EncryptionService, encryption_service

def test_encryption_service_initialization():
    """Test that encryption service initializes correctly."""
    assert encryption_service._fernet is not None

def test_encrypt_decrypt_cycle():
    """Test that data can be encrypted and then decrypted back to original."""
    original_text = "sk-test-1234567890abcdef"
    encrypted = encryption_service.encrypt(original_text)

    assert encrypted != original_text
    assert len(encrypted) > 0

    decrypted = encryption_service.decrypt(encrypted)
    assert decrypted == original_text

def test_decrypt_invalid_data():
    """Test that decrypting invalid data returns the original data (backward compatibility)."""
    invalid_data = "not-encrypted-data"
    # The service logs an error but returns the original data
    result = encryption_service.decrypt(invalid_data)
    assert result == invalid_data

def test_encrypt_empty():
    """Test encrypting empty string or None."""
    assert encryption_service.encrypt("") == ""
    assert encryption_service.encrypt(None) is None

def test_decrypt_empty():
    """Test decrypting empty string or None."""
    assert encryption_service.decrypt("") == ""
    assert encryption_service.decrypt(None) is None

@pytest.fixture
def reset_singleton():
    """Reset the EncryptionService singleton for a test, then restore it."""
    saved_instance = EncryptionService._instance
    saved_fernet = EncryptionService._fernet
    EncryptionService._instance = None
    EncryptionService._fernet = None
    try:
        yield
    finally:
        EncryptionService._instance = saved_instance
        EncryptionService._fernet = saved_fernet

def test_production_rejects_missing_key(monkeypatch, reset_singleton):
    """Production must refuse to initialize when APP_ENCRYPTION_KEY is unset."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("APP_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError, match="APP_ENCRYPTION_KEY must be set to a non-default value in production"):
        EncryptionService()

def test_production_rejects_default_key(monkeypatch, reset_singleton):
    """Production must refuse to initialize when APP_ENCRYPTION_KEY is the known default."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "langconfig-default-insecure-key-change-me")
    with pytest.raises(RuntimeError, match="APP_ENCRYPTION_KEY must be set to a non-default value in production"):
        EncryptionService()

def test_development_warns_on_default_key(monkeypatch, reset_singleton, caplog):
    """Non-production falls back to the default key but logs a prominent warning."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("APP_ENCRYPTION_KEY", raising=False)
    with caplog.at_level("WARNING", logger="services.encryption"):
        service = EncryptionService()
    assert service._fernet is not None
    assert any("insecure default" in record.message.lower() for record in caplog.records)
