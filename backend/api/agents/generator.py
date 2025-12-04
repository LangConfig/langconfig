# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Agent generation API endpoints - AI-powered agent configuration.
"""
from fastapi import APIRouter, HTTPException
from services.agent_generator_service import generate_agent_config, GenerateAgentRequest
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generation", tags=["generation"])


@router.post("/generate")
async def generate_agent(request: GenerateAgentRequest):
    """
    Generate agent configuration using AI.

    Takes user requirements (name, description, agent_type) and returns
    a complete agent configuration with model, temperature, system prompt,
    and recommended tools.

    Args:
        request: Agent generation request

    Returns:
        Generated agent configuration with reasoning
    """
    try:
        logger.info(f"Received generation request for: {request.name} (type: {request.agent_type})")

        # Generate configuration
        generated_config = await generate_agent_config(request)

        logger.info(f"Successfully generated config for: {request.name}")

        return {
            "success": True,
            "config": generated_config,
            "message": "Agent configuration generated successfully"
        }

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during generation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate agent configuration")


@router.get("/health")
async def generation_health_check():
    """
    Health check for agent generation service.

    Returns:
        Service status and availability
    """
    import os

    openai_key_set = bool(os.getenv("OPENAI_API_KEY"))

    return {
        "status": "healthy" if openai_key_set else "degraded",
        "openai_configured": openai_key_set,
        "message": "Agent generation service ready" if openai_key_set else "OPENAI_API_KEY not configured"
    }
