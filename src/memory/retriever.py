"""
Memory Retrieval Engine for Companion-AI.
Combines semantic vector similarity, keyword/entity overlap, temporal exponential decay,
importance weighting, and reinforcement frequency.
"""

from __future__ import annotations
import math
import re
from datetime import datetime, timezone
from typing import List, Optional
from src.memory.models import Fact, ScoredFact, MemoryStatus
from src.memory.store import MemoryStore
from src.llm.embeddings import EmbeddingClient
from src.config import config


class MemoryRetriever:
    """Retrieves the most contextually relevant, active memories for a dialogue turn."""

    def __init__(
        self,
        store: MemoryStore,
        embedding_client: Optional[EmbeddingClient] = None,
        decay_half_life_hours: float = config.decay_half_life_hours,
        w_sim: float = config.weight_similarity,
        w_rec: float = config.weight_recency,
        w_imp: float = config.weight_importance,
        w_freq: float = config.weight_frequency,
    ):
        self.store = store
        self.embedding_client = embedding_client or EmbeddingClient()
        self.decay_half_life_hours = decay_half_life_hours
        # Decay constant lambda = ln(2) / half_life_hours
        self.decay_lambda = math.log(2) / max(self.decay_half_life_hours, 1.0)
        self.w_sim = w_sim
        self.w_rec = w_rec
        self.w_imp = w_imp
        self.w_freq = w_freq

    def retrieve(
        self,
        query: str,
        user_id: str = "default_user",
        top_k: int = config.max_retrieved_memories,
        min_score: float = config.min_similarity_threshold,
    ) -> List[Fact]:
        """
        Retrieve the top-K highest scoring active memories for the given query.
        Updates access counts and returns list of Fact objects.
        """
        active_facts = self.store.get_active_facts(user_id=user_id)
        if not active_facts or not query.strip():
            return []

        query_embedding = self.embedding_client.get_embedding(query)
        now = datetime.now(timezone.utc)
        scored_facts: List[ScoredFact] = []

        query_tokens = set(re.findall(r"\b\w{3,}\b", query.lower()))

        for fact in active_facts:
            # 1. Semantic Similarity
            sim_score = 0.0
            if fact.embedding:
                sim_score = self.embedding_client.cosine_similarity(query_embedding, fact.embedding)
            
            # Keyword / entity lexical boost
            fact_text_lower = fact.fact_text.lower()
            fact_tokens = set(re.findall(r"\b\w{3,}\b", fact_text_lower))
            overlap = len(query_tokens.intersection(fact_tokens))
            if overlap > 0:
                sim_score = min(1.0, sim_score + 0.15 * overlap)

            # Entity exact match boost
            if fact.entity and fact.entity.lower() in query.lower():
                sim_score = min(1.0, sim_score + 0.25)

            # 2. Temporal Recency Decay
            # Age in hours
            age_hours = max(0.0, (now - fact.created_at).total_seconds() / 3600.0)
            recency_score = math.exp(-self.decay_lambda * age_hours)

            # 3. Importance
            importance_score = fact.importance

            # 4. Access Frequency
            # Scaled log frequency
            frequency_score = min(1.0, math.log2(1 + fact.access_count) / 3.0)

            # Composite Score
            final_score = (
                self.w_sim * sim_score
                + self.w_rec * recency_score
                + self.w_imp * importance_score
                + self.w_freq * frequency_score
            )

            # Only include if similarity indicates some contextual relevance
            if sim_score >= min_score or (fact.entity and fact.entity.lower() in query.lower()):
                scored_facts.append(
                    ScoredFact(
                        fact=fact,
                        final_score=final_score,
                        similarity_score=sim_score,
                        recency_score=recency_score,
                        importance_score=importance_score,
                        frequency_score=frequency_score
                    )
                )

        # Rank by final score descending
        scored_facts.sort(key=lambda sf: sf.final_score, reverse=True)
        top_scored = scored_facts[:top_k]

        # Record access in storage for retrieved facts
        retrieved_ids = [sf.fact.id for sf in top_scored]
        self.store.record_access(retrieved_ids)

        return [sf.fact for sf in top_scored]
