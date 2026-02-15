"""
Configuration Router
====================

API endpoints for managing system configuration, including API keys.
"""

import logging
import os
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["configuration"])


class UpdateAPIKeyRequest(BaseModel):
    """Request to update API key"""
    provider: str = Field(..., description="Provider name (openai, anthropic, google)")
    api_key: str = Field(..., description="API key value")


class UpdateAPIKeyResponse(BaseModel):
    """Response after updating API key"""
    success: bool
    message: str
    provider: str


@router.post("/api-key", response_model=UpdateAPIKeyResponse)
async def update_api_key(request: UpdateAPIKeyRequest):
    """
    Update API key for a specific provider.
    
    This updates the .env file in the config directory.
    """
    try:
        provider = request.provider.lower()
        api_key = request.api_key.strip()
        
        # Validate provider
        valid_providers = ["openai", "anthropic", "google"]
        if provider not in valid_providers:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid provider. Must be one of: {', '.join(valid_providers)}"
            )
        
        # Map provider to env variable name
        env_var_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY"
        }
        
        env_var_name = env_var_map[provider]
        
        # Update .env file
        config_dir = Path(__file__).parent.parent.parent / "config"
        env_path = config_dir / ".env"
        
        # Create .env if it doesn't exist
        if not env_path.exists():
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.touch()
        
        # Read existing .env content
        env_lines = []
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                env_lines = f.readlines()
        
        # Update or add the API key
        key_found = False
        for i, line in enumerate(env_lines):
            if line.strip().startswith(f"{env_var_name}="):
                env_lines[i] = f"{env_var_name}={api_key}\n"
                key_found = True
                break
        
        if not key_found:
            env_lines.append(f"{env_var_name}={api_key}\n")
        
        # Write back to .env file
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(env_lines)
        
        # Update the current environment variable
        os.environ[env_var_name] = api_key
        
        # Update Config class
        from config.config import Config
        setattr(Config, env_var_name, api_key)
        
        logger.info(f"[ConfigRouter] Updated {env_var_name} successfully")
        
        # Reinitialize LLM service to use new API key
        try:
            from services.llm_service import get_llm_service
            llm_service = get_llm_service(reset=True)
            logger.info(f"[ConfigRouter] LLM service reinitialized with new API key")
        except Exception as e:
            logger.warning(f"[ConfigRouter] Failed to reinitialize LLM service: {e}")
        
        return UpdateAPIKeyResponse(
            success=True,
            message=f"API key for {provider} updated successfully",
            provider=provider
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ConfigRouter] Error updating API key: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update API key: {str(e)}"
        )


@router.get("/api-key-status")
async def get_api_key_status():
    """
    Check which API keys are configured.
    
    Returns a status for each provider without revealing the actual keys.
    """
    from config.config import Config
    
    return {
        "openai": {
            "configured": bool(Config.OPENAI_API_KEY and len(Config.OPENAI_API_KEY) > 0),
            "partial_key": Config.OPENAI_API_KEY[-8:] if Config.OPENAI_API_KEY else None
        },
        "anthropic": {
            "configured": bool(Config.ANTHROPIC_API_KEY and len(Config.ANTHROPIC_API_KEY) > 0),
            "partial_key": Config.ANTHROPIC_API_KEY[-8:] if Config.ANTHROPIC_API_KEY else None
        },
        "google": {
            "configured": bool(Config.GOOGLE_API_KEY and len(Config.GOOGLE_API_KEY) > 0),
            "partial_key": Config.GOOGLE_API_KEY[-8:] if Config.GOOGLE_API_KEY else None
        }
    }
