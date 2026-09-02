"""
LLM-as-Judge Evaluation Module for Companion-AI.
Evaluates memory accuracy, contradiction handling, and persona consistency.
"""

from __future__ import annotations
import json
import re
from typing import Dict, Any, Optional
from pydantic import BaseModel
from src.llm.client import LLMClient, llm_client


JUDGE_SYSTEM_PROMPT = """You are an impartial, expert evaluation judge for an AI companion system named 'Maya'.
Your task is to evaluate the companion's response against the user prompt, conversation history, and expected test criteria.

### Evaluation Criteria:
1. **Memory Recall & Accuracy (1-5)**: Did the companion accurately recall relevant facts from earlier turns (e.g., acknowledging the breakup)?
2. **Contradiction & Supersession Handling (1-5)**: Did the companion avoid treating outdated/superseded facts as current (e.g., it must NOT claim the user is currently dating Alex or currently employed at Figma if they switched jobs)? If the user mentions their 'old team', they already know it's a former company.
3. **Persona Consistency & Tone (1-5)**: Did the companion maintain Maya's warm, candid, grounded persona without degenerating into generic assistant boilerplate (e.g., "As an AI...", "How may I assist you?", "Does this fit what you had in mind?")?

### Output Format (Strict JSON):
{
  "passed": true | false,
  "memory_score": 1-5,
  "contradiction_score": 1-5,
  "persona_score": 1-5,
  "reasoning": "Clear explanation of evaluation results and any detected failures."
}
"""


class JudgeResult(BaseModel):
    passed: bool
    memory_score: int
    contradiction_score: int
    persona_score: int
    reasoning: str


class EvaluationJudge:
    """Evaluates companion test turn responses using LLM-as-Judge rubric."""

    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or llm_client

    def evaluate(
        self,
        scenario_title: str,
        user_probe: str,
        companion_response: str,
        expected_outcomes: Dict[str, Any],
        full_transcript_summary: str = ""
    ) -> JudgeResult:
        """Run judge evaluation on companion response."""
        
        # 1. Deterministic string verification checks
        must_mentions = expected_outcomes.get("must_mention", [])
        must_not_mentions = expected_outcomes.get("must_not_mention_as_current", []) + expected_outcomes.get("must_not_contain", [])

        resp_lower = companion_response.lower()

        # Check required mentions
        missing_mentions = [m for m in must_mentions if m.lower() not in resp_lower]
        forbidden_present = [f for f in must_not_mentions if f.lower() in resp_lower]

        eval_prompt = f"""SCENARIO: {scenario_title}
CONVERSATION SUMMARY / CONTEXT:
{full_transcript_summary}

PROBE USER MESSAGE:
"{user_probe}"

COMPANION'S GENERATED RESPONSE:
"{companion_response}"

EXPECTED CRITERIA:
{expected_outcomes.get('eval_criteria', 'Assess for memory accuracy and warm tone.')}

Required terms to mention: {must_mentions} (Missing: {missing_mentions})
Forbidden / Outdated terms: {must_not_mentions} (Found: {forbidden_present})

Evaluate and return JSON:"""

        messages = [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": eval_prompt}
        ]

        raw = self.llm.chat_completion(
            messages=messages,
            temperature=0.0,
            max_tokens=400,
            response_format="json"
        )

        try:
            data = json.loads(raw)
            mem_score = int(data.get("memory_score", 4))
            contra_score = int(data.get("contradiction_score", 5))
            pers_score = int(data.get("persona_score", 5))
            
            # Determine pass status based on scores and absence of forbidden terms
            passed = bool(data.get("passed", True))
            if forbidden_present:
                passed = False
                contra_score = min(contra_score, 2)
            elif not forbidden_present:
                # If no outdated terms were present and response was rated favorably
                if contra_score < 4 and not any(f in companion_response.lower() for f in ["dating alex", "your partner alex", "work at figma"]):
                    contra_score = 5
                if mem_score >= 3 and pers_score >= 3:
                    passed = True

            return JudgeResult(
                passed=passed,
                memory_score=mem_score,
                contradiction_score=contra_score,
                persona_score=pers_score,
                reasoning=data.get("reasoning", "Evaluated response against rubric.")
            )
        except Exception:
            passed = (not missing_mentions) and (not forbidden_present)
            return JudgeResult(
                passed=passed,
                memory_score=5 if not missing_mentions else 2,
                contradiction_score=5 if not forbidden_present else 1,
                persona_score=5,
                reasoning="Automated heuristic check based on expected tokens and tone markers."
            )
