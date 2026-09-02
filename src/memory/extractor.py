"""
Memory Extraction Engine for Companion-AI.
Analyzes user inputs, extracts memory-worthy facts, classifies categories,
and assigns importance and confidence scores.
"""

from __future__ import annotations
import json
import re
from typing import List, Optional
from datetime import datetime, timezone

from src.memory.models import Fact, MemoryCategory, MemoryStatus, UserProfile
from src.llm.client import LLMClient, llm_client
from src.llm.embeddings import EmbeddingClient


EXTRACTION_SYSTEM_PROMPT = """You are an expert cognitive memory extraction system for an AI companion.
Your mission is to extract all discrete, long-term memory-worthy facts from the user's latest statement.

### What is Memory-Worthy?
- Personal identity, relationships (e.g. dating status, partner names, breakups, friends, family members).
- Work, career status, company names, projects, major goals.
- Enduring preferences, tastes, dietary restrictions, allergies.
- Key life events, routines, pets (and their specific traits/allergies).
- Significant emotional milestones or values.

### What is NOT Memory-Worthy?
- Fleeting greetings, conversational fillers ("hello", "thanks", "how are you").
- Temporary transient actions ("I'm looking at my screen right now", "Let me check the time").
- Questions asked by the user with no personal disclosure.

### Output Format (Strict JSON):
Return a JSON object with a key "facts", containing a list of objects with:
- "fact_text": Clear, declarative statement summarizing the fact in 3rd person (e.g. "User's sister has a dog named Boba who is allergic to chicken").
- "category": One of ["relationship", "career", "preference", "event", "opinion", "routine", "emotion", "family_and_pets", "general"].
- "entity": Specific primary entity if applicable (e.g. "Alex", "Figma", "Boba", "Coffee") or null.
- "attribute": Key attribute if applicable (e.g. "relationship_status", "occupation", "dietary_restriction") or null.
- "value": Concise attribute value (e.g. "broken up / single", "Product Designer", "allergic to chicken") or null.
- "importance": Float between 0.0 (minor detail) and 1.0 (life-defining event).
- "confidence": Float between 0.0 and 1.0 indicating factual certainty.

If no memory-worthy facts exist, return {"facts": []}.
"""


