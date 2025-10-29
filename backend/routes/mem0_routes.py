from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from sqlalchemy.orm import Session
import json

from ..modules.auth import get_current_user
from ..modules.database import get_db, Meeting
from ..modules.models import User as UserModel
from ..utils.supabase_mem0_service import supabase_mem0_service
from ..utils.supabase_service import supabase_service

router = APIRouter()

# ========== KONSTANTER OCH TILLSTÅND ==========

MEM0_AVAILABLE = False  # För närvarande använder vi bara Supabase

# ========== HJÄLPFUNKTIONER ==========

async def get_user_mem0_client(user_id: str):
    """Hämtar mem0-klient för användare - för närvarande inte implementerad"""
    # Denna funktion skulle skapa en mem0-klient för användaren
    # För närvarande använder vi bara Supabase
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="mem0 service not available"
    )

def serialize_memory(memory: Dict) -> Dict:
    """Serialiserar minne för JSON-svar"""
    return {
        "id": memory.get("id"),
        "content": memory.get("content", ""),
        "created_at": memory.get("created_at"),
        "updated_at": memory.get("updated_at"),
        "metadata": memory.get("metadata", {}),
        "user_id": memory.get("user_id")
    }

# ========== MEMORY MANAGEMENT ENDPOINTS (SUPABASE + LOCAL DB) ==========

@router.get("/memories", response_model=Dict[str, Any])
async def get_all_memories(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: Optional[str] = None,
    current_user: UserModel = Depends(get_current_user)
):
    """Hämtar alla minnen för användaren från Supabase"""
    try:
        # Använd specifik user_id eller current_user
        target_user_id = user_id or current_user.id

        # Hämta minnen från Supabase
        memories = await supabase_mem0_service.get_memories(user_id=target_user_id)

        # Konvertera till serialiserbart format
        serialized_memories = [serialize_memory(memory) for memory in memories]

        # Sortera efter uppdateringsdatum (senaste först)
        serialized_memories.sort(key=lambda x: x.get("updated_at") or "", reverse=True)

        # Applicera paginering
        total_count = len(serialized_memories)
        paginated_memories = serialized_memories[offset:offset + limit]

        return {
            "memories": paginated_memories,
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve memories: {str(e)}"
        )

