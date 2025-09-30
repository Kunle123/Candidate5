"""
Profile Session Manager for CV Workflow

This module provides session-based profile file management for OpenAI API interactions.
It uploads a profile once per session and reuses the file reference across multiple
CV workflow requests (preview, generate, update) until explicit cleanup.
"""

import json
import time
import uuid
import hashlib
import logging
import asyncio
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import io
from openai import OpenAI

logger = logging.getLogger(__name__)


def sanitize_profile(profile: dict) -> dict:
    sanitized = profile.copy()
    sanitized['name'] = "Candidate Name"
    sanitized['email'] = "candidate@email.com"
    return sanitized


class ProfileSessionManager:
    """
    Manages profile file uploads and sessions for CV workflow operations.
    
    This class handles:
    - Uploading profiles to OpenAI as files once per session
    - Tracking session metadata and file references
    - Automatic session cleanup and file deletion
    - Session validation and expiration
    """
    
    def __init__(self, openai_client: OpenAI, session_ttl_hours: int = 24):
        """
        Initialize the ProfileSessionManager.
        
        Args:
            openai_client: Configured OpenAI client instance
            session_ttl_hours: Time-to-live for sessions in hours (default: 24)
        """
        self.client = openai_client
        self.session_ttl_hours = session_ttl_hours
        self.sessions: Dict[str, Dict[str, Any]] = {}
        
        # Start background cleanup task
        self._cleanup_task = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """Start background task for automatic session cleanup."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """Periodically clean up expired sessions."""
        while True:
            try:
                await self.cleanup_expired_sessions()
                # Run cleanup every hour
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
                await asyncio.sleep(3600)  # Continue despite errors
    
    async def start_session(self, profile: Dict[str, Any], user_id: Optional[str] = None) -> str:
        """
        Start a new CV workflow session by uploading the profile to OpenAI.
        
        Args:
            profile: User profile data dictionary
            user_id: Optional user identifier for tracking
            
        Returns:
            session_id: Unique session identifier
            
        Raises:
            Exception: If profile upload fails
        """
        session_id = str(uuid.uuid4())
        
        try:
            # Sanitize profile to avoid sending PII
            profile_to_upload = sanitize_profile(profile)
            # Create profile hash for change detection
            profile_json = json.dumps(profile_to_upload, sort_keys=True)
            profile_hash = hashlib.md5(profile_json.encode()).hexdigest()
            
            # Upload profile as file to OpenAI
            file_obj = io.BytesIO(profile_json.encode('utf-8'))
            file_obj.name = f'profile_{session_id}.json'
            
            file_response = self.client.files.create(
                file=file_obj,
                purpose="assistants"
            )
            
            # Store session metadata
            self.sessions[session_id] = {
                'file_id': file_response.id,
                'user_id': user_id,
                'profile_hash': profile_hash,
                'created_at': datetime.utcnow(),
                'expires_at': datetime.utcnow() + timedelta(hours=self.session_ttl_hours),
                'last_accessed': datetime.utcnow(),
                'request_count': 0,
                'status': 'active'
            }
            
            logger.info(f"Started CV session {session_id} with file {file_response.id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            # Clean up partial session if it exists
            if session_id in self.sessions:
                await self._cleanup_session(session_id)
            raise Exception(f"Failed to upload profile: {str(e)}")
    
    def get_file_id(self, session_id: str) -> Optional[str]:
        """
        Get the OpenAI file ID for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            file_id: OpenAI file ID if session exists and is valid, None otherwise
        """
        session_data = self.sessions.get(session_id)
        
        if not session_data:
            logger.warning(f"Session {session_id} not found")
            return None
        
        # Check if session is expired
        if datetime.utcnow() > session_data['expires_at']:
            logger.warning(f"Session {session_id} has expired")
            asyncio.create_task(self._cleanup_session(session_id))
            return None
        
        if session_data['status'] != 'active':
            logger.warning(f"Session {session_id} is not active (status: {session_data['status']})")
            return None
        
        # Update last accessed time and increment request count
        session_data['last_accessed'] = datetime.utcnow()
        session_data['request_count'] += 1
        
        return session_data['file_id']
    
    async def end_session(self, session_id: str) -> bool:
        """
        End a CV workflow session and clean up the associated file.
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: True if session was successfully ended, False if not found
        """
        if session_id not in self.sessions:
            logger.warning(f"Attempted to end non-existent session {session_id}")
            return False
        
        await self._cleanup_session(session_id)
        logger.info(f"Ended CV session {session_id}")
        return True
    
    async def _cleanup_session(self, session_id: str):
        """
        Internal method to clean up a single session.
        
        Args:
            session_id: Session identifier
        """
        session_data = self.sessions.get(session_id)
        if not session_data:
            return
        
        # Mark session as cleaning up
        session_data['status'] = 'cleaning_up'
        
        try:
            # Delete file from OpenAI
            self.client.files.delete(session_data['file_id'])
            logger.info(f"Deleted OpenAI file {session_data['file_id']} for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to delete OpenAI file {session_data['file_id']}: {e}")
        
        # Remove session from memory
        del self.sessions[session_id]
    
    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up all expired sessions.
        
        Returns:
            int: Number of sessions cleaned up
        """
        current_time = datetime.utcnow()
        expired_sessions = [
            session_id for session_id, data in self.sessions.items()
            if current_time > data['expires_at']
        ]
        
        cleanup_tasks = [self._cleanup_session(session_id) for session_id in expired_sessions]
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
        
        return len(expired_sessions)
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            dict: Session information or None if not found
        """
        session_data = self.sessions.get(session_id)
        if not session_data:
            return None
        
        return {
            'session_id': session_id,
            'user_id': session_data['user_id'],
            'created_at': session_data['created_at'].isoformat(),
            'expires_at': session_data['expires_at'].isoformat(),
            'last_accessed': session_data['last_accessed'].isoformat(),
            'request_count': session_data['request_count'],
            'status': session_data['status'],
            'time_remaining': str(session_data['expires_at'] - datetime.utcnow())
        }
    
    def list_active_sessions(self, user_id: Optional[str] = None) -> list:
        """
        List all active sessions, optionally filtered by user_id.
        
        Args:
            user_id: Optional user ID to filter sessions
            
        Returns:
            list: List of active session information
        """
        active_sessions = []
        current_time = datetime.utcnow()
        
        for session_id, data in self.sessions.items():
            if (data['status'] == 'active' and 
                current_time <= data['expires_at'] and
                (user_id is None or data['user_id'] == user_id)):
                
                active_sessions.append(self.get_session_info(session_id))
        
        return active_sessions
    
    async def extend_session(self, session_id: str, hours: int = 24) -> bool:
        """
        Extend the expiration time of a session.
        
        Args:
            session_id: Session identifier
            hours: Number of hours to extend (default: 24)
            
        Returns:
            bool: True if session was extended, False if not found
        """
        session_data = self.sessions.get(session_id)
        if not session_data or session_data['status'] != 'active':
            return False
        
        session_data['expires_at'] = datetime.utcnow() + timedelta(hours=hours)
        logger.info(f"Extended session {session_id} by {hours} hours")
        return True
    
    async def cleanup_all_sessions(self):
        """Clean up all sessions (useful for shutdown)."""
        session_ids = list(self.sessions.keys())
        cleanup_tasks = [self._cleanup_session(session_id) for session_id in session_ids]
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        logger.info(f"Cleaned up all {len(session_ids)} sessions")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about current sessions.
        
        Returns:
            dict: Session statistics
        """
        current_time = datetime.utcnow()
        active_count = sum(1 for data in self.sessions.values() 
                          if data['status'] == 'active' and current_time <= data['expires_at'])
        expired_count = sum(1 for data in self.sessions.values() 
                           if current_time > data['expires_at'])
        total_requests = sum(data['request_count'] for data in self.sessions.values())
        
        return {
            'total_sessions': len(self.sessions),
            'active_sessions': active_count,
            'expired_sessions': expired_count,
            'total_requests_served': total_requests,
            'average_requests_per_session': total_requests / len(self.sessions) if self.sessions else 0
        }


# Global instance (to be initialized with OpenAI client)
profile_session_manager: Optional[ProfileSessionManager] = None


def initialize_profile_session_manager(openai_client: OpenAI, session_ttl_hours: int = 24):
    """
    Initialize the global ProfileSessionManager instance.
    
    Args:
        openai_client: Configured OpenAI client
        session_ttl_hours: Session time-to-live in hours
    """
    global profile_session_manager
    profile_session_manager = ProfileSessionManager(openai_client, session_ttl_hours)
    logger.info("ProfileSessionManager initialized")


def get_profile_session_manager() -> ProfileSessionManager:
    """
    Get the global ProfileSessionManager instance.
    
    Returns:
        ProfileSessionManager: The global instance
        
    Raises:
        RuntimeError: If manager hasn't been initialized
    """
    if profile_session_manager is None:
        raise RuntimeError("ProfileSessionManager not initialized. Call initialize_profile_session_manager() first.")
    return profile_session_manager
