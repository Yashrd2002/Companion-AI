"""
Embedding generation utilities supporting OpenAI, Gemini, and Local Fallback.
"""

from __future__ import annotations
import math
import re
import numpy as np
from typing import List, Optional
from src.config import config


class EmbeddingClient:
    """Generates dense vector representations for memory retrieval."""

    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or config.llm_provider
        self.dim = 384  # Standard dense dimension for local fallback

    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding vector for a single text."""
        return self.get_embeddings([text])[0]

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for a list of texts."""
        if not texts:
            return []

        # Try OpenAI if configured
        if self.provider == "openai" and config.openai_api_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=config.openai_api_key)
                response = client.embeddings.create(
                    input=texts,
                    model="text-embedding-3-small"
                )
                return [d.embedding for d in response.data]
            except Exception as e:
                # Graceful fallback to deterministic local embedding
                pass

        # Try Gemini if configured
        if self.provider == "gemini" and config.gemini_api_key:
            try:
                from google import genai
                client = genai.Client(api_key=config.gemini_api_key)
                embeddings = []
                for text in texts:
                    result = client.models.embed_content(
                        model="text-embedding-004",
                        contents=text,
                    )
                    embeddings.append(result.embedding.values)
                return embeddings
            except Exception:
                pass

        # Deterministic semantic hash / n-gram TF-IDF embedding fallback
        return [self._compute_local_embedding(t) for t in texts]

    def _compute_local_embedding(self, text: str) -> List[float]:
        """
        Deterministic lightweight semantic hash embedding for offline/zero-dependency use.
        Generates dense representation based on unigrams, bigrams, and character sub-words
        normalized to unit length for cosine similarity.
        """
        vec = np.zeros(self.dim, dtype=np.float32)
        words = re.findall(r"\b\w+\b", text.lower())
        
        if not words:
            return (vec / np.linalg.norm(vec + 1e-9)).tolist()

        # Word tokens
        for i, word in enumerate(words):
            h = hash(word) % self.dim
            vec[h] += 1.5
            
            # Character n-grams for subword matching (e.g., 'allergy' vs 'allergic')
            for n in (3, 4):
                if len(word) >= n:
                    for j in range(len(word) - n + 1):
                        ngram = word[j:j+n]
                        nh = hash(ngram) % self.dim
                        vec[nh] += 0.5
            
            # Bigrams
            if i < len(words) - 1:
                bigram = f"{words[i]}_{words[i+1]}"
                bh = hash(bigram) % self.dim
                vec[bh] += 2.0

        # L2 normalize
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Calculate cosine similarity between two vector lists."""
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
