# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
OAuth Token Database Model

Stores OAuth tokens securely for third-party integrations like Google Slides.
Tokens are encrypted at the application level using the EncryptionService.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from db.database import Base
from datetime import datetime, timezone


def _utc_now():
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class OAuthToken(Base):
    """
    Stores OAuth credentials for external services.
    This is a single-user app, so there's one token per provider.
    """
    __tablename__ = 'oauth_tokens'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Provider identification (e.g., 'google', 'microsoft')
    provider = Column(String(50), nullable=False, unique=True, index=True)

    # Token data (encrypted at application level before storage)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_type = Column(String(50), default='Bearer')

    # Token metadata
    expires_at = Column(DateTime(timezone=True), nullable=True)
    scope = Column(Text, nullable=True)  # Space-separated scopes

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=_utc_now)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    def is_expired(self) -> bool:
        """Check if the access token has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) >= self.expires_at

    def __repr__(self):
        return f"<OAuthToken(id={self.id}, provider='{self.provider}', expires_at={self.expires_at})>"