@router.get("/memories/{memory_id}", response_model=Dict[str, Any])
async def get_memory(
    memory_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Hämtar specifikt minne från Supabase eller lokal databas"""
    try:
        # Hämta alla minnen för användaren och filtrera efter ID
        memories = await supabase_mem0_service.get_memories(user_id=current_user.id)
        memory = next((m for m in memories if m.get("id") == memory_id), None)

        if not memory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory not found"
            )

        return serialize_memory(memory)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve memory: {str(e)}"
        )

@router.post("/memories", response_model=Dict[str, Any])
async def add_memory(
    memory_data: Dict[str, Any],
    current_user: UserModel = Depends(get_current_user)
):
    """Lägger till nytt minne i Supabase"""
    try:
        content = memory_data.get("content")
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Memory content is required"
            )

        # Lägg till metadata
        metadata = memory_data.get("metadata", {})
        metadata.update({
            "created_by": current_user.id,
            "created_at": datetime.now().isoformat(),
            "source": "manual_entry"
        })

        # Spara i Supabase
        result = await supabase_mem0_service.add_memory(
            content=content,
            user_id=current_user.id,
            metadata=metadata
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save memory"
            )

        return {
            "id": result.get("id"),
            "content": content,
            "metadata": metadata,
            "created_at": result.get("created_at"),
            "user_id": current_user.id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add memory: {str(e)}"
        )

@router.put("/memories/{memory_id}", response_model=Dict[str, Any])
async def update_memory(
    memory_id: str,
    updates: Dict[str, Any],
    current_user: UserModel = Depends(get_current_user)
):
    """Uppdaterar befintligt minne"""
    try:
        # För närvarande använder vi Supabase med lokal fallback
        # Vi lägger till som nytt minne med uppdaterad data
        old_memories = await supabase_mem0_service.get_memories(user_id=current_user.id)
        old_memory = next((m for m in old_memories if m.get("id") == memory_id), None)

        if not old_memory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory not found"
            )

        # Skapa uppdaterat minne
        new_content = updates.get("content", old_memory.get("content", ""))

        # Uppdatera metadata
        metadata = old_memory.get("metadata", {})
        metadata.update(updates.get("metadata", {}))
        metadata["updated_at"] = datetime.now().isoformat()
        metadata["updated_by"] = current_user.id

        # Spara uppdaterat minne
        result = await supabase_mem0_service.add_memory(
            content=new_content,
            user_id=current_user.id,
            metadata=metadata
        )

        return {
            "id": result.get("id", memory_id),
            "content": new_content,
            "metadata": metadata,
            "updated_at": datetime.now().isoformat(),
            "user_id": current_user.id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update memory: {str(e)}"
        )

@router.delete("/memories/{memory_id}")
async def delete_memory(
    memory_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Tar bort minne (markerar som borttagen)"""
    try:
        # För närvarande använder vi Supabase med lokal fallback
        # Vi markerar som borttagen istället för att faktiskt ta bort
        memories = await supabase_mem0_service.get_memories(user_id=current_user.id)
        memory = next((m for m in memories if m.get("id") == memory_id), None)

        if not memory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory not found"
            )

        # Uppdatera metadata för att markera som borttagen
        metadata = memory.get("metadata", {})
        metadata["deleted_at"] = datetime.now().isoformat()
        metadata["deleted_by"] = current_user.id
        metadata["is_deleted"] = True

        # Uppdatera minnet genom att lägga till som nytt med borttagen-markering
        deleted_content = "[DELETED] " + memory.get("content", "")

        await supabase_mem0_service.add_memory(
            content=deleted_content,
            user_id=current_user.id,
            metadata=metadata
        )

        return {"message": "Memory marked as deleted"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete memory: {str(e)}"
        )

# ========== SÖK ENDPOINTS (SUPABASE) ==========

@router.get("/search", response_model=Dict[str, Any])
async def search_memories(
    q: str = Query(..., description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    user_id: Optional[str] = None,
    filters: Optional[str] = None,
    current_user: UserModel = Depends(get_current_user)
):
    """Sök i minnen med Supabase"""
    try:
        target_user_id = user_id or current_user.id

        # Sök i Supabase
        memories = await supabase_mem0_service.search_memories(
            query=q,
            user_id=target_user_id,
            limit=limit
        )

        # Serialisera resultat
        serialized_results = [serialize_memory(memory) for memory in memories]

        return {
            "query": q,
            "results": serialized_results,
            "total": len(memories),
            "limit": limit,
            "filters_applied": filters is not None
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )

@router.post("/search/semantic", response_model=Dict[str, Any])
async def semantic_search(
    query_data: Dict[str, Any],
    current_user: UserModel = Depends(get_current_user)
):
    """Semantisk sökning i minnen (för närvarande använder vanlig textsökning)"""
    try:
        query = query_data.get("query", "")
        if not query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query is required for semantic search"
            )

        # För närvarande använder vi vanlig textsökning
        # I framtiden kan vi implementera riktig semantisk sökning med embeddings
        fallback_response = await search_memories(
            q=query,
            limit=query_data.get("limit", 10),
            filters=json.dumps(query_data.get("filters", {})),
            current_user=current_user
        )

        return {
            **fallback_response,
            "search_type": "text_search",
            "note": "Semantic search not fully implemented yet, using text search"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic search failed: {str(e)}"
        )

# ========== MÖTESPECIFIKA MINNEN ==========

