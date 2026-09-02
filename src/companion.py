"""
Companion Core Loop Orchestrator.
Coordinates memory retrieval, response generation, fact extraction,
contradiction resolution, and session persistence across restarts.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from src.memory.models import Fact, UserProfile
from src.memory.store import MemoryStore
from src.memory.extractor import MemoryExtractor
from src.memory.resolver import ConflictResolver
from src.memory.retriever import MemoryRetriever
from src.persona.maya import PersonaDefinition, MAYA_PERSONA
from src.persona.prompt_builder import PromptBuilder
from src.llm.client import LLMClient, llm_client
from src.llm.embeddings import EmbeddingClient
from src.config import config


class CompanionResponse:
    def __init__(
        self,
        content: str,
        retrieved_memories: List[Fact],
        extracted_facts: List[Fact],
        turn_index: int,
    ):
        self.content = content
        self.retrieved_memories = retrieved_memories
        self.extracted_facts = extracted_facts
        self.turn_index = turn_index


class Companion:
    """The complete, stateful AI companion engine."""

    def __init__(
        self,
        user_id: str = "default_user",
        db_path: Optional[str] = None,
        persona: Optional[PersonaDefinition] = None,
        llm: Optional[LLMClient] = None,
    ):
        self.user_id = user_id
        self.store = MemoryStore(db_path=db_path or config.db_path)
        self.llm = llm or llm_client
        self.embedding_client = EmbeddingClient()
        self.extractor = MemoryExtractor(llm=self.llm, embedding_client=self.embedding_client)
        self.resolver = ConflictResolver(store=self.store, llm=self.llm)
        self.retriever = MemoryRetriever(store=self.store, embedding_client=self.embedding_client)
        self.persona = persona or MAYA_PERSONA
        self.prompt_builder = PromptBuilder(persona=self.persona)

    def chat(self, user_message: str) -> CompanionResponse:
        """
        Executes a complete companion interaction turn:
        1. Retrieve relevant active memories
        2. Build prompt & generate in-character response
        3. Extract new facts & resolve contradictions/supersessions
        4. Persist all state to SQLite
        """
        # Get current turn index
        latest_turn = self.store.get_latest_turn_index(self.user_id)
        current_turn_index = latest_turn + 1

        # 1. Retrieve relevant active memories
        retrieved_memories = self.retriever.retrieve(
            query=user_message,
            user_id=self.user_id,
            top_k=config.max_retrieved_memories
        )

        # Fetch current structured profile and sync with active facts
        user_profile = self.store.get_user_profile(self.user_id)
        active_facts = self.store.get_active_facts(self.user_id)
        if active_facts:
            user_profile.pets = []
            chronological_facts = sorted(active_facts, key=lambda f: f.created_at)
            user_profile = self.extractor.update_profile_from_facts(user_profile, chronological_facts)
            self.store.save_user_profile(user_profile)

        # 2. Build system prompt
        system_prompt = self.prompt_builder.build_system_prompt(
            retrieved_memories=retrieved_memories,
            user_profile=user_profile
        )

        # Get recent dialogue for short-term working context
        recent_turns = self.store.get_recent_dialogue(
            user_id=self.user_id,
            limit=config.short_term_window_turns
        )

        # Construct messages payload
        messages = [{"role": "system", "content": system_prompt}]
        for turn in recent_turns:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": user_message})

        # Generate companion response
        response_content = self.llm.chat_completion(
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens
        )

        # 3. Post-turn memory lifecycle: extract new facts from user statement
        extracted_facts = self.extractor.extract_facts(
            user_message=user_message,
            user_id=self.user_id,
            turn_index=current_turn_index
        )

        stored_fact_ids = []
        for fact in extracted_facts:
            # Resolve potential contradictions and store
            saved_fact = self.resolver.resolve_and_store(fact, user_id=self.user_id)
            stored_fact_ids.append(saved_fact.id)

        # Update structured profile if new facts modify profile attributes
        if extracted_facts:
            updated_profile = self.extractor.update_profile_from_facts(user_profile, extracted_facts)
            self.store.save_user_profile(updated_profile)

        # 4. Record dialogue turns in persistent store
        retrieved_ids = [m.id for m in retrieved_memories]
        self.store.add_dialogue_turn(
            user_id=self.user_id,
            role="user",
            content=user_message,
            turn_index=current_turn_index,
            retrieved_ids=retrieved_ids,
            extracted_ids=stored_fact_ids
        )
        self.store.add_dialogue_turn(
            user_id=self.user_id,
            role="assistant",
            content=response_content,
            turn_index=current_turn_index + 1
        )

        return CompanionResponse(
            content=response_content,
            retrieved_memories=retrieved_memories,
            extracted_facts=extracted_facts,
            turn_index=current_turn_index
        )

    def get_all_memories(self) -> List[Fact]:
        """Audit helper to get all memories for the user."""
        return self.store.get_all_facts(self.user_id)

    def get_active_memories(self) -> List[Fact]:
        """Audit helper to get active memories for the user."""
        return self.store.get_active_facts(self.user_id)

    def get_profile(self) -> UserProfile:
        """Fetch current user profile."""
        return self.store.get_user_profile(self.user_id)

    def reset_memory(self):
        """Clear all stored data for this user."""
        self.store.clear_all_memory(self.user_id)
