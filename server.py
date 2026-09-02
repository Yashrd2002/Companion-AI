"""
FastAPI Backend Server for Companion-AI ("Maya").
Provides REST API endpoints for chat, memory inspection, contradiction audit,
and user profile management.
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pathlib import Path
import uvicorn

from src.companion import Companion
from src.config import config
from src.memory.models import MemoryStatus

FRONTEND_DIR = Path(__file__).parent / "frontend"

app = FastAPI(
    title="Companion-AI Memory & Persona API",
    description="Cognitive memory architecture with persistent retrieval, contradiction supersession, and persona stability.",
    version="1.0.0",
)

# Enable CORS for frontend integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend static directory
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# Shared companion instance
companion = Companion()


@app.get("/")
def serve_index():
    """Serve the companion web UI frontend."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Companion-AI Backend API is online. Visit /docs for API documentation."}



# --- Request & Response Models ---

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message to the companion")
    user_id: Optional[str] = Field(default="default_user", description="User ID for multi-session support")


class MemoryItem(BaseModel):
    id: str
    fact_text: str
    category: str
    importance: float
    confidence: float
    access_count: int
    status: str
    superseded_by_id: Optional[str] = None
    created_at: str
    updated_at: str


class ChatResponse(BaseModel):
    reply: str
    turn_index: int
    retrieved_memories: List[MemoryItem]
    extracted_facts: List[MemoryItem]


class InspectRequest(BaseModel):
    query: str
    top_k: int = 5
    user_id: Optional[str] = "default_user"


class ResetRequest(BaseModel):
    user_id: Optional[str] = "default_user"


# --- Endpoints ---

@app.get("/health")
def health_check():
    """Returns backend status, current LLM provider, and memory counts."""
    active_facts = companion.get_active_memories()
    all_facts = companion.get_all_memories()
    return {
        "status": "online",
        "companion_name": companion.persona.name,
        "llm_provider": config.llm_provider,
        "model_name": config.model_name,
        "total_facts_stored": len(all_facts),
        "active_facts": len(active_facts),
        "superseded_facts": len([f for f in all_facts if f.status == MemoryStatus.SUPERSEDED]),
    }


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    """Chat with the companion. Executes retrieval, generation, fact extraction, and contradiction handling."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if req.user_id != companion.user_id:
        active_companion = Companion(user_id=req.user_id)
    else:
        active_companion = companion

    resp = active_companion.chat(req.message)

    def _to_item(f) -> MemoryItem:
        return MemoryItem(
            id=f.id,
            fact_text=f.fact_text,
            category=f.category.value if hasattr(f.category, "value") else str(f.category),
            importance=f.importance,
            confidence=f.confidence,
            access_count=f.access_count,
            status=f.status.value if hasattr(f.status, "value") else str(f.status),
            superseded_by_id=f.superseded_by_id,
            created_at=f.created_at.isoformat(),
            updated_at=f.updated_at.isoformat(),
        )

    return ChatResponse(
        reply=resp.content,
        turn_index=resp.turn_index,
        retrieved_memories=[_to_item(m) for m in resp.retrieved_memories],
        extracted_facts=[_to_item(f) for f in resp.extracted_facts],
    )


@app.get("/memories", response_model=List[MemoryItem])
def get_memories(user_id: str = "default_user", all_history: bool = False):
    """Fetch active or all stored memories for a user."""
    facts = companion.store.get_all_facts(user_id) if all_history else companion.store.get_active_facts(user_id)
    return [
        MemoryItem(
            id=f.id,
            fact_text=f.fact_text,
            category=f.category.value if hasattr(f.category, "value") else str(f.category),
            importance=f.importance,
            confidence=f.confidence,
            access_count=f.access_count,
            status=f.status.value if hasattr(f.status, "value") else str(f.status),
            superseded_by_id=f.superseded_by_id,
            created_at=f.created_at.isoformat(),
            updated_at=f.updated_at.isoformat(),
        )
        for f in facts
    ]


@app.get("/superseded")
def get_superseded_audit(user_id: str = "default_user"):
    """Fetch all superseded facts to inspect contradiction resolution audit trail."""
    all_facts = companion.store.get_all_facts(user_id)
    superseded = [f for f in all_facts if f.status == MemoryStatus.SUPERSEDED]
    return {
        "count": len(superseded),
        "superseded_facts": [
            {
                "id": f.id,
                "fact_text": f.fact_text,
                "category": f.category.value if hasattr(f.category, "value") else str(f.category),
                "superseded_by_id": f.superseded_by_id,
                "created_at": f.created_at.isoformat(),
                "updated_at": f.updated_at.isoformat(),
            }
            for f in superseded
        ]
    }


@app.get("/profile")
def get_user_profile(user_id: str = "default_user"):
    """Get structured user profile attributes synchronized with active memories."""
    prof = companion.store.get_user_profile(user_id)
    active_facts = companion.store.get_active_facts(user_id)
    if active_facts:
        prof.pets = []  # Reset pets so superseded pets are not retained
        # Process in chronological order
        chronological_facts = sorted(active_facts, key=lambda f: f.created_at)
        prof = companion.extractor.update_profile_from_facts(prof, chronological_facts)
        companion.store.save_user_profile(prof)
    return prof.model_dump(mode="json")


@app.post("/inspect")
def inspect_retrieval(req: InspectRequest):
    """Test retrieval scoring and ranking breakdown for a hypothetical query."""
    retrieved = companion.retriever.retrieve(query=req.query, user_id=req.user_id, top_k=req.top_k)
    return {
        "query": req.query,
        "results_count": len(retrieved),
        "retrieved_memories": [
            {
                "id": m.id,
                "fact_text": m.fact_text,
                "category": m.category.value if hasattr(m.category, "value") else str(m.category),
                "importance": m.importance,
                "access_count": m.access_count,
            }
            for m in retrieved
        ]
    }


@app.post("/reset")
def reset_memory(req: ResetRequest):
    """Wipe all memory and dialogue turns for the user."""
    companion.store.clear_all_memory(req.user_id)
    return {"status": "success", "message": f"Memory cleared for user: {req.user_id}"}


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8001, reload=True)