@router.get("/meetings/{meeting_id}/memories", response_model=Dict[str, Any])
async def get_meeting_memories(
    meeting_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Hämtar alla minnen kopplade till ett möte från Supabase eller lokal databas"""
    try:
        # Kontrollera att möte finns
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meeting not found"
            )

        # Hämta alla minnen för användaren
        memories = await supabase_mem0_service.get_memories(user_id=current_user.id)

        # Filtrera minnen som är kopplade till detta möte
        meeting_memories = [
            serialize_memory(memory) for memory in memories
            if memory.get("metadata", {}).get("meeting_id") == meeting_id
        ]

        return {
            "meeting_id": meeting_id,
            "memories": meeting_memories,
            "count": len(meeting_memories)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get meeting memories: {str(e)}"
        )

@router.post("/meetings/{meeting_id}/memories", response_model=Dict[str, Any])
async def link_memories_to_meeting(
    meeting_id: str,
    link_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Kopplar minnen till ett möte"""
    try:
        memory_ids = link_data.get("memory_ids", [])
        if not memory_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Memory IDs are required"
            )

        # Kontrollera att möte finns
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meeting not found"
            )

        # Hämta alla minnen för användaren
        memories = await supabase_mem0_service.get_memories(user_id=current_user.id)

        # Uppdatera metadata för valda minnen
        updated_count = 0
        for memory in memories:
            if memory.get("id") in memory_ids:
                metadata = memory.get("metadata", {})
                metadata["meeting_id"] = meeting_id
                metadata["linked_at"] = datetime.now().isoformat()
                metadata["linked_by"] = current_user.id

                # Uppdatera minnet genom att lägga till som nytt
                await supabase_mem0_service.add_memory(
                    content=memory.get("content", ""),
                    user_id=current_user.id,
                    metadata=metadata
                )
                updated_count += 1

        return {
            "meeting_id": meeting_id,
            "linked_memories": updated_count,
            "message": f"Linked {updated_count} memories to meeting"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to link memories to meeting: {str(e)}"
        )

@router.delete("/meetings/{meeting_id}/memories", response_model=Dict[str, Any])
async def unlink_memories_from_meeting(
    meeting_id: str,
    unlink_data: Dict[str, Any],
    current_user: UserModel = Depends(get_current_user)
):
    """Tar bort koppling mellan minnen och möte"""
    try:
        memory_ids = unlink_data.get("memory_ids", [])

        memories = await supabase_mem0_service.get_memories(user_id=current_user.id)

        # Ta bort meeting_id från metadata
        updated_count = 0
        for memory in memories:
            if memory.get("id") in memory_ids:
                metadata = memory.get("metadata", {})
                metadata.pop("meeting_id", None)
                metadata.pop("linked_at", None)
                metadata.pop("linked_by", None)
                metadata["unlinked_at"] = datetime.now().isoformat()
                metadata["unlinked_by"] = current_user.id

                # Uppdatera minnet
                await supabase_mem0_service.add_memory(
                    content=memory.get("content", ""),
                    user_id=current_user.id,
                    metadata=metadata
                )
                updated_count += 1

        return {
            "meeting_id": meeting_id,
            "unlinked_memories": updated_count,
            "message": f"Unlinked {updated_count} memories from meeting"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unlink memories from meeting: {str(e)}"
        )

# ========== STATISTIK ENDPOINTS (SUPABASE) ==========

@router.get("/stats", response_model=Dict[str, Any])
async def get_memory_stats(
    current_user: UserModel = Depends(get_current_user)
):
    """Hämtar statistik för användarens minnen från Supabase"""
    try:
        stats = await supabase_mem0_service.get_memory_stats(user_id=current_user.id)

        return {
            "total_memories": stats.get("total_memories", 0),
            "memories_with_metadata": 0,  # Kan utökas senare
            "categories": stats.get("categories", {}),
            "this_week": stats.get("total_memories", 0),
            "this_month": stats.get("total_memories", 0),
            "average_per_week": stats.get("total_memories", 0),
            "user_id": current_user.id,
            "database": "supabase"
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get memory stats: {str(e)}"
        )

