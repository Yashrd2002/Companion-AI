"""
Contradiction & Supersession Engine for Companion-AI.
Detects when newly extracted facts invalidate, update, or supersede previous facts,
preventing cognitive dissonance and contradictory retrieval.
"""

from __future__ import annotations
import json
import re
from typing import List, Optional, Tuple
from src.memory.models import Fact, MemoryCategory, MemoryStatus, ConflictResolution, ConflictType
from src.memory.store import MemoryStore
from src.llm.client import LLMClient, llm_client


RESOLVER_SYSTEM_PROMPT = """You are a cognitive contradiction and epistemic supersession resolver for an AI companion.
Your job is to compare a NEW candidate fact about the user against an EXISTING active fact, and decide if there is a factual conflict or state update.

### Conflict Types:
1. "CONTRADICTS_AND_SUPERSEDES": The new fact represents a change in state or directly contradicts the old fact (e.g. "User broke up with Alex" supersedes "User is dating Alex"; "User now works at Stripe" supersedes "User works at Figma"; "User moved to London" supersedes "User lives in New York").
2. "REFINES": The new fact adds more detail to the old fact without invalidating it (e.g. "Alex is a software engineer" refines "User is dating Alex").
3. "DUPLICATE": The new fact states essentially the exact same thing as the old fact.
4. "NO_CONFLICT": Both facts can be simultaneously true and are independent (e.g. "User likes coffee" vs "User likes tea").

### Output Format (Strict JSON):
{
  "resolution": "CONTRADICTS_AND_SUPERSEDES" | "REFINES" | "DUPLICATE" | "NO_CONFLICT",
  "explanation": "Brief explanation of why"
}
"""


class ConflictResolver:
    """Detects and executes contradiction resolution between new facts and stored facts."""

    def __init__(self, store: MemoryStore, llm: Optional[LLMClient] = None):
        self.store = store
        self.llm = llm or llm_client

    def resolve_and_store(self, new_fact: Fact, user_id: str = "default_user") -> Fact:
        """
        Compares new_fact against relevant active facts in the store.
        If contradiction/supersession is found, marks the old fact as superseded.
        Stores the new fact in SQLite.
        """
        # Fetch active candidate facts in the store
        candidate_facts = self.store.get_active_facts(user_id=user_id)
        
        superseded_any = False
        for old_fact in candidate_facts:
            resolution = self._check_conflict(new_fact, old_fact)

            if resolution.resolution_type == ConflictType.CONTRADICTS_AND_SUPERSEDES:
                # Mark old fact as superseded
                self.store.mark_superseded(old_fact_id=old_fact.id, new_fact_id=new_fact.id)
                new_fact.supersedes_id = old_fact.id
                superseded_any = True
                
            elif resolution.resolution_type == ConflictType.DUPLICATE:
                # If duplicate, update old fact's importance and don't add duplicate
                old_fact.importance = max(old_fact.importance, new_fact.importance)
                old_fact.confidence = max(old_fact.confidence, new_fact.confidence)
                self.store.add_fact(old_fact)
                return old_fact

        # Save new fact as active
        self.store.add_fact(new_fact)
        return new_fact

    def _check_conflict(self, new_fact: Fact, old_fact: Fact) -> ConflictResolution:
        """Run conflict analysis using LLM reasoning."""
        # Fast deterministic heuristics for common pattern matches
        new_lower = new_fact.fact_text.lower()
        old_lower = old_fact.fact_text.lower()

        # Relationship break-up check
        if any(w in new_lower for w in ("broke up", "breakup", "broken up", "single", "split", "divorced")) and any(w in old_lower for w in ("dating", "partner", "relationship", "married", "boyfriend", "girlfriend")):
            return ConflictResolution(
                resolution_type=ConflictType.CONTRADICTS_AND_SUPERSEDES,
                conflicting_fact_id=old_fact.id,
                explanation="Breakup statement supersedes prior dating status."
            )

        # Career job switch check
        if ("job offer" in new_lower or "started working" in new_lower or "new job" in new_lower) and ("works as" in old_lower or "working as" in old_lower):
            if new_fact.entity and old_fact.entity and new_fact.entity.lower() != old_fact.entity.lower():
                return ConflictResolution(
                    resolution_type=ConflictType.CONTRADICTS_AND_SUPERSEDES,
                    conflicting_fact_id=old_fact.id,
                    explanation="New job supersedes prior employment."
                )

        # Duplicate check
        if new_lower == old_lower:
            return ConflictResolution(
                resolution_type=ConflictType.DUPLICATE,
                conflicting_fact_id=old_fact.id,
                explanation="Exact duplicate text."
            )

        # LLM based resolution for nuanced cases
        prompt = f"""EXISTING FACT:
"{old_fact.fact_text}" (Category: {old_fact.category.value})

NEW CANDIDATE FACT:
"{new_fact.fact_text}" (Category: {new_fact.category.value})

Analyze conflict:"""

        messages = [
            {"role": "system", "content": RESOLVER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        raw_resp = self.llm.chat_completion(
            messages=messages,
            temperature=0.0,
            max_tokens=250,
            response_format="json"
        )

        try:
            data = json.loads(raw_resp)
            res_str = data.get("resolution", "NO_CONFLICT").lower()
            explanation = data.get("explanation", "")

            if "supersede" in res_str or "contradict" in res_str:
                res_type = ConflictType.CONTRADICTS_AND_SUPERSEDES
            elif "duplicate" in res_str:
                res_type = ConflictType.DUPLICATE
            elif "refine" in res_str:
                res_type = ConflictType.REFINES
            else:
                res_type = ConflictType.NO_CONFLICT

            return ConflictResolution(
                resolution_type=res_type,
                conflicting_fact_id=old_fact.id if res_type != ConflictType.NO_CONFLICT else None,
                explanation=explanation
            )
        except Exception:
            return ConflictResolution(resolution_type=ConflictType.NO_CONFLICT)
