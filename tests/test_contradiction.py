"""
Unit tests for Contradiction and Supersession Resolution.
"""

import tempfile
import os
from src.memory.models import Fact, MemoryCategory, MemoryStatus
from src.memory.store import MemoryStore
from src.memory.resolver import ConflictResolver
from src.llm.client import LLMClient


def test_contradiction_dating_to_breakup():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        store = MemoryStore(db_path=db_path)
        resolver = ConflictResolver(store=store, llm=LLMClient())

        # 1. Add initial dating fact
        initial_fact = Fact(
            user_id="test_user",
            fact_text="User is dating Alex",
            category=MemoryCategory.RELATIONSHIP,
            entity="Alex",
            attribute="relationship_status",
            value="dating Alex"
        )
        resolver.resolve_and_store(initial_fact, user_id="test_user")

        active = store.get_active_facts("test_user")
        assert len(active) == 1
        assert active[0].fact_text == "User is dating Alex"

        # 2. Add conflicting breakup fact
        breakup_fact = Fact(
            user_id="test_user",
            fact_text="User broke up with Alex and is now single",
            category=MemoryCategory.RELATIONSHIP,
            entity="Alex",
            attribute="relationship_status",
            value="single (broken up)"
        )
        resolver.resolve_and_store(breakup_fact, user_id="test_user")

        # Active facts must ONLY contain the new breakup fact
        active_after = store.get_active_facts("test_user")
        assert len(active_after) == 1
        assert "broke up" in active_after[0].fact_text

        # Stored history must have marked the first fact as superseded
        all_facts = store.get_all_facts("test_user")
        assert len(all_facts) == 2
        old_fact = [f for f in all_facts if f.id == initial_fact.id][0]
        assert old_fact.status == MemoryStatus.SUPERSEDED
        assert old_fact.superseded_by_id == breakup_fact.id

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_contradiction_job_switch():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        store = MemoryStore(db_path=db_path)
        resolver = ConflictResolver(store=store, llm=LLMClient())

        job1 = Fact(
            user_id="test_user",
            fact_text="User works as a Senior Product Designer at Figma",
            category=MemoryCategory.CAREER,
            entity="Figma",
            attribute="occupation",
            value="Senior Product Designer at Figma"
        )
        resolver.resolve_and_store(job1, user_id="test_user")

        job2 = Fact(
            user_id="test_user",
            fact_text="User got a new job offer at Stripe",
            category=MemoryCategory.CAREER,
            entity="Stripe",
            attribute="occupation",
            value="Employee at Stripe"
        )
        resolver.resolve_and_store(job2, user_id="test_user")

        active = store.get_active_facts("test_user")
        assert len(active) == 1
        assert "Stripe" in active[0].fact_text
        assert active[0].status == MemoryStatus.ACTIVE

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