@router.get("/meetings/{meeting_id}/stats", response_model=Dict[str, Any])
async def get_meeting_memory_stats(
    meeting_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Hämtar statistik för mötespecifika minnen från Supabase eller lokal databas"""
    try:
        # Kontrollera att möte finns
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meeting not found"
            )

        memories = await supabase_mem0_service.get_memories(user_id=current_user.id)

        # Filtrera mötespecifika minnen
        meeting_memories = [
            memory for memory in memories
            if memory.get("metadata", {}).get("meeting_id") == meeting_id
        ]

        # Beräkna statistik för möte
        total_meeting_memories = len(meeting_memories)

        categories = {}
        for memory in meeting_memories:
            metadata = memory.get("metadata", {})
            category = metadata.get("category")
            if category:
                categories[category] = categories.get(category, 0) + 1

        return {
            "meeting_id": meeting_id,
            "total_memories": total_meeting_memories,
            "categories": categories,
            "linked_at": meeting.created_at.isoformat() if meeting.created_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get meeting memory stats: {str(e)}"
        )

# ========== EXPORT/IMPORT ENDPOINTS ==========

@router.get("/export")
async def export_memories(
    format: str = Query("json", regex="^(json|csv)$"),
    current_user: UserModel = Depends(get_current_user)
):
    """Exporterar användarens minnen från Supabase eller lokal databas"""
    try:
        memories = await supabase_mem0_service.get_memories(user_id=current_user.id)
        serialized_memories = [serialize_memory(memory) for memory in memories]

        if format == "csv":
            # Konvertera till CSV-format
            import csv
            import io

            output = io.StringIO()
            fieldnames = ["id", "content", "created_at", "updated_at", "metadata"]
            writer = csv.DictWriter(output, fieldnames=fieldnames)

            writer.writeheader()
            for memory in serialized_memories:
                writer.writerow({
                    "id": memory.get("id", ""),
                    "content": memory.get("content", ""),
                    "created_at": memory.get("created_at", ""),
                    "updated_at": memory.get("updated_at", ""),
                    "metadata": json.dumps(memory.get("metadata", {}), ensure_ascii=False)
                })

            return {
                "content": output.getvalue(),
                "content_type": "text/csv",
                "filename": f"memories_{current_user.id}_{datetime.now().strftime('%Y%m%d')}.csv"
            }

        else:  # json format
            return {
                "memories": serialized_memories,
                "exported_at": datetime.now().isoformat(),
                "total_count": len(serialized_memories),
                "user_id": current_user.id
            }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )

@router.post("/import")
async def import_memories(
    file: Dict[str, Any],
    merge_strategy: str = Query("skip_existing", regex="^(skip_existing|overwrite|duplicate)$"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Importerar minnen från fil"""
    # Denna endpoint skulle hantera filuppladdning och import
    # För närvarande är den inte fullständigt implementerad

    return {
        "message": "Import functionality not yet implemented",
        "merge_strategy": merge_strategy
    }

# ========== KATEGORI/TAGG ENDPOINTS ==========

@router.get("/categories", response_model=Dict[str, Any])
async def get_memory_categories(
    current_user: UserModel = Depends(get_current_user)
):
    """Hämtar alla kategorier för användarens minnen från Supabase eller lokal databas"""
    try:
        memories = await supabase_mem0_service.get_memories(user_id=current_user.id)

        categories = {}
        for memory in memories:
            metadata = memory.get("metadata", {})
            category = metadata.get("category")
            if category:
                if category not in categories:
                    categories[category] = {
                        "name": category,
                        "count": 0,
                        "latest_memory": None
                    }
                categories[category]["count"] += 1

                # Uppdatera senaste minne
                memory_date = memory.get("created_at")
                if not categories[category]["latest_memory"] or memory_date > categories[category]["latest_memory"]:
                    categories[category]["latest_memory"] = memory_date

        category_list = list(categories.values())
        category_list.sort(key=lambda x: x["count"], reverse=True)

        return {
            "categories": category_list,
            "total_categories": len(category_list)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get categories: {str(e)}"
        )

@router.post("/memories/{memory_id}/categories")
async def add_memory_category(
    memory_id: str,
    category_data: Dict[str, Any],
    current_user: UserModel = Depends(get_current_user)
):
    """Lägger till kategori till minne"""
    try:
        category = category_data.get("category")
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category is required"
            )

        memories = await supabase_mem0_service.get_memories(user_id=current_user.id)
        memory = next((m for m in memories if m.get("id") == memory_id), None)
        if not memory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory not found"
            )

        # Uppdatera metadata med kategori
        metadata = memory.get("metadata", {})
        if "categories" not in metadata:
            metadata["categories"] = []
        if category not in metadata["categories"]:
            metadata["categories"].append(category)
        metadata["category"] = category  # Primär kategori
        metadata["categorized_at"] = datetime.now().isoformat()
        metadata["categorized_by"] = current_user.id

        # Uppdatera minnet genom att lägga till som nytt
        await supabase_mem0_service.add_memory(
            content=memory.get("content", ""),
            user_id=current_user.id,
            metadata=metadata
        )

        return {
            "memory_id": memory_id,
            "category": category,
            "updated_at": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add category: {str(e)}"
        )

