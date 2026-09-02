"""
Data models and schemas for the Companion-AI Memory Architecture.
"""

from __future__ import annotations
from enum import Enum
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid


class MemoryCategory(str, Enum):
    RELATIONSHIP = "relationship"
    CAREER = "career"
    PREFERENCE = "preference"
    EVENT = "event"
    OPINION = "opinion"
    ROUTINE = "routine"
    EMOTION = "emotion"
    FAMILY_AND_PETS = "family_and_pets"
    GENERAL = "general"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DECAYED = "decayed"
    RETIRED = "retired"


class Fact(BaseModel):
    """Represents a discrete extracted unit of knowledge about the user."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = "default_user"
    fact_text: str
    category: MemoryCategory = MemoryCategory.GENERAL
    entity: Optional[str] = None
    attribute: Optional[str] = None
    value: Optional[str] = None
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    access_count: int = 0
    status: MemoryStatus = MemoryStatus.ACTIVE
    superseded_by_id: Optional[str] = None
    supersedes_id: Optional[str] = None
    source_turn_index: Optional[int] = None
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "fact_text": self.fact_text,
            "category": self.category.value if isinstance(self.category, MemoryCategory) else self.category,
            "entity": self.entity,
            "attribute": self.attribute,
            "value": self.value,
            "importance": self.importance,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_accessed_at": self.last_accessed_at.isoformat(),
            "access_count": self.access_count,
            "status": self.status.value if isinstance(self.status, MemoryStatus) else self.status,
            "superseded_by_id": self.superseded_by_id,
            "supersedes_id": self.supersedes_id,
            "source_turn_index": self.source_turn_index,
        }


class ConflictType(str, Enum):
    NO_CONFLICT = "no_conflict"
    CONTRADICTS_AND_SUPERSEDES = "contradicts_and_supersedes"
    REFINES = "refines"
    DUPLICATE = "duplicate"


class ConflictResolution(BaseModel):
    """Outcome of resolving a new candidate fact against existing stored facts."""
    resolution_type: ConflictType
    conflicting_fact_id: Optional[str] = None
    explanation: str = ""
    updated_fact_text: Optional[str] = None


class UserProfile(BaseModel):
    """Consolidated structured profile attributes for fast deterministic injection."""
    user_id: str = "default_user"
    name: Optional[str] = None
    occupation: Optional[str] = None
    relationship_status: Optional[str] = None
    partner_name: Optional[str] = None
    location: Optional[str] = None
    pets: List[str] = Field(default_factory=list)
    key_preferences: Dict[str, str] = Field(default_factory=dict)
    key_relationships: Dict[str, str] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DialogueTurn(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    turn_index: int = 0
    retrieved_memory_ids: List[str] = Field(default_factory=list)
    extracted_fact_ids: List[str] = Field(default_factory=list)


class ScoredFact(BaseModel):
    fact: Fact
    final_score: float
    similarity_score: float
    recency_score: float
    importance_score: float
    frequency_score: float
