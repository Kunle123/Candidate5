import json
import time
import uuid
import logging
from typing import Dict, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

class FunctionBasedProfileManager:
    """Manages profile sessions using function calling instead of file uploads"""
    
    def __init__(self, openai_client: OpenAI):
        self.client = openai_client
        self.sessions = {}  # In production: use Redis/database
        logger.info("FunctionBasedProfileManager initialized")
    
    def start_session(self, profile: Dict[str, Any], user_id: Optional[str] = None) -> str:
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            'profile': profile,
            'user_id': user_id,
            'created_at': time.time(),
            'last_accessed': time.time()
        }
        logger.info(f"Started session {session_id} for user {user_id}")
        return session_id
    
    def get_profile(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")
        session = self.sessions[session_id]
        if time.time() - session['created_at'] > 86400:
            del self.sessions[session_id]
            raise ValueError(f"Session {session_id} has expired")
        session['last_accessed'] = time.time()
        return session['profile']
    
    def end_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Ended session {session_id}")
            return True
        return False
    
    def create_profile_function(self, session_id: str) -> Dict[str, Any]:
        return {
            "name": "get_candidate_profile",
            "description": "Get the complete candidate profile data including work experience, education, skills, and personal information. This function MUST be called before generating any CV content.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    
    def handle_profile_function_call(self, session_id: str, function_name: str) -> str:
        if function_name != "get_candidate_profile":
            raise ValueError(f"Unknown function: {function_name}")
        profile = self.get_profile(session_id)
        return json.dumps(profile, indent=2)
    
    def generate_with_profile_function(self, session_id: str, prompt: str, user_message: str, model: str = "gpt-4o") -> str:
        profile_function = self.create_profile_function(session_id)
        initial_response = self.client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system", 
                    "content": "You MUST call the get_candidate_profile function first to access the candidate's information before proceeding with any task."
                },
                {
                    "role": "user", 
                    "content": f"Task: {user_message}"
                }
            ],
            functions=[profile_function],
            function_call={"name": "get_candidate_profile"}
        )
        function_call = initial_response.choices[0].message.function_call
        profile_data = self.handle_profile_function_call(session_id, function_call.name)
        final_response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": None, "function_call": function_call},
                {"role": "function", "name": "get_candidate_profile", "content": profile_data},
                {"role": "user", "content": "Now generate the requested content using the profile data you just received."}
            ]
        )
        return final_response.choices[0].message.content
    
    def cleanup_expired_sessions(self):
        current_time = time.time()
        expired_sessions = [
            session_id for session_id, session in self.sessions.items()
            if current_time - session['created_at'] > 86400
        ]
        for session_id in expired_sessions:
            del self.sessions[session_id]
            logger.info(f"Cleaned up expired session {session_id}")
        return len(expired_sessions)

profile_manager = None

def get_profile_manager() -> FunctionBasedProfileManager:
    global profile_manager
    if profile_manager is None:
        from openai import OpenAI
        import os
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        profile_manager = FunctionBasedProfileManager(client)
    return profile_manager
