"""
Unit tests for Persistent SQLite Memory Storage.
"""

import tempfile
import os
from datetime import datetime, timezone
from src.memory.models import Fact, MemoryCategory, MemoryStatus, UserProfile
from src.memory.store import MemoryStore


def test_add_and_retrieve_facts():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        store = MemoryStore(db_path=db_path)
        fact1 = Fact(
            user_id="user_123",
            fact_text="User works as a Senior Product Designer at Figma",
            category=MemoryCategory.CAREER,
            entity="Figma",
            attribute="occupation",
            value="Senior Product Designer",
            importance=0.8,
            confidence=0.95
        )
        store.add_fact(fact1)

        active = store.get_active_facts("user_123")
        assert len(active) == 1
        assert active[0].fact_text == fact1.fact_text
        assert active[0].entity == "Figma"
        assert active[0].status == MemoryStatus.ACTIVE

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_mark_superseded_and_access():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        store = MemoryStore(db_path=db_path)
        fact_old = Fact(
            user_id="user_123",
            fact_text="User is dating Alex",
            category=MemoryCategory.RELATIONSHIP,
            entity="Alex",
            status=MemoryStatus.ACTIVE
        )
        fact_new = Fact(
            user_id="user_123",
            fact_text="User broke up with Alex and is now single",
            category=MemoryCategory.RELATIONSHIP,
            entity="Alex",
            status=MemoryStatus.ACTIVE
        )
        store.add_fact(fact_old)
        store.add_fact(fact_new)

        # Mark old fact superseded
        store.mark_superseded(old_fact_id=fact_old.id, new_fact_id=fact_new.id)

        # Active facts should only return the new one
        active = store.get_active_facts("user_123")
        assert len(active) == 1
        assert active[0].id == fact_new.id

        # All facts should return both
        all_facts = store.get_all_facts("user_123")
        assert len(all_facts) == 2
        old_stored = [f for f in all_facts if f.id == fact_old.id][0]
        assert old_stored.status == MemoryStatus.SUPERSEDED
        assert old_stored.superseded_by_id == fact_new.id

        # Test access recording
        store.record_access([fact_new.id])
        updated_new = store.get_fact_by_id(fact_new.id)
        assert updated_new.access_count == 1

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_user_profile_persistence():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        store = MemoryStore(db_path=db_path)
        profile = UserProfile(
            user_id="user_abc",
            name="Jordan",
            occupation="Engineer at Stripe",
            relationship_status="Single",
            pets=["Boba (Dog)"],
            key_preferences={"coffee": "Oat milk cortado"}
        )
        store.save_user_profile(profile)

        loaded = store.get_user_profile("user_abc")
        assert loaded.name == "Jordan"
        assert loaded.occupation == "Engineer at Stripe"
        assert loaded.pets == ["Boba (Dog)"]
        assert loaded.key_preferences["coffee"] == "Oat milk cortado"

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
