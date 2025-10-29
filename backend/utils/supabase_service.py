from typing import List, Dict, Any, Optional
from datetime import datetime
import json
from jose import jwt
from .supabase_config import supabase, supabase_admin, supabase_settings
from ..modules.database import SessionLocal, User as DBUser, Memory as DBMemory, Meeting as DBMeeting, Agent as DBAgent

class SupabaseService:
    def __init__(self):
        self.supabase = supabase
        self.supabase_admin = supabase_admin
        self.supabase_enabled = supabase is not None and supabase_admin is not None

    # User operations with local database fallback
    async def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user in Supabase or local database"""
        # Use local database if Supabase is not configured (AWS deployment)
        if not self.supabase_enabled:
            return await self._create_user_local(user_data)
            
        try:
            result = self.supabase_admin.table('users').insert(user_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Supabase user creation failed, using local database fallback: {e}")
            return await self._create_user_local(user_data)

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        try:
            result = self.supabase.table('users').select('*').eq('username', username).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Supabase failed, using local database: {e}")
            return await self._get_user_by_username_local(username)

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        try:
            result = self.supabase.table('users').select('*').eq('email', email).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Supabase failed, using local database: {e}")
            return await self._get_user_by_email_local(email)

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            result = self.supabase.table('users').select('*').eq('id', user_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Supabase failed, using local database: {e}")
            return await self._get_user_by_id_local(user_id)

    # Local database fallback methods for users
    async def _create_user_local(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create user in local database"""
        db = SessionLocal()
        try:
            db_user = DBUser(
                id=user_data["id"],
                username=user_data["username"],
                email=user_data["email"],
                password_hash=user_data.get("password_hash", "demo_hash"),
                role=user_data.get("role", "user")
            )
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            return {
                "id": db_user.id,
                "username": db_user.username,
                "email": db_user.email,
                "role": db_user.role,
                "created_at": db_user.created_at.isoformat() if db_user.created_at else None
            }
        except Exception as e:
            db.rollback()
            print(f"Error creating user in local database: {e}")
            return None
        finally:
            db.close()

    async def _get_user_by_username_local(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username from local database"""
        db = SessionLocal()
        try:
            db_user = db.query(DBUser).filter(DBUser.username == username).first()
            if db_user:
                return {
                    "id": db_user.id,
                    "username": db_user.username,
                    "email": db_user.email,
                    "role": db_user.role,
                    "created_at": db_user.created_at.isoformat() if db_user.created_at else None
                }
            return None
        except Exception as e:
            print(f"Error getting user from local database: {e}")
            return None
        finally:
            db.close()

    async def _get_user_by_email_local(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email from local database"""
        db = SessionLocal()
        try:
            db_user = db.query(DBUser).filter(DBUser.email == email).first()
            if db_user:
                return {
                    "id": db_user.id,
                    "username": db_user.username,
                    "email": db_user.email,
                    "role": db_user.role,
                    "created_at": db_user.created_at.isoformat() if db_user.created_at else None
                }
            return None
        except Exception as e:
            print(f"Error getting user from local database: {e}")
            return None
        finally:
            db.close()

    async def _get_user_by_id_local(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID from local database"""
        db = SessionLocal()
        try:
            db_user = db.query(DBUser).filter(DBUser.id == user_id).first()
            if db_user:
                return {
                    "id": db_user.id,
                    "username": db_user.username,
                    "email": db_user.email,
                    "role": db_user.role,
                    "created_at": db_user.created_at.isoformat() if db_user.created_at else None
                }
            return None
        except Exception as e:
            print(f"Error getting user from local database: {e}")
            return None
        finally:
            db.close()

    async def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update user UI preferences"""
        try:
            result = self.supabase_admin.table('users').update({
                'ui_preferences': preferences
            }).eq('id', user_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error updating user preferences: {e}")
            return None

    # Meeting operations
    async def create_meeting(self, meeting_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new meeting"""
        try:
            result = self.supabase_admin.table('meetings').insert(meeting_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error creating meeting: {e}")
            return None

    async def get_meeting(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """Get meeting by ID"""
        try:
            result = self.supabase.table('meetings').select('*').eq('id', meeting_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error getting meeting: {e}")
            return None

    async def get_user_meetings(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all meetings for a user"""
        try:
            result = self.supabase.table('meetings').select('*').eq('owner_id', user_id).execute()
            return result.data or []
        except Exception as e:
            print(f"Error getting user meetings: {e}")
            return []

    # Agent operations
    async def create_agent(self, agent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new agent"""
        try:
            result = self.supabase_admin.table('agents').insert(agent_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error creating agent: {e}")
            return None

    async def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent by ID"""
        try:
            result = self.supabase.table('agents').select('*').eq('id', agent_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error getting agent: {e}")
            return None

    async def update_agent_status(self, agent_id: str, status: str) -> bool:
        """Update agent status"""
        try:
            result = self.supabase_admin.table('agents').update({'status': status}).eq('id', agent_id).execute()
            return True
        except Exception as e:
            print(f"Error updating agent status: {e}")
            return False

    # Memory operations (Mem0 compatibility) with local database fallback
    async def save_memory(self, memory_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save a memory"""
        try:
            result = self.supabase_admin.table('memories').insert(memory_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Supabase memory save failed, using local database fallback: {e}")
            print(f"Supabase URL: {getattr(self.supabase_admin, 'supabase_url', 'unknown')}")
            return await self._save_memory_local(memory_data)

    async def get_memories(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get memories with optional filters"""
        try:
            query = self.supabase.table('memories').select('*')

            if filters:
                if 'user_id' in filters:
                    query = query.eq('user_id', filters['user_id'])
                if 'meeting_id' in filters:
                    query = query.eq('meeting_id', filters['meeting_id'])

            result = query.execute()
            return result.data or []
        except Exception as e:
            print(f"Supabase get memories failed, using local database fallback: {e}")
            print(f"Supabase URL: {getattr(self.supabase, 'supabase_url', 'unknown')}")
            return await self._get_memories_local(filters)

    async def search_memories(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search memories using Supabase full-text search"""
        try:
            result = self.supabase.table('memories').select('*').text_search('content', query).limit(limit).execute()
            return result.data or []
        except Exception as e:
            print(f"Supabase failed, using local database: {e}")
            return await self._search_memories_local(query, limit)

    # Local database fallback methods for memories
    async def _save_memory_local(self, memory_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save memory to local database"""
        db = SessionLocal()
        try:
            db_memory = DBMemory(
                id=memory_data.get("id", f"mem_{datetime.utcnow().timestamp()}"),
                content=memory_data["content"],
                memory_metadata=memory_data.get("metadata", {}),
                user_id=memory_data.get("user_id"),
                meeting_id=memory_data.get("meeting_id")
            )
            db.add(db_memory)
            db.commit()
            db.refresh(db_memory)
            return {
                "id": db_memory.id,
                "content": db_memory.content,
                "metadata": db_memory.memory_metadata,
                "user_id": db_memory.user_id,
                "meeting_id": db_memory.meeting_id,
                "created_at": db_memory.created_at.isoformat() if db_memory.created_at else None,
                "updated_at": db_memory.updated_at.isoformat() if db_memory.updated_at else None
            }
        except Exception as e:
            db.rollback()
            print(f"Error saving memory to local database: {e}")
            return None
        finally:
            db.close()

    async def _get_memories_local(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get memories from local database with optional filters"""
        db = SessionLocal()
        try:
            query = db.query(DBMemory)

            if filters:
                if 'user_id' in filters:
                    query = query.filter(DBMemory.user_id == filters['user_id'])
                if 'meeting_id' in filters:
                    query = query.filter(DBMemory.meeting_id == filters['meeting_id'])

            db_memories = query.all()
            return [{
                "id": mem.id,
                "content": mem.content,
                "metadata": mem.memory_metadata,
                "user_id": mem.user_id,
                "meeting_id": mem.meeting_id,
                "created_at": mem.created_at.isoformat() if mem.created_at else None,
                "updated_at": mem.updated_at.isoformat() if mem.updated_at else None
            } for mem in db_memories]
        except Exception as e:
            print(f"Error getting memories from local database: {e}")
            return []
        finally:
            db.close()

    async def _search_memories_local(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search memories in local database using simple text matching"""
        db = SessionLocal()
        try:
            # Simple text search - in production you'd want full-text search
            db_memories = db.query(DBMemory).filter(
                DBMemory.content.contains(query)
            ).limit(limit).all()

            return [{
                "id": mem.id,
                "content": mem.content,
                "metadata": mem.memory_metadata,
                "user_id": mem.user_id,
                "meeting_id": mem.meeting_id,
                "created_at": mem.created_at.isoformat() if mem.created_at else None,
                "updated_at": mem.updated_at.isoformat() if mem.updated_at else None
            } for mem in db_memories]
        except Exception as e:
            print(f"Error searching memories in local database: {e}")
            return []
        finally:
            db.close()

    # Authentication helper
    def verify_supabase_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token with Supabase"""
        try:
            # Decode and verify the JWT token
            payload = jwt.decode(token, supabase_settings.SECRET_KEY, algorithms=[supabase_settings.ALGORITHM])
            return payload
        except Exception as e:
            print(f"Error verifying token: {e}")
            return None

    # Utility methods
    async def health_check(self) -> bool:
        """Check if Supabase connection is working"""
        try:
            result = self.supabase.table('users').select('id').limit(1).execute()
            return True
        except Exception as e:
            print(f"Supabase health check failed: {e}")
            return False

# Global instance
supabase_service = SupabaseService()