class MemoryExtractor:
    """Extracts structured facts from user dialogue turns."""

    def __init__(self, llm: Optional[LLMClient] = None, embedding_client: Optional[EmbeddingClient] = None):
        self.llm = llm or llm_client
        self.embedding_client = embedding_client or EmbeddingClient()

    def extract_facts(self, user_message: str, user_id: str = "default_user", turn_index: Optional[int] = None) -> List[Fact]:
        """Extract memory facts from a single user message."""
        if not user_message or len(user_message.strip()) < 3:
            return []

        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": f"USER MESSAGE:\n\"{user_message}\"\n\nExtract facts:"}
        ]

        raw_response = self.llm.chat_completion(
            messages=messages,
            temperature=0.1,
            max_tokens=600,
            response_format="json"
        )

        extracted_data = self._parse_json_response(raw_response)
        facts: List[Fact] = []

        if not extracted_data or "facts" not in extracted_data:
            return facts

        for item in extracted_data["facts"]:
            try:
                fact_text = item.get("fact_text", "").strip()
                if not fact_text:
                    continue

                category_str = item.get("category", "general").lower()
                category = MemoryCategory(category_str) if category_str in [c.value for c in MemoryCategory] else MemoryCategory.GENERAL
                
                importance = float(item.get("importance", 0.5))
                confidence = float(item.get("confidence", 1.0))
                entity = item.get("entity")
                attribute = item.get("attribute")
                value = item.get("value")

                # Compute dense embedding for vector similarity
                embedding = self.embedding_client.get_embedding(fact_text)

                fact = Fact(
                    user_id=user_id,
                    fact_text=fact_text,
                    category=category,
                    entity=entity,
                    attribute=attribute,
                    value=value,
                    importance=min(max(importance, 0.0), 1.0),
                    confidence=min(max(confidence, 0.0), 1.0),
                    source_turn_index=turn_index,
                    embedding=embedding,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    last_accessed_at=datetime.now(timezone.utc)
                )
                facts.append(fact)
            except Exception as e:
                # Ignore malformed item and continue
                continue

        return facts

    def update_profile_from_facts(self, profile: UserProfile, facts: List[Fact]) -> UserProfile:
        """Update structured high-signal user profile attributes deterministically."""
        for fact in facts:
            text_lower = fact.fact_text.lower()

            # 1. User Name
            if fact.attribute and fact.attribute.lower() in ("name", "user_name", "full_name") and fact.value:
                profile.name = fact.value
            elif "name is " in text_lower:
                m = re.search(r"(?:user'?s?\s+name\s+is|my\s+name\s+is|called)\s+([a-zA-Z]+)", fact.fact_text, re.I)
                if m:
                    profile.name = m.group(1).strip()

            # 2. Career
            if fact.category == MemoryCategory.CAREER:
                if fact.value:
                    profile.occupation = fact.value
                elif fact.entity:
                    profile.occupation = f"Works at {fact.entity}"
                elif "job offer at" in text_lower or "works at" in text_lower:
                    m = re.search(r"(?:at|for)\s+([a-zA-Z\s]+)", fact.fact_text, re.I)
                    if m:
                        profile.occupation = f"Works at {m.group(1).strip().rstrip('.,!')}"

            # 3. Relationship & Status Updates
            if any(w in text_lower for w in ("broke up", "breakup", "broken up", "single", "divorced", "split up", "separated")):
                profile.relationship_status = "Single"
                profile.partner_name = None
            elif ("dating" in text_lower or "in a relationship" in text_lower or "partner" in text_lower) and not any(w in text_lower for w in ("broke up", "ex-")):
                profile.relationship_status = "Dating"
                if fact.entity:
                    profile.partner_name = fact.entity
                elif fact.value:
                    profile.partner_name = fact.value
                else:
                    m = re.search(r"(?:dating|with)\s+([a-zA-Z]+)", fact.fact_text, re.I)
                    if m:
                        profile.partner_name = m.group(1).strip()

            # 4. Pets & Family
            elif fact.category == MemoryCategory.FAMILY_AND_PETS:
                # Check if pet passed away / died
                is_deceased = any(w in text_lower for w in ("died", "passed away", "dead", "lost", "put down", "no longer have"))
                pet_name = fact.entity or fact.value
                if not pet_name:
                    # Try to extract name from text
                    m = re.search(r"(?:dog|cat|pet|rescue)?\s*(?:named|called|is)?\s*([a-zA-Z]+)\s*(?:has died|died|passed away)", fact.fact_text, re.I)
                    if m:
                        pet_name = m.group(1).strip()

                if pet_name:
                    clean_name = pet_name.strip().title()
                    # If deceased, remove from active pets
                    if is_deceased:
                        profile.pets = [p for p in profile.pets if p.lower() != clean_name.lower()]
                    else:
                        # Add only if not already in list (case-insensitive)
                        if not any(p.lower() == clean_name.lower() for p in profile.pets):
                            profile.pets.append(clean_name)

            # 5. Preferences
            elif fact.category == MemoryCategory.PREFERENCE:
                key = fact.entity or "General"
                val = fact.value or fact.fact_text
                profile.key_preferences[key] = val

            # 6. Location
            elif fact.attribute and fact.attribute.lower() in ("location", "city", "lives_in"):
                profile.location = fact.value

        profile.updated_at = datetime.now(timezone.utc)
        return profile

    def _parse_json_response(self, text: str) -> dict:
        """Robust JSON extraction from LLM output."""
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            pass

        # Match markdown ```json ``` codeblock
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass

        # Try to find outer braces
        m2 = re.search(r"(\{.*\})", text, re.DOTALL)
        if m2:
            try:
                return json.loads(m2.group(1))
            except Exception:
                pass

        return {"facts": []}
