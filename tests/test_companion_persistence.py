"""
Integration tests for Companion Persistence Across Process Restarts.
"""

import tempfile
import os
from src.companion import Companion
from src.memory.models import MemoryStatus


def test_session_persistence_across_restarts():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        # Session 1: User discloses personal details
        companion_session_1 = Companion(user_id="persisted_user", db_path=db_path)
        
        turn1 = companion_session_1.chat("Hey Maya, I'm working as a Senior Product Designer at Figma and dating Alex.")
        assert turn1.content
        
        turn2 = companion_session_1.chat("My sister got a rescue dog named Boba who has a severe allergy to chicken.")
        assert turn2.content

        # Verify facts exist in Session 1
        active_1 = companion_session_1.get_active_memories()
        assert len(active_1) >= 2

        # Simulate Process Restart: Destroy instance and instantiate a brand new Companion object
        del companion_session_1

        companion_session_2 = Companion(user_id="persisted_user", db_path=db_path)

        # Verify facts survived restart
        active_2 = companion_session_2.get_active_memories()
        assert len(active_2) >= 2
        fact_texts = [f.fact_text for f in active_2]
        assert any("Figma" in t for t in fact_texts)
        assert any("Boba" in t or "chicken" in t for t in fact_texts)

        # In Session 2, trigger contradiction update
        turn3 = companion_session_2.chat("Alex and I broke up last night. I'm single now.")
        assert turn3.content

        # Re-verify active vs superseded state in database
        all_mems = companion_session_2.get_all_memories()
        superseded = [m for m in all_mems if m.status == MemoryStatus.SUPERSEDED]
        assert len(superseded) >= 1
        assert any("Alex" in s.fact_text for s in superseded)

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
