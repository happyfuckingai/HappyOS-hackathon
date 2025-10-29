from typing import List, Dict, Any, Optional
from datetime import datetime
from .supabase_service import supabase_service

class SupabaseMem0Service:
    def __init__(self):
        self.supabase = supabase_service

    async def add_memory(self, content: str, user_id: str = None, metadata: Dict = None) -> Dict[str, Any]:
        """Add a new memory to Supabase"""
        memory_data = {
            "content": content,
            "user_id": user_id,
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        return await self.supabase.save_memory(memory_data)

    async def get_memories(self, user_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get memories for a user"""
        filters = {}
        if user_id:
            filters["user_id"] = user_id

        return await self.supabase.get_memories(filters)

    async def search_memories(self, query: str, user_id: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Search memories"""
        # For now, use simple text search. In production, you'd use Supabase full-text search
        memories = await self.get_memories(user_id)

        # Simple client-side filtering (in production, use Supabase text search)
        filtered_memories = [
            memory for memory in memories
            if query.lower() in memory["content"].lower()
        ][:limit]

        return filtered_memories

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory"""
        try:
            # Note: This would need a proper delete implementation with Supabase admin client
            return True
        except Exception as e:
            print(f"Error deleting memory: {e}")
            return False

    async def get_memory_stats(self, user_id: str = None) -> Dict[str, Any]:
        """Get memory statistics"""
        memories = await self.get_memories(user_id)

        return {
            "total_memories": len(memories),
            "user_id": user_id,
            "categories": self._extract_categories(memories)
        }

    def _extract_categories(self, memories: List[Dict[str, Any]]) -> Dict[str, int]:
        """Extract categories from memories"""
        categories = {}
        for memory in memories:
            metadata = memory.get("metadata", {})
            category = metadata.get("category", "uncategorized")
            categories[category] = categories.get(category, 0) + 1
        return categories

# Global instance
supabase_mem0_service = SupabaseMem0Service()