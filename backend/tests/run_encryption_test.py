# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.services.encryption import encryption_service

def test_encryption_service_initialization():
    """Test that encryption service initializes correctly."""
    print("Testing initialization...", end=" ")
    if encryption_service._fernet is not None:
        print("PASS")
    else:
        print("FAIL")
        sys.exit(1)

def test_encrypt_decrypt_cycle():
    """Test that data can be encrypted and then decrypted back to original."""
    print("Testing encrypt/decrypt cycle...", end=" ")
    original_text = "sk-test-1234567890abcdef"
    encrypted = encryption_service.encrypt(original_text)

    if encrypted == original_text:
        print("FAIL (Data not encrypted)")
        sys.exit(1)

    if len(encrypted) == 0:
        print("FAIL (Empty encryption)")
        sys.exit(1)

    decrypted = encryption_service.decrypt(encrypted)
    if decrypted == original_text:
        print("PASS")
    else:
        print(f"FAIL (Decrypted '{decrypted}' != Original '{original_text}')")
        sys.exit(1)

def test_decrypt_invalid_data():
    """Test that decrypting invalid data returns the original data (backward compatibility)."""
    print("Testing invalid data decryption...", end=" ")
    invalid_data = "not-encrypted-data"
    # The service logs an error but returns the original data
    result = encryption_service.decrypt(invalid_data)
    if result == invalid_data:
        print("PASS")
    else:
        print(f"FAIL (Result '{result}' != Original '{invalid_data}')")
        sys.exit(1)

def test_encrypt_empty():
    """Test encrypting empty string or None."""
    print("Testing empty input...", end=" ")
    if encryption_service.encrypt("") == "" and encryption_service.encrypt(None) is None:
        print("PASS")
    else:
        print("FAIL")
        sys.exit(1)

def test_decrypt_empty():
    """Test decrypting empty string or None."""
    print("Testing empty decryption...", end=" ")
    if encryption_service.decrypt("") == "" and encryption_service.decrypt(None) is None:
        print("PASS")
    else:
        print("FAIL")
        sys.exit(1)

if __name__ == "__main__":
    print("Running Encryption Service Tests")
    print("================================")
    test_encryption_service_initialization()
    test_encrypt_decrypt_cycle()
    test_decrypt_invalid_data()
    test_encrypt_empty()
    test_decrypt_empty()
    print("================================")
    print("All tests passed!")
