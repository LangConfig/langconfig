# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Google OAuth API Endpoints

Handles Google OAuth 2.0 flow for Google Slides and Drive API access.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from db.database import get_db
from services.oauth_service import google_oauth_service

router = APIRouter(prefix="/api/auth/google", tags=["auth"])


class AuthorizationUrlResponse(BaseModel):
    """Response containing the OAuth authorization URL."""
    authorization_url: str
    state: str


class ConnectionStatusResponse(BaseModel):
    """Response containing OAuth connection status."""
    connected: bool
    provider: str
    configured: bool
    expires_at: Optional[str] = None
    is_expired: Optional[bool] = None
    can_refresh: Optional[bool] = None
    scope: Optional[str] = None
    created_at: Optional[str] = None


class TokenExchangeRequest(BaseModel):
    """Request body for token exchange."""
    code: str
    state: Optional[str] = None


class DisconnectResponse(BaseModel):
    """Response for disconnect operation."""
    success: bool
    message: str


@router.get("/authorize", response_model=AuthorizationUrlResponse)
async def get_authorization_url():
    """
    Get the Google OAuth authorization URL for the popup flow.

    Returns the URL that should be opened in a popup window for user consent.
    """
    try:
        result = google_oauth_service.get_authorization_url()
        return AuthorizationUrlResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate authorization URL: {str(e)}")


@router.get("/callback")
async def oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: Optional[str] = Query(None, description="State parameter for CSRF protection"),
    error: Optional[str] = Query(None, description="Error from Google OAuth"),
    db: Session = Depends(get_db)
):
    """
    Handle the OAuth callback from Google.

    This endpoint receives the authorization code after user consent
    and exchanges it for access and refresh tokens.

    Returns an HTML page that posts a message to the opener window.
    """
    if error:
        # Return error page that notifies the opener
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head><title>OAuth Error</title></head>
        <body>
            <script>
                if (window.opener) {{
                    window.opener.postMessage({{
                        type: 'google-oauth-error',
                        error: '{error}'
                    }}, '*');
                    window.close();
                }} else {{
                    document.body.innerHTML = '<h1>OAuth Error</h1><p>{error}</p><p>You can close this window.</p>';
                }}
            </script>
            <noscript>
                <h1>OAuth Error</h1>
                <p>{error}</p>
                <p>Please close this window and try again.</p>
            </noscript>
        </body>
        </html>
        """)

    try:
        # Exchange code for tokens
        token = await google_oauth_service.exchange_code_for_tokens(code, db)

        # Return success page that notifies the opener
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head><title>OAuth Success</title></head>
        <body>
            <script>
                if (window.opener) {
                    window.opener.postMessage({
                        type: 'google-oauth-success',
                        provider: 'google'
                    }, '*');
                    window.close();
                } else {
                    document.body.innerHTML = '<h1>Connected!</h1><p>Google account connected successfully. You can close this window.</p>';
                }
            </script>
            <noscript>
                <h1>Connected!</h1>
                <p>Google account connected successfully. You can close this window.</p>
            </noscript>
        </body>
        </html>
        """)

    except Exception as e:
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head><title>OAuth Error</title></head>
        <body>
            <script>
                if (window.opener) {{
                    window.opener.postMessage({{
                        type: 'google-oauth-error',
                        error: 'Token exchange failed: {str(e).replace("'", "\\'")}'
                    }}, '*');
                    window.close();
                }} else {{
                    document.body.innerHTML = '<h1>OAuth Error</h1><p>Failed to complete authentication.</p><p>You can close this window.</p>';
                }}
            </script>
            <noscript>
                <h1>OAuth Error</h1>
                <p>Failed to complete authentication. Please try again.</p>
            </noscript>
        </body>
        </html>
        """, status_code=200)


@router.post("/callback", response_model=ConnectionStatusResponse)
async def oauth_callback_post(
    request: TokenExchangeRequest,
    db: Session = Depends(get_db)
):
    """
    Alternative callback endpoint for manual code exchange.

    Use this if the popup flow doesn't work well with your setup.
    """
    try:
        await google_oauth_service.exchange_code_for_tokens(request.code, db)
        return await google_oauth_service.get_connection_status(db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {str(e)}")


@router.get("/status", response_model=ConnectionStatusResponse)
async def get_connection_status(db: Session = Depends(get_db)):
    """
    Check if Google OAuth is connected and get status details.

    Returns connection status including expiration and scope information.
    """
    try:
        status = await google_oauth_service.get_connection_status(db)
        return ConnectionStatusResponse(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get connection status: {str(e)}")


@router.delete("/disconnect", response_model=DisconnectResponse)
async def disconnect(db: Session = Depends(get_db)):
    """
    Disconnect the Google OAuth connection.

    Revokes the tokens with Google and deletes them from the database.
    """
    try:
        success = await google_oauth_service.revoke_tokens(db)
        if success:
            return DisconnectResponse(success=True, message="Google account disconnected successfully")
        else:
            return DisconnectResponse(success=False, message="No Google connection found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to disconnect: {str(e)}")


@router.post("/refresh")
async def refresh_token(db: Session = Depends(get_db)):
    """
    Manually refresh the Google access token.

    The token is automatically refreshed when needed, but this endpoint
    allows manual refresh if desired.
    """
    try:
        new_token = await google_oauth_service.refresh_access_token(db)
        if new_token:
            return {"success": True, "message": "Token refreshed successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to refresh token. Re-authentication may be required.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token refresh failed: {str(e)}")
