"""
Memory Router

REST API endpoints for Cerebro memory operations:
- View user memories and profile
- Manually store memories
- Update user preferences
- Delete memories
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.cerebro_memory import (
    get_cerebro, CerebroMemory,
    MemoryType, MemoryImportance,
    Observation, UserProfile, SessionSummary
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


# ============== Request/Response Models ==============

class StoreMemoryRequest(BaseModel):
    """Request to store a memory"""
    user_id: str = Field(default="default", description="User ID")
    session_id: str = Field(default="manual", description="Session ID")
    memory_type: str = Field(description="Type: preference, fact, decision, discovery, context, style")
    title: str = Field(description="Short summary of the memory")
    importance: str = Field(default="medium", description="Importance: critical, high, medium, low")
    subtitle: Optional[str] = None
    facts: List[str] = Field(default_factory=list)
    narrative: Optional[str] = None
    concepts: List[str] = Field(default_factory=list)


class UpdateProfileRequest(BaseModel):
    """Request to update user profile"""
    user_id: str = Field(default="default")
    display_name: Optional[str] = None
    language_preference: Optional[str] = None  # zh-TW, en, auto
    response_style: Optional[str] = None  # concise, detailed, balanced
    expertise_level: Optional[str] = None  # beginner, intermediate, expert
    profession: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    tools_used: List[str] = Field(default_factory=list)
    preferred_formats: List[str] = Field(default_factory=list)
    dislikes: List[str] = Field(default_factory=list)


class MemoryResponse(BaseModel):
    """Response for a single memory"""
    id: str
    user_id: str
    session_id: str
    memory_type: str
    importance: str
    title: str
    subtitle: Optional[str]
    facts: List[str]
    narrative: Optional[str]
    concepts: List[str]
    confidence: float
    created_at: str
    access_count: int


class UserProfileResponse(BaseModel):
    """Response for user profile"""
    user_id: str
    display_name: Optional[str]
    language_preference: str
    response_style: str
    expertise_level: str
    profession: Optional[str]
    skills: List[str]
    interests: List[str]
    tools_used: List[str]
    preferred_formats: List[str]
    dislikes: List[str]
    observation_count: int
    created_at: str
    updated_at: str


# ============== Helper Functions ==============

def obs_to_response(obs: Observation) -> MemoryResponse:
    """Convert Observation to MemoryResponse"""
    return MemoryResponse(
        id=obs.id,
        user_id=obs.user_id,
        session_id=obs.session_id,
        memory_type=obs.memory_type.value if isinstance(obs.memory_type, MemoryType) else obs.memory_type,
        importance=obs.importance.value if isinstance(obs.importance, MemoryImportance) else obs.importance,
        title=obs.title,
        subtitle=obs.subtitle,
        facts=obs.facts,
        narrative=obs.narrative,
        concepts=obs.concepts,
        confidence=obs.confidence,
        created_at=obs.created_at,
        access_count=obs.access_count
    )


def profile_to_response(profile: UserProfile) -> UserProfileResponse:
    """Convert UserProfile to UserProfileResponse"""
    return UserProfileResponse(
        user_id=profile.user_id,
        display_name=profile.display_name,
        language_preference=profile.language_preference,
        response_style=profile.response_style,
        expertise_level=profile.expertise_level,
        profession=profile.profession,
        skills=profile.skills,
        interests=profile.interests,
        tools_used=profile.tools_used,
        preferred_formats=profile.preferred_formats,
        dislikes=profile.dislikes,
        observation_count=profile.observation_count,
        created_at=profile.created_at,
        updated_at=profile.updated_at
    )


# ============== Endpoints ==============

@router.get("/profile/{user_id}")
async def get_user_profile(user_id: str):
    """Get user profile and memory stats"""
    try:
        cerebro = get_cerebro()
        profile = cerebro.get_or_create_user(user_id)
        return profile_to_response(profile)
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/profile")
async def update_user_profile(request: UpdateProfileRequest):
    """Update user profile"""
    try:
        cerebro = get_cerebro()
        
        # Build updates dict, excluding None values
        updates = {}
        for field, value in request.dict(exclude={'user_id'}).items():
            if value is not None and (not isinstance(value, list) or value):
                updates[field] = value
        
        if not updates:
            return {"success": True, "message": "No updates provided"}
        
        profile = cerebro.update_user_profile(request.user_id, updates)
        return {
            "success": True,
            "profile": profile_to_response(profile)
        }
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/observations/{user_id}")
async def get_user_observations(
    user_id: str,
    memory_type: Optional[str] = None,
    importance: Optional[str] = None,
    limit: int = 20
):
    """Get user's stored memories/observations"""
    try:
        cerebro = get_cerebro()
        
        # Parse filters
        memory_types = None
        if memory_type:
            try:
                memory_types = [MemoryType(memory_type)]
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid memory_type: {memory_type}")
        
        importance_levels = None
        if importance:
            try:
                importance_levels = [MemoryImportance(importance)]
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid importance: {importance}")
        
        observations = cerebro.get_observations(
            user_id=user_id,
            memory_types=memory_types,
            importance_levels=importance_levels,
            limit=limit
        )
        
        return {
            "user_id": user_id,
            "count": len(observations),
            "observations": [obs_to_response(obs) for obs in observations]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting observations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/observations")
async def store_observation(request: StoreMemoryRequest):
    """Store a new memory/observation manually"""
    try:
        cerebro = get_cerebro()
        
        # Parse enums
        try:
            memory_type = MemoryType(request.memory_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid memory_type: {request.memory_type}")
        
        try:
            importance = MemoryImportance(request.importance)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid importance: {request.importance}")
        
        observation = cerebro.store_observation(
            user_id=request.user_id,
            session_id=request.session_id,
            memory_type=memory_type,
            title=request.title,
            importance=importance,
            subtitle=request.subtitle,
            facts=request.facts,
            narrative=request.narrative,
            concepts=request.concepts
        )
        
        return {
            "success": True,
            "observation": obs_to_response(observation)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error storing observation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/observations/{observation_id}")
async def delete_observation(observation_id: str):
    """Delete a memory/observation"""
    try:
        cerebro = get_cerebro()
        success = cerebro.delete_observation(observation_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Observation {observation_id} not found")
        
        return {"success": True, "deleted": observation_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting observation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/{user_id}")
async def search_memories(user_id: str, query: str, limit: int = 10):
    """Search user's memories by keyword"""
    try:
        cerebro = get_cerebro()
        observations = cerebro.search_observations(user_id, query, limit)
        
        return {
            "user_id": user_id,
            "query": query,
            "count": len(observations),
            "observations": [obs_to_response(obs) for obs in observations]
        }
    except Exception as e:
        logger.error(f"Error searching memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/context/{user_id}")
async def get_memory_context(user_id: str, query: Optional[str] = None, max_observations: int = 10):
    """
    Get formatted context for prompt injection.
    This is what gets injected into prompts for personalization.
    """
    try:
        cerebro = get_cerebro()
        context = cerebro.get_context_for_prompt(user_id, query, max_observations)
        
        return {
            "user_id": user_id,
            "query": query,
            "context_length": len(context),
            "context": context
        }
    except Exception as e:
        logger.error(f"Error getting context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summaries/{user_id}")
async def get_session_summaries(user_id: str, limit: int = 10):
    """Get recent session summaries for a user"""
    try:
        cerebro = get_cerebro()
        summaries = cerebro.get_recent_summaries(user_id, limit)
        
        return {
            "user_id": user_id,
            "count": len(summaries),
            "summaries": [s.to_dict() for s in summaries]
        }
    except Exception as e:
        logger.error(f"Error getting session summaries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/types")
async def list_memory_types():
    """List available memory types and importance levels"""
    return {
        "memory_types": [
            {"value": "preference", "description": "User preferences (e.g., 'prefers concise answers')"},
            {"value": "fact", "description": "Facts about user (e.g., 'is a Python developer')"},
            {"value": "decision", "description": "Important decisions made"},
            {"value": "discovery", "description": "Discovered patterns/habits"},
            {"value": "context", "description": "Contextual information"},
            {"value": "style", "description": "Communication style preferences"}
        ],
        "importance_levels": [
            {"value": "critical", "description": "Must always inject (e.g., language preference)"},
            {"value": "high", "description": "Inject when relevant"},
            {"value": "medium", "description": "Inject if space allows"},
            {"value": "low", "description": "Archive, rarely inject"}
        ]
    }


# ============== Update Memory ==============

class UpdateObservationRequest(BaseModel):
    """Request to update an existing observation"""
    title: Optional[str] = None
    subtitle: Optional[str] = None
    facts: Optional[List[str]] = None
    narrative: Optional[str] = None
    concepts: Optional[List[str]] = None
    importance: Optional[str] = None
    memory_type: Optional[str] = None
    confidence: Optional[float] = None


@router.put("/observations/{observation_id}")
async def update_observation(observation_id: str, request: UpdateObservationRequest):
    """Update an existing memory/observation"""
    try:
        cerebro = get_cerebro()
        updates = {k: v for k, v in request.dict().items() if v is not None}
        
        if not updates:
            return {"success": True, "message": "No updates provided"}
        
        result = cerebro.update_observation(observation_id, updates)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Observation {observation_id} not found")
        
        return {
            "success": True,
            "observation": obs_to_response(result)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating observation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Memory Dashboard ==============

@router.get("/dashboard/{user_id}")
async def get_memory_dashboard(user_id: str):
    """
    Get complete memory dashboard for a user.
    Shows: profile + all observations (grouped by type/importance) + stats.
    This is the 'what does the model remember about me' view.
    """
    try:
        cerebro = get_cerebro()
        
        # Get profile
        profile = cerebro.get_or_create_user(user_id)
        
        # Get all observations summary
        obs_summary = cerebro.get_all_observations_summary(user_id)
        
        # Get current prompt context (what's actually injected)
        prompt_context = cerebro.get_context_for_prompt(user_id)
        
        return {
            "user_id": user_id,
            "profile": profile_to_response(profile),
            "memory_stats": {
                "total_observations": obs_summary["total"],
                "by_type": obs_summary["by_type"],
                "by_importance": obs_summary["by_importance"]
            },
            "observations": obs_summary["observations"],
            "prompt_context": {
                "length": len(prompt_context),
                "content": prompt_context,
                "description": "This is what gets injected into every agent prompt"
            }
        }
    except Exception as e:
        logger.error(f"Error getting memory dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/observations/all/{user_id}")
async def delete_all_observations(user_id: str):
    """Delete ALL observations for a user (dangerous!)"""
    try:
        cerebro = get_cerebro()
        with cerebro._cursor() as cursor:
            cursor.execute("DELETE FROM observations WHERE user_id = ?", (user_id,))
            deleted = cursor.rowcount
            cursor.execute("UPDATE user_profiles SET observation_count = 0 WHERE user_id = ?", (user_id,))
        
        return {
            "success": True,
            "user_id": user_id,
            "deleted_count": deleted
        }
    except Exception as e:
        logger.error(f"Error deleting all observations: {e}")
        raise HTTPException(status_code=500, detail=str(e))
