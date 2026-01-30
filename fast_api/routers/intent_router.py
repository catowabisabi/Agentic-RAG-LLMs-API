"""
Intent Management Router

API endpoints for managing intents dynamically:
- List all intents
- Add new intent
- Reload configuration
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agents.shared_services.intent_router import get_intent_router
from agents.core.entry_classifier import get_entry_classifier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intents", tags=["intents"])


class IntentConfig(BaseModel):
    """Intent configuration for API"""
    description: str = Field(description="Intent description")
    route_to: str = Field(description="Target agent name")
    handler: Optional[str] = Field(default=None, description="Specific handler method")
    patterns: List[str] = Field(default_factory=list, description="Regex patterns to match")
    examples: List[str] = Field(default_factory=list, description="Example queries")


class AddIntentRequest(BaseModel):
    """Request to add a new intent"""
    name: str = Field(description="Intent name (snake_case)")
    config: IntentConfig


@router.get("/list")
async def list_intents():
    """
    List all configured intents
    
    Returns all intents from config/intents.yaml
    """
    router = get_intent_router()
    intents = router.get_all_intents()
    
    return {
        "count": len(intents),
        "intents": {
            name: {
                "description": config.get("description", ""),
                "route_to": config.get("route_to", "manager_agent"),
                "handler": config.get("handler"),
                "patterns_count": len(config.get("patterns", [])),
                "examples": config.get("examples", [])[:3]
            }
            for name, config in intents.items()
        }
    }


@router.post("/add")
async def add_intent(request: AddIntentRequest):
    """
    Add a new intent dynamically
    
    This will:
    1. Add the intent to memory
    2. Save to config/intents.yaml
    3. Take effect immediately (no restart needed)
    
    Example:
    ```json
    {
        "name": "weather",
        "config": {
            "description": "Weather queries",
            "route_to": "manager_agent",
            "handler": "weather_lookup",
            "patterns": ["天氣", "weather", "幾度"],
            "examples": ["今天天氣如何", "What's the weather?"]
        }
    }
    ```
    """
    classifier = get_entry_classifier()
    
    success = classifier.add_intent(request.name, request.config.model_dump())
    
    if success:
        return {
            "success": True,
            "message": f"Intent '{request.name}' added successfully",
            "intent": {
                "name": request.name,
                **request.config.model_dump()
            }
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to add intent")


@router.post("/reload")
async def reload_intents():
    """
    Reload intent configuration from YAML
    
    Use this after manually editing config/intents.yaml
    """
    classifier = get_entry_classifier()
    
    success = classifier.reload_config()
    
    if success:
        router = get_intent_router()
        return {
            "success": True,
            "message": "Intent configuration reloaded",
            "intent_count": len(router.intents)
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to reload configuration")


@router.post("/test")
async def test_classification(message: str, context: str = ""):
    """
    Test intent classification for a message
    
    Returns the classification result without executing
    """
    classifier = get_entry_classifier()
    
    result = await classifier.classify(message, context)
    
    return {
        "message": message,
        "classification": {
            "intent": result.intent,
            "route_to": result.route_to,
            "handler": result.handler,
            "is_casual": result.is_casual,
            "confidence": result.confidence,
            "matched_by": result.matched_by,
            "reason": result.reason
        }
    }
