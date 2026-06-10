"""
USSD Session Manager
Manages session storage in Redis and session lifecycle.
"""

import json
from datetime import datetime, timedelta
from typing import Optional

from redis.asyncio import Redis as AsyncRedis
from typing import Optional

from packages.shared.config import get_settings

settings = get_settings()


class SessionManager:
    """Redis-backed USSD session storage (production)."""
    
    def __init__(self):
        self.redis: Optional[AsyncRedis] = None
        self.session_ttl = settings.ussd_session_ttl_seconds
    
    async def connect(self):
        """Connect to Redis."""
        self.redis = AsyncRedis.from_url(settings.redis_url, decode_responses=True)
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
    
    async def create_session(self, session_id: str, phone_number: str, language: str) -> dict:
        """Create a new USSD session."""
        session_data = {
            "session_id": session_id,
            "phone_number": phone_number,
            "language": language,
            "user_id": None,
            "current_menu": "AUTH",
            "history": [],
            "context": {},
            "created_at": datetime.utcnow().isoformat(),
            "last_activity_at": datetime.utcnow().isoformat(),
        }
        
        key = f"ussd_session:{session_id}"
        await self.redis.setex(
            key,
            self.session_ttl,
            json.dumps(session_data)
        )
        return session_data
    
    async def get_session(self, session_id: str) -> Optional[dict]:
        """Retrieve session data."""
        key = f"ussd_session:{session_id}"
        data = await self.redis.get(key)
        if not data:
            return None
        return json.loads(data)
    
    async def update_session(self, session_id: str, updates: dict) -> dict:
        """Update session data."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        session.update(updates)
        session["last_activity_at"] = datetime.utcnow().isoformat()
        
        key = f"ussd_session:{session_id}"
        await self.redis.setex(
            key,
            self.session_ttl,
            json.dumps(session)
        )
        return session
    
    async def delete_session(self, session_id: str):
        """Delete session."""
        key = f"ussd_session:{session_id}"
        await self.redis.delete(key)
    
    async def get_user_sessions(self, phone_number: str) -> list[dict]:
        """Get all active sessions for a phone number."""
        pattern = "ussd_session:*"
        keys = await self.redis.keys(pattern)
        
        sessions = []
        for key in keys:
            data = await self.redis.get(key)
            if data:
                session = json.loads(data)
                if session["phone_number"] == phone_number:
                    sessions.append(session)
        
        return sessions


# Global session manager
session_manager = SessionManager()
