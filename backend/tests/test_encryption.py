# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import pytest
import os
from services.encryption import encryption_service

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
