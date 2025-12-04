# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
MCP Configuration API - Per-User Credentials

Endpoints for managing MCP server configurations, credentials, and viewing available tools.
All credentials are stored per-user in the database with encryption.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from schemas.mcp_tools import BUILTIN_MCP_SERVERS, MCPServerConfig
from services.mcp_manager import get_mcp_manager
from api.dependencies import get_current_user
from db import get_db
from models.user import User, UserCredentials

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp-config", tags=["mcp-config"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class MCPCredentialInput(BaseModel):
    """Input for setting MCP credentials"""
    server_id: str
    credentials: Dict[str, str] = Field(
        ...,
        description="Key-value pairs for credentials (e.g., {'GITHUB_PERSONAL_ACCESS_TOKEN': 'ghp_...'})"
    )


class MCPServerInfo(BaseModel):
    """Extended MCP server information including tools and credential requirements"""
    server_id: str
    display_name: str
    server_type: str
    enabled: bool
    npm_package: Optional[str]

    # Tool information
    available_tools: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of tools provided by this MCP server"
    )

    # Credential requirements
    requires_credentials: bool = Field(
        default=False,
        description="Whether this MCP requires credentials to function"
    )
    required_env_vars: List[str] = Field(
        default_factory=list,
        description="List of required environment variable names"
    )
    credential_status: str = Field(
        default="not_configured",
        description="Status: 'configured', 'not_configured', 'partial'"
    )

    # Blockchain-specific info
    is_blockchain: bool = False
    blockchain_type: Optional[str] = None


class MCPCredentialStatus(BaseModel):
    """Status of MCP credentials"""
    server_id: str
    is_configured: bool
    configured_credentials: List[str] = Field(
        description="List of credential keys that are set (values not included)"
    )
    missing_credentials: List[str] = Field(
        description="List of required credentials that are missing"
    )


# =============================================================================
# CREDENTIAL STORAGE (Database-backed, Per-User)
# =============================================================================

async def _get_or_create_user_credentials(
    user: User,
    db: AsyncSession
) -> UserCredentials:
    """Get or create UserCredentials for a user"""
    from sqlalchemy import select

    # Query for user credentials explicitly to avoid lazy loading
    result = await db.execute(
        select(UserCredentials).where(UserCredentials.user_id == user.id)
    )
    credentials = result.scalar_one_or_none()

    if credentials:
        return credentials

    # Create new credentials record
    credentials = UserCredentials(user_id=user.id)
    db.add(credentials)
    await db.commit()
    await db.refresh(credentials)
    return credentials


async def _get_user_mcp_credentials(
    user: User,
    db: AsyncSession
) -> Dict[str, Dict[str, str]]:
    """Get all MCP credentials for a user"""
    creds = await _get_or_create_user_credentials(user, db)
    return creds.get_mcp_credentials()


async def _get_server_credentials(
    server_id: str,
    user: User,
    db: AsyncSession
) -> Dict[str, str]:
    """Get credentials for a specific MCP server for a user"""
    creds = await _get_or_create_user_credentials(user, db)
    return creds.get_mcp_server_credentials(server_id)


