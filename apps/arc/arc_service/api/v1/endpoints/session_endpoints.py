"""
Session Management Endpoints for CV Workflow

This module provides FastAPI endpoints for managing CV workflow sessions,
including starting sessions with profile uploads and ending sessions with cleanup.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from profile_session_manager import get_profile_session_manager
from utils.profile_fetch import get_user_profile

logger = logging.getLogger(__name__)

# Create router for session endpoints
session_router = APIRouter(prefix="/cv/session", tags=["CV Session Management"])


class StartSessionRequest(BaseModel):
    """Request model for starting a CV workflow session."""
    profile: dict = Field(..., description="Complete user profile data")
    user_id: Optional[str] = Field(None, description="Optional user identifier for tracking")


class StartSessionResponse(BaseModel):
    """Response model for session start."""
    session_id: str = Field(..., description="Unique session identifier")
    status: str = Field(..., description="Session status")
    expires_at: str = Field(..., description="Session expiration timestamp")
    message: str = Field(..., description="Success message")


class EndSessionRequest(BaseModel):
    """Request model for ending a CV workflow session."""
    session_id: str = Field(..., description="Session identifier to end")


class EndSessionResponse(BaseModel):
    """Response model for session end."""
    session_id: str = Field(..., description="Session identifier that was ended")
    status: str = Field(..., description="Operation status")
    file_cleaned: bool = Field(..., description="Whether the profile file was successfully cleaned up")
    message: str = Field(..., description="Success message")


class SessionInfoResponse(BaseModel):
    """Response model for session information."""
    session_id: str
    user_id: Optional[str]
    created_at: str
    expires_at: str
    last_accessed: str
    request_count: int
    status: str
    time_remaining: str


@session_router.post("/start", response_model=StartSessionResponse)
async def start_cv_session(request: StartSessionRequest, http_request: Request):
    """
    Start a new CV workflow session.
    """
    try:
        profile = request.profile or {}
        # If profile is empty, try to fetch from user service
        if not profile or not profile.get("name") or not profile.get("email"):
            user_id = request.user_id
            # Get token from Authorization header
            auth_header = http_request.headers.get("authorization")
            if not user_id or not auth_header or not auth_header.lower().startswith("bearer "):
                raise HTTPException(status_code=400, detail="Profile data is required and cannot be empty, and user_id and Authorization token are required to fetch profile.")
            token = auth_header.split(" ", 1)[1]
            try:
                profile = await get_user_profile(user_id, token)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to fetch profile from user service: {str(e)}")
        required_fields = ['name', 'email']
        missing_fields = [field for field in required_fields if not profile.get(field)]
        if missing_fields:
            raise HTTPException(status_code=400, detail=f"Profile missing required fields: {', '.join(missing_fields)}")
        session_manager = get_profile_session_manager()
        session_id = await session_manager.start_session(profile=profile, user_id=request.user_id)
        session_info = session_manager.get_session_info(session_id)
        logger.info(f"Started CV session {session_id} for user {request.user_id}")
        return StartSessionResponse(
            session_id=session_id,
            status="active",
            expires_at=session_info['expires_at'],
            message="CV workflow session started successfully. Profile uploaded and ready for use."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start CV session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")


@session_router.post("/end", response_model=EndSessionResponse)
async def end_cv_session(request: EndSessionRequest):
    """
    End a CV workflow session and clean up resources.
    """
    try:
        session_manager = get_profile_session_manager()
        session_info = session_manager.get_session_info(request.session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail=f"Session {request.session_id} not found or already expired")
        success = await session_manager.end_session(request.session_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Session {request.session_id} not found")
        logger.info(f"Ended CV session {request.session_id}")
        return EndSessionResponse(
            session_id=request.session_id,
            status="ended",
            file_cleaned=True,
            message="CV workflow session ended successfully. Profile file cleaned up."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to end CV session {request.session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to end session: {str(e)}")


@session_router.get("/info/{session_id}", response_model=SessionInfoResponse)
async def get_session_info(session_id: str):
    """
    Get information about a CV workflow session.
    """
    try:
        session_manager = get_profile_session_manager()
        session_info = session_manager.get_session_info(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found or expired")
        return SessionInfoResponse(**session_info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session info for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get session info: {str(e)}")


@session_router.get("/list")
async def list_active_sessions(user_id: Optional[str] = None):
    """
    List all active CV workflow sessions.
    """
    try:
        session_manager = get_profile_session_manager()
        active_sessions = session_manager.list_active_sessions(user_id)
        stats = session_manager.get_stats()
        return {
            "active_sessions": active_sessions,
            "total_active": len(active_sessions),
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")


@session_router.post("/extend/{session_id}")
async def extend_session(session_id: str, hours: int = 24):
    """
    Extend the expiration time of a CV workflow session.
    """
    try:
        if hours <= 0 or hours > 168:
            raise HTTPException(status_code=400, detail="Extension hours must be between 1 and 168 (1 week)")
        session_manager = get_profile_session_manager()
        success = await session_manager.extend_session(session_id, hours)
        if not success:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found or not active")
        session_info = session_manager.get_session_info(session_id)
        return {
            "session_id": session_id,
            "status": "extended",
            "new_expires_at": session_info['expires_at'],
            "hours_extended": hours,
            "message": f"Session extended by {hours} hours"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to extend session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to extend session: {str(e)}")


@session_router.post("/cleanup/expired")
async def cleanup_expired_sessions():
    """
    Manually trigger cleanup of expired sessions.
    """
    try:
        session_manager = get_profile_session_manager()
        cleaned_count = await session_manager.cleanup_expired_sessions()
        return {
            "status": "completed",
            "sessions_cleaned": cleaned_count,
            "message": f"Cleaned up {cleaned_count} expired sessions"
        }
    except Exception as e:
        logger.error(f"Failed to cleanup expired sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup sessions: {str(e)}")


@session_router.get("/stats")
async def get_session_stats():
    """
    Get statistics about CV workflow sessions.
    """
    try:
        session_manager = get_profile_session_manager()
        stats = session_manager.get_stats()
        return {
            "status": "success",
            "stats": stats,
            "timestamp": "utc_now"
        }
    except Exception as e:
        logger.error(f"Failed to get session stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@session_router.get("/health")
async def session_health_check():
    """
    Health check for session management system.
    """
    try:
        session_manager = get_profile_session_manager()
        stats = session_manager.get_stats()
        return {
            "status": "healthy",
            "service": "CV Session Management",
            "active_sessions": stats["active_sessions"],
            "total_sessions": stats["total_sessions"]
        }
    except Exception as e:
        logger.error(f"Session health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "CV Session Management",
            "error": str(e)
        }

