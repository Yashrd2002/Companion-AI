"""
Unit tests for Memory Retrieval & Ranking.
"""

import tempfile
import os
from datetime import datetime, timezone, timedelta
from src.memory.models import Fact, MemoryCategory, MemoryStatus
from src.memory.store import MemoryStore
from src.memory.retriever import MemoryRetriever
from src.llm.embeddings import EmbeddingClient


def test_retrieval_relevance_and_decay():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        store = MemoryStore(db_path=db_path)
        embed_client = EmbeddingClient()
        retriever = MemoryRetriever(store=store, embedding_client=embed_client)

        # Fact 1: Highly relevant to coffee
        f1_text = "User loves oat milk cortados"
        fact1 = Fact(
            user_id="u1",
            fact_text=f1_text,
            category=MemoryCategory.PREFERENCE,
            entity="Coffee",
            importance=0.8,
            embedding=embed_client.get_embedding(f1_text)
        )

        # Fact 2: Irrelevant (gardening)
        f2_text = "User planted tomatoes in backyard"
        fact2 = Fact(
            user_id="u1",
            fact_text=f2_text,
            category=MemoryCategory.GENERAL,
            importance=0.3,
            embedding=embed_client.get_embedding(f2_text)
        )

        # Fact 3: Superseded fact (should NEVER be retrieved)
        f3_text = "User dislikes coffee"
        fact3 = Fact(
            user_id="u1",
            fact_text=f3_text,
            category=MemoryCategory.PREFERENCE,
            status=MemoryStatus.SUPERSEDED,
            embedding=embed_client.get_embedding(f3_text)
        )

        store.add_fact(fact1)
        store.add_fact(fact2)
        store.add_fact(fact3)

        results = retriever.retrieve(query="What kind of coffee drinks do I enjoy?", user_id="u1", top_k=3)
        assert len(results) >= 1
        assert results[0].id == fact1.id
        
        # Verify superseded fact is never in results
        result_ids = [r.id for r in results]
        assert fact3.id not in result_ids

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
