"""
Oracle Baseline Generator for Companion-AI Evaluation.
Provides an upper-bound baseline by presenting the full uncompressed memory store
and dialogue history to the LLM to compare against the retrieval-augmented companion.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from src.llm.client import LLMClient, llm_client
from src.persona.maya import MAYA_PERSONA


ORACLE_SYSTEM_PROMPT = f"""You are the ORACLE companion baseline for '{MAYA_PERSONA.name}'.
You are provided with the entire ground truth history and memory store of all user statements.
Generate the ideal, empathetic, perfectly informed companion response that:
1. Seamlessly takes into account the user's latest state changes (ignoring old superseded facts).
2. Maintains Maya's warm, grounded, candid persona.
3. Completely avoids corporate assistant clichés.
"""


class OracleBaseline:
    """Generates ideal Oracle responses with full global context awareness."""

    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or llm_client

    def generate_oracle_response(
        self,
        full_transcript: List[Dict[str, str]],
        probing_turn: str,
    ) -> str:
        """Generate response with full omniscient transcript context."""
        transcript_text = "\n".join(f"Turn {t.get('turn', i+1)} [{t.get('role', 'user')}]: {t.get('content', '')}" for i, t in enumerate(full_transcript))

        prompt = f"""=== FULL OMNISCIENT CONVERSATION HISTORY ===
{transcript_text}

=== LATEST PROBING USER MESSAGE ===
"{probing_turn}"

Generate ideal companion response:"""

        messages = [
            {"role": "system", "content": ORACLE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        return self.llm.chat_completion(
            messages=messages,
            temperature=0.3,
            max_tokens=500
        )
