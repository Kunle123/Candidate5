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
    
    def create_profile_functions(self, session_id: str) -> list:
        """Create functions for batched role access (groups of 5)"""
        return [
            {
                "name": "get_role_count",
                "description": "Get the total number of work experience roles in the candidate's profile. Call this FIRST to determine how many batches to request.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_roles_batch",
                "description": "Get a batch of 5 work experience roles starting from a specific index. Call this multiple times to get all roles (batch 0-4, then 5-9, then 10-14, etc).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_index": {
                            "type": "integer",
                            "description": "The starting index for this batch (0, 5, 10, 15, etc). Each batch returns up to 5 roles."
                        }
                    },
                    "required": ["start_index"]
                }
            },
            {
                "name": "get_candidate_metadata",
                "description": "Get candidate's basic information, projects, languages, and interests (but NOT work experience - use get_roles_batch for that).",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]
    
    def create_profile_function(self, session_id: str) -> Dict[str, Any]:
        """Legacy single function - returns full profile"""
        return {
            "name": "get_candidate_profile",
            "description": "Get the complete candidate profile data including work experience, education, skills, and personal information. This function MUST be called before generating any CV content.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    
    def handle_profile_function_call(self, session_id: str, function_name: str, arguments: Dict[str, Any] = None) -> str:
        """Handle batched and legacy profile function calls"""
        profile = self.get_profile(session_id)
        
        if function_name == "get_role_count":
            count = len(profile.get('work_experience', []))
            logger.info(f"[BATCHED] Session {session_id}: Returning role count = {count}")
            return json.dumps({"role_count": count, "batch_size": 5})
        
        elif function_name == "get_roles_batch":
            if not arguments or 'start_index' not in arguments:
                raise ValueError("get_roles_batch requires 'start_index' parameter")
            start_idx = arguments['start_index']
            work_exp = profile.get('work_experience', [])
            
            # Get batch of 5 roles starting from start_idx
            batch = work_exp[start_idx:start_idx + 5]
            batch_info = {
                "start_index": start_idx,
                "batch_size": len(batch),
                "total_roles": len(work_exp),
                "roles": batch
            }
            logger.info(f"[BATCHED] Session {session_id}: Returning roles {start_idx}-{start_idx+len(batch)-1} of {len(work_exp)} total")
            return json.dumps(batch_info, indent=2)
        
        elif function_name == "get_candidate_metadata":
            # Return everything EXCEPT work_experience
            metadata = {k: v for k, v in profile.items() if k not in ['work_experience', 'skills', 'education', 'certifications']}
            logger.info(f"[BATCHED] Session {session_id}: Returning metadata (excluding work_experience, skills, education, certs)")
            return json.dumps(metadata, indent=2)
        
        elif function_name == "get_candidate_profile":
            # Legacy full profile return
            work_exp_count = len(profile.get('work_experience', []))
            skills_count = len(profile.get('skills', []))
            education_count = len(profile.get('education', []))
            certifications_count = len(profile.get('certifications', []))
            
            logger.info(f"[LEGACY] Session {session_id}: Profile contains {work_exp_count} work experiences, {skills_count} skills, {education_count} education, {certifications_count} certifications")
            if work_exp_count > 0:
                companies = [exp.get('company', 'Unknown') for exp in profile.get('work_experience', [])]
                logger.info(f"[LEGACY] Companies: {companies}")
            
            # Filter out static data that AI doesn't meaningfully transform
            filtered_profile = {k: v for k, v in profile.items() 
                              if k not in ['skills', 'education', 'certifications']}
            logger.info(f"[LEGACY] Filtered out: skills ({skills_count}), education ({education_count}), certifications ({certifications_count}) - ~55% payload reduction")
            
            return json.dumps(filtered_profile, indent=2)
        
        else:
            raise ValueError(f"Unknown function: {function_name}")
    
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
    
    def generate_with_batched_roles(self, session_id: str, prompt: str, user_message: str, model: str = "gpt-4o") -> str:
        """Generate CV using batched role access (5 roles at a time)"""
        profile_functions = self.create_profile_functions(session_id)
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_message}
        ]
        
        # Allow LLM to make multiple function calls iteratively
        max_iterations = 10  # Prevent infinite loops (17 roles = 4 batches + metadata + count = ~6 calls)
        for iteration in range(max_iterations):
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                functions=profile_functions
            )
            
            message = response.choices[0].message
            
            # If no function call, LLM is done
            if not message.function_call:
                logger.info(f"[BATCHED] Session {session_id}: Generation complete after {iteration} iterations")
                return message.content
            
            # Handle function call
            func_name = message.function_call.name
            func_args = json.loads(message.function_call.arguments) if message.function_call.arguments else {}
            
            logger.info(f"[BATCHED] Session {session_id}: LLM calling {func_name} with args {func_args}")
            func_result = self.handle_profile_function_call(session_id, func_name, func_args)
            
            # Add function call and result to conversation
            messages.append({
                "role": "assistant",
                "content": None,
                "function_call": {"name": func_name, "arguments": json.dumps(func_args)}
            })
            messages.append({
                "role": "function",
                "name": func_name,
                "content": func_result
            })
        
        logger.warning(f"[BATCHED] Session {session_id}: Hit max iterations ({max_iterations})")
        return "Error: Max iterations reached"
    
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
