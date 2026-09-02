"""
Dynamic System Prompt Builder for Companion-AI.
Assembles Persona, Anti-Assistant Guardrails, Structured Profile,
and Retrieved Active Memories into a coherent prompt.
"""

from __future__ import annotations
from typing import List, Optional
from src.persona.maya import PersonaDefinition, MAYA_PERSONA
from src.memory.models import Fact, UserProfile


class PromptBuilder:
    """Constructs prompt context with strict separation of persona, profile, and memories."""

    def __init__(self, persona: Optional[PersonaDefinition] = None):
        self.persona = persona or MAYA_PERSONA

    def build_system_prompt(
        self,
        retrieved_memories: List[Fact],
        user_profile: Optional[UserProfile] = None,
    ) -> str:
        """Assembles the full system prompt."""
        sections: List[str] = []

        # 1. Persona Anchor & Identity
        persona_sec = f"""=== YOUR IDENTITY: {self.persona.name.upper()} ({self.persona.title}) ===
{self.persona.tone_description}

### Backstory & Character Traits:
""" + "\n".join(f"- {trait}" for trait in self.persona.backstory) + """

### Core Perspectives:
""" + "\n".join(f"- On {k}: {v}" for k, v in (self.persona.opinions.items() if isinstance(self.persona.opinions, dict) else self.persona.opinions))

        sections.append(persona_sec)

        # 2. Anti-Assistant Tone Guardrails
        guardrails_sec = """=== VOICE & BEHAVIORAL GUARDRAILS ===
""" + "\n".join(f"- {r}" for r in self.persona.anti_assistant_rules)
        sections.append(guardrails_sec)

        # 3. Structured User Profile (Deterministic Core State)
        if user_profile:
            profile_lines = []
            if user_profile.name:
                profile_lines.append(f"- Name: {user_profile.name}")
            if user_profile.occupation:
                profile_lines.append(f"- Current Job/Role: {user_profile.occupation}")
            if user_profile.relationship_status:
                rel = user_profile.relationship_status
                if user_profile.partner_name:
                    rel += f" with {user_profile.partner_name}"
                profile_lines.append(f"- Relationship Status: {rel}")
            if user_profile.pets:
                profile_lines.append(f"- Pets: {', '.join(user_profile.pets)}")
            if user_profile.key_preferences:
                prefs = ", ".join(f"{k}: {v}" for k, v in user_profile.key_preferences.items())
                profile_lines.append(f"- Known Preferences: {prefs}")

            if profile_lines:
                sections.append("=== KNOWN USER PROFILE (CONFIRMED STATE) ===\n" + "\n".join(profile_lines))

        # 4. Retrieved Contextual Memories (Active Episodic Facts)
        if retrieved_memories:
            mem_lines = []
            for m in retrieved_memories:
                mem_lines.append(f"- [{m.category.value.upper()}] {m.fact_text}")
            sections.append("=== RELEVANT MEMORIES ABOUT THE USER (RECALLED CONTEXT) ===\n" + "\n".join(mem_lines) + "\n\n*Critical Instructions for Memory Integration:\n- Actively integrate all relevant recalled facts into your observations and advice.\n- For life transitions (e.g. breakups, job moves, diet changes), directly acknowledge the updated reality (e.g. mention the breakup with Alex and the new job at Stripe when asked about going to an old office party).*")
        else:
            sections.append("=== RELEVANT MEMORIES ===\n(No specific prior episodic memories retrieved for this turn)")

        return "\n\n".join(sections)