def _get_required_env_vars(server_config: MCPServerConfig) -> List[str]:
    """Extract required environment variable names from server config"""
    # Get env_vars that are currently empty or need user input
    required = []
    for key, value in server_config.env_vars.items():
        # If value is empty or references an env var that doesn't exist
        if not value or (value.startswith("${") and value.endswith("}")):
            required.append(key)
    return required


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("/servers", response_model=List[MCPServerInfo])
async def list_mcp_servers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all available MCP servers with their tool information and credential status.

    Returns extended information including:
    - Available tools and capabilities
    - Credential requirements
    - Configuration status (per-user)
    - Blockchain-specific metadata
    """
    try:
        mcp_manager = await get_mcp_manager()
        stored_creds = await _get_user_mcp_credentials(current_user, db)

        server_list = []

        for server_id, config in BUILTIN_MCP_SERVERS.items():
            # Get available tools from running server or config
            available_tools = []
            if server_id in mcp_manager.servers:
                server = mcp_manager.servers[server_id]
                if server.is_running:
                    # Get tools from running server
                    tools = await server.list_tools()
                    available_tools = [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "input_schema": tool.inputSchema
                        }
                        for tool in tools
                    ]

            # If no runtime tools, use static capabilities
            if not available_tools and config.capabilities:
                available_tools = [
                    {
                        "name": cap.name,
                        "description": cap.description,
                        "input_schema": cap.input_schema,
                        "category": cap.category
                    }
                    for cap in config.capabilities
                ]

            # Determine credential requirements
            required_env_vars = _get_required_env_vars(config)
            requires_credentials = bool(
                len(required_env_vars) > 0 or
                (config.blockchain_config and config.blockchain_config.requires_credentials)
            )

            # Check credential status
            server_creds = stored_creds.get(server_id, {})
            configured_vars = [k for k in required_env_vars if k in server_creds and server_creds[k]]

            if not requires_credentials:
                cred_status = "not_required"
            elif len(configured_vars) == len(required_env_vars):
                cred_status = "configured"
            elif len(configured_vars) > 0:
                cred_status = "partial"
            else:
                cred_status = "not_configured"

            server_info = MCPServerInfo(
                server_id=server_id,
                display_name=config.display_name,
                server_type=config.server_type.value,
                enabled=config.enabled,
                npm_package=config.npm_package,
                available_tools=available_tools,
                requires_credentials=requires_credentials,
                required_env_vars=required_env_vars,
                credential_status=cred_status,
                is_blockchain=config.blockchain_config.is_blockchain if config.blockchain_config else False,
                blockchain_type=config.blockchain_config.blockchain_type if config.blockchain_config else None
            )

            server_list.append(server_info)

        return server_list

    except Exception as e:
        logger.error(f"Failed to list MCP servers: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve MCP server information: {str(e)}"
        )


@router.get("/servers/{server_id}", response_model=MCPServerInfo)
async def get_mcp_server(
    server_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information about a specific MCP server"""
    if server_id not in BUILTIN_MCP_SERVERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server '{server_id}' not found"
        )

    # Use the list endpoint logic but filter for one server
    servers = await list_mcp_servers(current_user, db)
    for server in servers:
        if server.server_id == server_id:
            return server

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"MCP server '{server_id}' not found"
    )


@router.get("/servers/{server_id}/credentials", response_model=MCPCredentialStatus)
async def get_credential_status(
    server_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get credential status for a specific MCP server for the current user.

    Returns which credentials are configured and which are missing.
    Does NOT return actual credential values (encrypted).
    """
    if server_id not in BUILTIN_MCP_SERVERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server '{server_id}' not found"
        )

    config = BUILTIN_MCP_SERVERS[server_id]
    required_env_vars = _get_required_env_vars(config)

    server_creds = await _get_server_credentials(server_id, current_user, db)

    configured = [k for k in required_env_vars if k in server_creds and server_creds[k]]
    missing = [k for k in required_env_vars if k not in configured]

    return MCPCredentialStatus(
        server_id=server_id,
        is_configured=len(missing) == 0,
        configured_credentials=configured,
        missing_credentials=missing
    )


@router.post("/servers/{server_id}/credentials")
async def set_credentials(
    server_id: str,
    credential_input: MCPCredentialInput,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Set credentials for an MCP server (per-user, encrypted in database).

    Security notes:
    - ✅ Credentials are encrypted with Fernet before storage
    - ✅ Per-user isolation (each user has their own credentials)
    - ✅ Encrypted at rest in PostgreSQL
    """
    if server_id not in BUILTIN_MCP_SERVERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server '{server_id}' not found"
        )

    if credential_input.server_id != server_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="server_id in URL must match server_id in request body"
        )

    # Get or create user credentials
    creds = await _get_or_create_user_credentials(current_user, db)

    # Update MCP credentials for this server
    for key, value in credential_input.credentials.items():
        creds.set_mcp_credential(server_id, key, value)

    # Save to database
    await db.commit()

    # Update MCP manager with new credentials
    try:
        mcp_manager = await get_mcp_manager()

        # Restart the MCP server with new credentials if it's running
        if server_id in mcp_manager.servers:
            config = BUILTIN_MCP_SERVERS[server_id]
            # Get updated credentials and merge with config env_vars
            server_creds = await _get_server_credentials(server_id, current_user, db)
            updated_env_vars = config.env_vars.copy()
            updated_env_vars.update(server_creds)

            # Update the config
            config.env_vars = updated_env_vars

            # Restart server
            await mcp_manager.stop_server(server_id)
            await mcp_manager.start_server(server_id, config)

            logger.info(f"Restarted MCP server '{server_id}' with updated credentials")

    except Exception as e:
        logger.error(f"Failed to restart MCP server after credential update: {e}")
        # Don't fail the request - credentials were saved successfully

    return {
        "success": True,
        "message": f"Credentials updated for MCP server '{server_id}'",
        "server_id": server_id,
        "configured_credentials": list(credential_input.credentials.keys())
    }


