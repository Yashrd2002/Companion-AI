"""
Configuration module for Companion-AI Core Loop.
Handles environment variables, default model providers, decay constants,
and retrieval thresholds.
"""

from __future__ import annotations
import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env file from project root if it exists
load_dotenv()

ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class AppConfig(BaseModel):
    # LLM Settings
    llm_provider: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "mock"))
    model_name: str = Field(default_factory=lambda: os.getenv("MODEL_NAME", "gpt-4o-mini"))
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=800)

    # API Keys
    openai_api_key: str | None = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    anthropic_api_key: str | None = Field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    gemini_api_key: str | None = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))

    # Database & Storage
    db_path: str = Field(default_factory=lambda: os.getenv("DB_PATH", str(DATA_DIR / "companion_memory.db")))

    # Memory Decay & Scoring Weights
    # Half-life for temporal decay in hours (e.g. 72 hours = 3 days)
    decay_half_life_hours: float = Field(default=72.0)
    
    # Weight parameters for retrieval scoring:
    # Score = w_sim * cosine_sim + w_rec * decay_score + w_imp * importance + w_freq * freq_score
    weight_similarity: float = Field(default=0.50)
    weight_recency: float = Field(default=0.20)
    weight_importance: float = Field(default=0.20)
    weight_frequency: float = Field(default=0.10)

    # Retrieval Thresholds
    max_retrieved_memories: int = Field(default=5)
    min_similarity_threshold: float = Field(default=0.15)
    
    # Short-Term Dialogue Working Memory (turns to keep in immediate window)
    short_term_window_turns: int = Field(default=8)


config = AppConfig()
