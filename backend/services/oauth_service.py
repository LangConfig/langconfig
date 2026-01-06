# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Google OAuth Service

Handles OAuth 2.0 authentication flow for Google APIs (Slides, Drive).
Tokens are encrypted at rest using the EncryptionService.
"""
import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleAuthRequest
from sqlalchemy.orm import Session

from models.oauth_token import OAuthToken
from services.encryption import encryption_service

logger = logging.getLogger(__name__)


class GoogleOAuthService:
    """
    Manages Google OAuth 2.0 authentication for Google Slides and Drive APIs.
    """

    # OAuth scopes required for presentation generation
    SCOPES = [
        'https://www.googleapis.com/auth/presentations',  # Create/edit Google Slides
        'https://www.googleapis.com/auth/drive.file',     # Access files created by the app
    ]

    PROVIDER = 'google'

    def __init__(self):
        """Initialize the OAuth service with credentials from environment."""
        self.client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        self.redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:8765/api/auth/google/callback')

        if not self.client_id or not self.client_secret:
            logger.warning("Google OAuth credentials not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")

    def is_configured(self) -> bool:
        """Check if OAuth is properly configured."""
        return bool(self.client_id and self.client_secret)

    def get_authorization_url(self) -> Dict[str, str]:
        """
        Generate the OAuth authorization URL for the popup flow.

        Returns:
            Dict with 'authorization_url' and 'state' for CSRF protection
        """
        if not self.is_configured():
            raise ValueError("Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables.")

        # Create flow from client config
        client_config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri]
            }
        }

        flow = Flow.from_client_config(
            client_config,
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri
        )

        authorization_url, state = flow.authorization_url(
            access_type='offline',  # Request refresh token
            include_granted_scopes='true',
            prompt='consent'  # Always show consent screen for refresh token
        )

        return {
            'authorization_url': authorization_url,
            'state': state
        }

    async def exchange_code_for_tokens(
        self,
        code: str,
        db: Session
    ) -> OAuthToken:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            code: The authorization code from OAuth callback
            db: Database session

        Returns:
            The created/updated OAuthToken record
        """
        if not self.is_configured():
            raise ValueError("Google OAuth not configured")

        client_config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri]
            }
        }

        flow = Flow.from_client_config(
            client_config,
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri
        )

        # Exchange code for tokens
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Calculate expiration time
        expires_at = None
        if credentials.expiry:
            expires_at = credentials.expiry.replace(tzinfo=timezone.utc)

        # Encrypt tokens before storage
        encrypted_access_token = encryption_service.encrypt(credentials.token)
        encrypted_refresh_token = None
        if credentials.refresh_token:
            encrypted_refresh_token = encryption_service.encrypt(credentials.refresh_token)

        # Check if token already exists for this provider
        existing_token = db.query(OAuthToken).filter(
            OAuthToken.provider == self.PROVIDER
        ).first()

        if existing_token:
            # Update existing token
            existing_token.access_token = encrypted_access_token
            existing_token.refresh_token = encrypted_refresh_token or existing_token.refresh_token
            existing_token.expires_at = expires_at
            existing_token.scope = ' '.join(self.SCOPES)
            existing_token.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing_token)
            return existing_token
        else:
            # Create new token
            new_token = OAuthToken(
                provider=self.PROVIDER,
                access_token=encrypted_access_token,
                refresh_token=encrypted_refresh_token,
                token_type='Bearer',
                expires_at=expires_at,
                scope=' '.join(self.SCOPES)
            )
            db.add(new_token)
            db.commit()
            db.refresh(new_token)
            return new_token

    async def refresh_access_token(self, db: Session) -> Optional[str]:
        """
        Refresh the access token using the stored refresh token.

        Args:
            db: Database session

        Returns:
            The new access token, or None if refresh failed
        """
        token = db.query(OAuthToken).filter(
            OAuthToken.provider == self.PROVIDER
        ).first()

        if not token or not token.refresh_token:
            logger.warning("No refresh token available for Google OAuth")
            return None

        try:
            # Decrypt tokens
            decrypted_refresh_token = encryption_service.decrypt(token.refresh_token)

            # Create credentials for refresh
            credentials = Credentials(
                token=None,
                refresh_token=decrypted_refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            # Refresh the token
            credentials.refresh(GoogleAuthRequest())

            # Update stored token
            token.access_token = encryption_service.encrypt(credentials.token)
            if credentials.expiry:
                token.expires_at = credentials.expiry.replace(tzinfo=timezone.utc)
            token.updated_at = datetime.now(timezone.utc)

            db.commit()
            db.refresh(token)

            return credentials.token

        except Exception as e:
            logger.error(f"Failed to refresh Google access token: {e}")
            return None

    async def get_valid_credentials(self, db: Session) -> Optional[Credentials]:
        """
        Get valid Google API credentials, refreshing if needed.

        Args:
            db: Database session

        Returns:
            Valid Credentials object, or None if not authenticated
        """
        token = db.query(OAuthToken).filter(
            OAuthToken.provider == self.PROVIDER
        ).first()

        if not token:
            logger.debug("No Google OAuth token found")
            return None

        # Decrypt tokens
        decrypted_access_token = encryption_service.decrypt(token.access_token)
        decrypted_refresh_token = None
        if token.refresh_token:
            decrypted_refresh_token = encryption_service.decrypt(token.refresh_token)

        # Create credentials
        # Note: Google's Credentials.expired uses datetime.utcnow() (naive),
        # so we need to pass expiry as naive UTC to avoid comparison errors
        expiry_naive = None
        if token.expires_at:
            # Convert timezone-aware to naive UTC for google-auth compatibility
            if token.expires_at.tzinfo is not None:
                expiry_naive = token.expires_at.replace(tzinfo=None)
            else:
                expiry_naive = token.expires_at

        credentials = Credentials(
            token=decrypted_access_token,
            refresh_token=decrypted_refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=self.client_id,
            client_secret=self.client_secret,
            expiry=expiry_naive
        )

        # Check if token needs refresh
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(GoogleAuthRequest())

                # Update stored token
                token.access_token = encryption_service.encrypt(credentials.token)
                if credentials.expiry:
                    token.expires_at = credentials.expiry.replace(tzinfo=timezone.utc)
                token.updated_at = datetime.now(timezone.utc)

                db.commit()
                logger.info("Google access token refreshed successfully")

            except Exception as e:
                logger.error(f"Failed to refresh credentials: {e}")
                return None

        return credentials

    async def get_connection_status(self, db: Session) -> Dict[str, Any]:
        """
        Get the current Google OAuth connection status.

        Args:
            db: Database session

        Returns:
            Dict with connection status information
        """
        token = db.query(OAuthToken).filter(
            OAuthToken.provider == self.PROVIDER
        ).first()

        if not token:
            return {
                'connected': False,
                'provider': self.PROVIDER,
                'configured': self.is_configured()
            }

        # Check if token is expired
        is_expired = token.is_expired()

        # Check if we can refresh
        can_refresh = bool(token.refresh_token)

        return {
            'connected': True,
            'provider': self.PROVIDER,
            'configured': self.is_configured(),
            'expires_at': token.expires_at.isoformat() if token.expires_at else None,
            'is_expired': is_expired,
            'can_refresh': can_refresh,
            'scope': token.scope,
            'created_at': token.created_at.isoformat() if token.created_at else None
        }

    async def revoke_tokens(self, db: Session) -> bool:
        """
        Revoke and delete stored OAuth tokens.

        Args:
            db: Database session

        Returns:
            True if tokens were revoked, False otherwise
        """
        token = db.query(OAuthToken).filter(
            OAuthToken.provider == self.PROVIDER
        ).first()

        if not token:
            return False

        try:
            # Optionally revoke the token with Google
            # This is best-effort - we delete local token regardless
            import httpx
            decrypted_access_token = encryption_service.decrypt(token.access_token)

            async with httpx.AsyncClient() as client:
                await client.post(
                    'https://oauth2.googleapis.com/revoke',
                    params={'token': decrypted_access_token}
                )
        except Exception as e:
            logger.warning(f"Failed to revoke token with Google (continuing anyway): {e}")

        # Delete local token
        db.delete(token)
        db.commit()

        logger.info("Google OAuth tokens revoked and deleted")
        return True


# Global instance
google_oauth_service = GoogleOAuthService()