@router.delete("/memories/{memory_id}/categories")
async def remove_memory_category(
    memory_id: str,
    category_data: Dict[str, Any],
    current_user: UserModel = Depends(get_current_user)
):
    """Tar bort kategori från minne"""
    try:
        category = category_data.get("category")
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category is required"
            )

        memories = await supabase_mem0_service.get_memories(user_id=current_user.id)
        memory = next((m for m in memories if m.get("id") == memory_id), None)
        if not memory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory not found"
            )

        # Ta bort kategori från metadata
        metadata = memory.get("metadata", {})
        if "categories" in metadata:
            metadata["categories"] = [c for c in metadata["categories"] if c != category]
        if metadata.get("category") == category:
            metadata["category"] = metadata["categories"][0] if metadata["categories"] else None

        metadata["category_removed_at"] = datetime.now().isoformat()
        metadata["category_removed_by"] = current_user.id

        # Uppdatera minnet genom att lägga till som nytt
        await supabase_mem0_service.add_memory(
            content=memory.get("content", ""),
            user_id=current_user.id,
            metadata=metadata
        )

        return {
            "memory_id": memory_id,
            "removed_category": category,
            "updated_at": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove category: {str(e)}"
        )

# ========== HJÄLP ENDPOINTS (SUPABASE) ==========

@router.get("/health")
async def mem0_health_check():
    """Kontrollerar hälsa för minnes-tjänster"""
    try:
        # Testa Supabase-anslutning
        health = await supabase_service.health_check()

        return {
            "supabase_connected": health,
            "status": "healthy" if health else "disconnected",
            "database": "supabase",
            "mem0_available": MEM0_AVAILABLE,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "supabase_connected": False,
            "status": "error",
            "error": str(e),
            "database": "supabase",
            "mem0_available": MEM0_AVAILABLE,
            "timestamp": datetime.now().isoformat()
        }

@router.get("/meetings")
async def get_meetings_with_memories(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Hämtar alla möten med mem0-integration"""
    try:
        # Hämta alla möten användaren har tillgång till
        meetings = db.query(Meeting).all()

        meetings_with_memory_data = []
        for meeting in meetings:
            # Kontrollera om användaren har tillgång till mötet
            if current_user.id == meeting.owner_id or current_user.id in [p.id for p in meeting.participants]:
                meetings_with_memory_data.append({
                    "id": meeting.id,
                    "name": meeting.name,
                    "status": meeting.status,
                    "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
                    "has_memories": True,  # För närvarande antar vi att alla möten kan ha minnen
                    "memory_count": 0  # Detta skulle räknas från mem0
                })

        return {
            "meetings": meetings_with_memory_data,
            "total": len(meetings_with_memory_data)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get meetings with memories: {str(e)}"
        )