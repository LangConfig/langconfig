# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Encryption Service for Securing Sensitive Data

Handles encryption and decryption of sensitive information like API keys
using Fernet symmetric encryption.
"""
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)

class EncryptionService:
    _instance = None
    _fernet = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EncryptionService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize the encryption key from environment or generate a default."""
        try:
            # Get encryption key from env or use a default (for dev/self-hosted)
            # In production, this should be strictly managed
            key_str = os.getenv("APP_ENCRYPTION_KEY", "langconfig-default-insecure-key-change-me")

            # Derive a secure 32-byte key from the string
            salt = b'langconfig_salt' # Fixed salt for deterministic key generation from the env var
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(key_str.encode()))

            self._fernet = Fernet(key)
            logger.info("Encryption service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize encryption service: {e}")
            raise

    def encrypt(self, data: str) -> str:
        """Encrypt a string value."""
        if not data:
            return data
        try:
            return self._fernet.encrypt(data.encode()).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt an encrypted string value."""
        if not encrypted_data:
            return encrypted_data
        try:
            return self._fernet.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            # Return original data if decryption fails (backward compatibility for unencrypted data)
            return encrypted_data

# Global instance
encryption_service = EncryptionService()