@router.delete("/servers/{server_id}/credentials")
async def delete_credentials(
    server_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete all stored credentials for an MCP server (per-user)"""
    if server_id not in BUILTIN_MCP_SERVERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server '{server_id}' not found"
        )

    # Get user credentials and delete this server's credentials
    creds = await _get_or_create_user_credentials(current_user, db)
    all_creds = creds.get_mcp_credentials()

    if server_id in all_creds:
        del all_creds[server_id]
        creds.set_mcp_credentials(all_creds)
        await db.commit()

    return {
        "success": True,
        "message": f"Credentials deleted for MCP server '{server_id}'"
    }


@router.post("/servers/{server_id}/enable")
async def enable_mcp_server(
    server_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Enable an MCP server and start it if credentials are configured (per-user)"""
    if server_id not in BUILTIN_MCP_SERVERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server '{server_id}' not found"
        )

    config = BUILTIN_MCP_SERVERS[server_id]
    config.enabled = True

    # Check if credentials are needed and configured
    required_env_vars = _get_required_env_vars(config)
    if required_env_vars:
        server_creds = await _get_server_credentials(server_id, current_user, db)
        missing = [k for k in required_env_vars if k not in server_creds or not server_creds[k]]

        if missing:
            return {
                "success": False,
                "message": f"Cannot enable '{server_id}' - missing required credentials: {', '.join(missing)}",
                "missing_credentials": missing
            }

    # Start the server
    try:
        mcp_manager = await get_mcp_manager()

        # Merge stored credentials with config
        server_creds = await _get_server_credentials(server_id, current_user, db)
        config.env_vars.update(server_creds)

        await mcp_manager.start_server(server_id, config)

        return {
            "success": True,
            "message": f"MCP server '{server_id}' enabled and started",
            "server_id": server_id
        }

    except Exception as e:
        logger.error(f"Failed to start MCP server '{server_id}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start MCP server: {str(e)}"
        )


@router.post("/servers/{server_id}/disable")
async def disable_mcp_server(
    server_id: str,
    current_user: Any = Depends(get_current_user)
):
    """Disable and stop an MCP server"""
    if server_id not in BUILTIN_MCP_SERVERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server '{server_id}' not found"
        )

    config = BUILTIN_MCP_SERVERS[server_id]
    config.enabled = False

    try:
        mcp_manager = await get_mcp_manager()
        await mcp_manager.stop_server(server_id)

        return {
            "success": True,
            "message": f"MCP server '{server_id}' disabled and stopped"
        }

    except Exception as e:
        logger.error(f"Failed to stop MCP server '{server_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop MCP server: {str(e)}"
        )
