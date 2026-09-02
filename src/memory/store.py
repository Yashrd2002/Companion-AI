"""
Persistent SQLite Memory Storage for Companion-AI.
Supports fact lifecycle (active, superseded, decayed), dialogue history,
and structured user profile state.
"""

from __future__ import annotations
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any
from src.memory.models import Fact, MemoryCategory, MemoryStatus, UserProfile, DialogueTurn
from src.config import config


class MemoryStore:
    """Manages persistent SQLite storage and indexed access for memories."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database schema tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Facts Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    fact_text TEXT NOT NULL,
                    category TEXT NOT NULL,
                    entity TEXT,
                    attribute TEXT,
                    value TEXT,
                    importance REAL NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_accessed_at TEXT NOT NULL,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    superseded_by_id TEXT,
                    supersedes_id TEXT,
                    source_turn_index INTEGER,
                    embedding TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_facts_user_status ON facts(user_id, status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category)")

            # User Profile Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Dialogue History Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dialogue_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    turn_index INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    retrieved_memory_ids TEXT,
                    extracted_fact_ids TEXT,
                    timestamp TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_dialogue_user ON dialogue_history(user_id, turn_index)")
            conn.commit()

    def add_fact(self, fact: Fact) -> None:
        """Insert or update a fact in the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO facts (
                    id, user_id, fact_text, category, entity, attribute, value,
                    importance, confidence, created_at, updated_at, last_accessed_at,
                    access_count, status, superseded_by_id, supersedes_id,
                    source_turn_index, embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fact.id,
                fact.user_id,
                fact.fact_text,
                fact.category.value if isinstance(fact.category, MemoryCategory) else fact.category,
                fact.entity,
                fact.attribute,
                fact.value,
                fact.importance,
                fact.confidence,
                fact.created_at.isoformat(),
                fact.updated_at.isoformat(),
                fact.last_accessed_at.isoformat(),
                fact.access_count,
                fact.status.value if isinstance(fact.status, MemoryStatus) else fact.status,
                fact.superseded_by_id,
                fact.supersedes_id,
                fact.source_turn_index,
                json.dumps(fact.embedding) if fact.embedding else None
            ))
            conn.commit()

    def get_fact_by_id(self, fact_id: str) -> Optional[Fact]:
        """Fetch a single fact by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM facts WHERE id = ?", (fact_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_fact(row)
        return None

    def get_active_facts(self, user_id: str = "default_user", category: Optional[MemoryCategory] = None) -> List[Fact]:
        """Retrieve all currently active facts for a user."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if category:
                cat_str = category.value if isinstance(category, MemoryCategory) else category
                cursor.execute(
                    "SELECT * FROM facts WHERE user_id = ? AND status = 'active' AND category = ? ORDER BY created_at DESC",
                    (user_id, cat_str)
                )
            else:
                cursor.execute(
                    "SELECT * FROM facts WHERE user_id = ? AND status = 'active' ORDER BY created_at DESC",
                    (user_id,)
                )
            rows = cursor.fetchall()
            return [self._row_to_fact(r) for r in rows]

    def get_all_facts(self, user_id: str = "default_user") -> List[Fact]:
        """Retrieve all facts (active, superseded, decayed) for auditing."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM facts WHERE user_id = ? ORDER BY created_at ASC", (user_id,))
            rows = cursor.fetchall()
            return [self._row_to_fact(r) for r in rows]

    def mark_superseded(self, old_fact_id: str, new_fact_id: str) -> None:
        """Mark an existing fact as superseded by a newer fact."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE facts
                SET status = 'superseded', superseded_by_id = ?, updated_at = ?
                WHERE id = ?
            """, (new_fact_id, now_iso, old_fact_id))
            conn.commit()

    def record_access(self, fact_ids: List[str]) -> None:
        """Bump access count and update last_accessed_at for retrieved facts."""
        if not fact_ids:
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for fid in fact_ids:
                cursor.execute("""
                    UPDATE facts
                    SET access_count = access_count + 1, last_accessed_at = ?
                    WHERE id = ?
                """, (now_iso, fid))
            conn.commit()

    def get_user_profile(self, user_id: str = "default_user") -> UserProfile:
        """Fetch structured user profile or initialize new one."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT profile_json FROM user_profiles WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                data = json.loads(row["profile_json"])
                return UserProfile(**data)
            return UserProfile(user_id=user_id)

    def save_user_profile(self, profile: UserProfile) -> None:
        """Persist structured user profile."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO user_profiles (user_id, profile_json, updated_at)
                VALUES (?, ?, ?)
            """, (
                profile.user_id,
                json.dumps(profile.model_dump(mode="json")),
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()

    def add_dialogue_turn(
        self,
        user_id: str,
        role: str,
        content: str,
        turn_index: int,
        retrieved_ids: Optional[List[str]] = None,
        extracted_ids: Optional[List[str]] = None
    ) -> None:
        """Record dialogue turn to history."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO dialogue_history (
                    user_id, turn_index, role, content, retrieved_memory_ids, extracted_fact_ids, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                turn_index,
                role,
                content,
                json.dumps(retrieved_ids or []),
                json.dumps(extracted_ids or []),
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()

    def get_recent_dialogue(self, user_id: str = "default_user", limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent dialogue turns for short-term working context."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT turn_index, role, content, timestamp
                FROM dialogue_history
                WHERE user_id = ?
                ORDER BY turn_index DESC
                LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()
            # Return in chronological order
            return [{"role": r["role"], "content": r["content"], "turn_index": r["turn_index"]} for r in reversed(rows)]

    def get_latest_turn_index(self, user_id: str = "default_user") -> int:
        """Return the highest turn index in dialogue history."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(turn_index) as max_turn FROM dialogue_history WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row and row["max_turn"] is not None:
                return int(row["max_turn"])
            return 0

    def clear_all_memory(self, user_id: str = "default_user") -> None:
        """Clear memory for a given user (useful for resets/benchmarks)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM facts WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM user_profiles WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM dialogue_history WHERE user_id = ?", (user_id,))
            conn.commit()

    def _row_to_fact(self, row: sqlite3.Row) -> Fact:
        """Convert SQLite row to Fact model."""
        return Fact(
            id=row["id"],
            user_id=row["user_id"],
            fact_text=row["fact_text"],
            category=MemoryCategory(row["category"]),
            entity=row["entity"],
            attribute=row["attribute"],
            value=row["value"],
            importance=float(row["importance"]),
            confidence=float(row["confidence"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            last_accessed_at=datetime.fromisoformat(row["last_accessed_at"]),
            access_count=int(row["access_count"]),
            status=MemoryStatus(row["status"]),
            superseded_by_id=row["superseded_by_id"],
            supersedes_id=row["supersedes_id"],
            source_turn_index=row["source_turn_index"],
            embedding=json.loads(row["embedding"]) if row["embedding"] else None
        )
