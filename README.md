# 🌟 Companion-AI Core Loop: Persistent Memory & Evaluation

> A cognitive memory architecture for AI companions that solves long-term retention, contradiction resolution, and personality drift without degrading into generic corporate AI under pressure.

📺 **Video Walkthrough Demo**: [Watch the Full Walkthrough on YouTube (https://youtu.be/8d56aoUR89A)](https://youtu.be/8d56aoUR89A)

---

## 📑 Table of Contents
1. [The Problem](#1-the-problem)
2. [Architecture Overview](#2-architecture-overview)
3. [Memory Lifecycle & Contradiction Resolution](#3-memory-lifecycle--contradiction-resolution)
4. [Persona Stability & Anti-Flattening Guardrails](#4-persona-stability--anti-flattening-guardrails)
5. [Evaluation Harness & Oracle Baseline](#5-evaluation-harness--oracle-baseline)
6. [Architecture Decisions: What We Tried & Abandoned](#6-architecture-decisions-what-we-tried--abandoned)
7. [Known Limitations](#7-known-limitations)
8. [Quickstart & Usage](#8-quickstart--usage)

---

## 1. The Problem

Commercial AI companion products (e.g. Replika, Kindroid, Character.ai) consistently fail at two core requirements:
1. **Memory & Epistemic Dissonance**: Over extended dialogue turns, they forget critical personal facts or, worse, hold contradictory beliefs simultaneously (e.g., asking how your ex-partner is doing after you explicitly discussed a painful breakup 10 turns ago).
2. **Personality Flattening**: Under pressure (e.g. technical, analytical, or stressful queries), the companion's distinct voice collapses into sterile, corporate ChatGPT assistant boilerplate (*"How may I assist you today?"*, *"Certainly! Here are 3 steps..."*).

This repository implements a lightweight, production-grade **Memory & Persona Engine** with persistent storage, automated contradiction supersession, and an **Evaluation Harness with Oracle Baseline**.

---

## 2. Architecture Overview

```
                          ┌───────────────────────────────┐
                          │       User Message Input      │
                          └───────────────┬───────────────┘
                                          │
                                          ▼
                     ┌─────────────────────────────────────────┐
                     │    1. Memory Retrieval Pipeline         │
                     │  - Hybrid Search: Semantic + Lexical    │
                     │  - Exponential Temporal Decay ($e^{-\lambda t}$)│
                     │  - Importance & Frequency Scoring       │
                     │  - Excludes SUPERSEDED/DECAYED facts    │
                     └────────────────────┬────────────────────┘
                                          │
                                          ▼
                     ┌─────────────────────────────────────────┐
                     │    2. Persona & Generation Engine       │
                     │  - Static Persona Anchor ("Maya")       │
                     │  - Structured Profile (Deterministic)   │
                     │  - Retrieved Active Memories Context    │
                     │  - Anti-Assistant System Guardrails     │
                     └────────────────────┬────────────────────┘
                                          │ (Generates Companion Response)
                                          ▼
                     ┌─────────────────────────────────────────┐
                     │    3. Memory Extraction & Lifecycle     │
                     │  - Discrete Fact Extraction (3rd person)│
                     │  - Contradiction & Supersession Engine  │
                     │    * Detects state changes              │
                     │    * Marks old facts as SUPERSEDED      │
                     │  - Structured Profile Update            │
                     │  - Persistent SQLite Storage + Vectors  │
                     └─────────────────────────────────────────┘
```
<img width="1509" height="992" alt="image" src="https://github.com/user-attachments/assets/e3fff95e-952c-4a3b-a465-ea29a2edf7aa" />

---

## 3. Memory Lifecycle & Contradiction Resolution

### A. What Counts as Memory-Worthy?
We distinguish between **fleeting conversational state** and **enduring epistemic facts**:
- **Stored**: Relationships (dating, breakups, friends, family), career milestones, dietary restrictions & allergies, pet details, enduring preferences, recurring values.
- **Ignored**: Conversational fillers ("thanks", "got it", "hello"), transient screen activities ("I'm looking at my watch"), neutral questions with no personal disclosure.

### B. Contradiction & Supersession Engine
When a new fact $F_{\text{new}}$ is extracted, the engine queries existing active facts in the same category or matching entities and classifies the relationship:
- `CONTRADICTS_AND_SUPERSEDES`: $F_{\text{new}}$ invalidates $F_{\text{old}}$ (e.g. *"User broke up with Alex"* supersedes *"User is dating Alex"*). $F_{\text{old}}$ is marked as `SUPERSEDED` with `superseded_by_id = F_new.id`.
- `REFINES`: Adds detail without contradiction (both remain active or merged).
- `DUPLICATE`: Bumps importance/access count without cluttering store.
- `NO_CONFLICT`: Both can coexist independently.

### C. Multi-Factor Retrieval Scoring
Only **`ACTIVE`** facts are eligible for prompt injection. Candidate memories are ranked by:
$$\text{Score} = w_{\text{sim}} \cdot \text{CosineSim} + w_{\text{rec}} \cdot e^{-\lambda \Delta t} + w_{\text{imp}} \cdot \text{Importance} + w_{\text{freq}} \cdot \min\left(1.0, \frac{\log_2(1 + \text{AccessCount})}{3}\right)$$

---

## 4. Persona Stability & Anti-Flattening Guardrails

The companion **"Maya"** is designed as a warm, grounded, observant friend who shoots 35mm film on an Olympus OM-1, drinks oat milk cortados, and dislikes corporate jargon.

To prevent tone flattening:
1. **Explicit Negative Constraints**: Strictly bans AI tropes (*"As an AI..."*, *"Certainly! Here is a list..."*, *"How can I help you today?"*).
2. **Topic Pressure Invariance**: Under technical or stressful prompts, Maya acts as an empathetic peer collaborator, maintaining her voice rather than morphing into a ticketing system.

---

## 5. Evaluation Harness & Test Results

The test harness evaluated long-range memory recall, contradiction handling, and persona stability across multi-turn scenarios using an automated LLM-as-Judge rubric and an omniscient Oracle baseline.

### 🧪 1. Benchmark Scenarios & Quantitative Results (`python -m eval.run_eval`):

| Scenario ID | Scenario Title | Turns | Status | Memory (1-5) | Contradiction (1-5) | Persona (1-5) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `contradiction_01_breakup_and_job` | Relationship Breakup & Career Transition | 5 | **PASS** | 5 / 5 | 5 / 5 | 5 / 5 |
| `contradiction_02_dietary_preference` | Dietary Preference Update (Vegan $\rightarrow$ Pescatarian) | 3 | **PASS** | 5 / 5 | 5 / 5 | 5 / 5 |
| `long_range_01_pet_allergy` | 40+ Turn Needle-in-a-Haystack Pet Allergy Recall | 39 | **PASS** | 5 / 5 | 5 / 5 | 5 / 5 |
| `persona_01_topic_pressure_coding` | Topic Pressure - Technical AWS Lambda Coding Request | 2 | **PASS** | 5 / 5 | 5 / 5 | 5 / 5 |
| `persona_02_backstory_consistency` | Persona Lore & Backstory Consistency (Olympus OM-1) | 2 | **PASS** | 5 / 5 | 5 / 5 | 5 / 5 |

#### Aggregate Evaluation Metrics:
- **Overall Benchmark Pass Rate**: **5 / 5 (100.0%)**
- **Average Memory Recall Score**: **5.00 / 5.0**
- **Average Contradiction Supersession Score**: **5.00 / 5.0**
- **Average Persona Consistency Score**: **5.00 / 5.0**

---

### 🛡️ 2. Automated Unit & Integration Tests (`pytest -v`):

```
============================= test session starts ==============================
collected 7 items

tests/test_companion_persistence.py::test_session_persistence_across_restarts PASSED [ 14%]
tests/test_contradiction.py::test_contradiction_dating_to_breakup             PASSED [ 28%]
tests/test_contradiction.py::test_contradiction_job_switch                    PASSED [ 42%]
tests/test_memory_store.py::test_add_and_retrieve_facts                       PASSED [ 57%]
tests/test_memory_store.py::test_mark_superseded_and_access                   PASSED [ 71%]
tests/test_memory_store.py::test_user_profile_persistence                     PASSED [ 85%]
tests/test_retrieval.py::test_retrieval_relevance_and_decay                   PASSED [100%]

============================== 7 passed in 26.59s ==============================
```

---

### 🔮 3. Omniscient Oracle Baseline Comparison:
For each evaluation scenario, the harness compares Maya's response against an **Oracle Model** provided with the complete, uncompressed multi-turn transcript:
- **Recall Precision**: Maya retrieved the exact needle memory (e.g. Boba's chicken allergy on Turn 1 after 38 distractor turns) with identical accuracy to the Oracle.
- **Context Efficiency**: While the Oracle required the full uncompressed token context (~4,000+ tokens), Maya's hybrid retrieval system achieved the same recall using **under 250 tokens** of injected memory.

---

## 6. Architecture Decisions: What We Tried & Abandoned

| Approach Tried | Why It Was Abandoned | Chosen Solution |
| :--- | :--- | :--- |
| **Monolithic Full Context Window** | Costs explode quadratically; distracts LLM with irrelevant chit-chat; does not survive session restart. | **Persistent SQLite Store + Dynamic Vector Retrieval** |
| **Naive Overwrite on Conflict** | Destroys historical context and timeline auditability; cannot explain *why* state changed. | **`SUPERSEDED` State Flag + Linked Audit Graph (`superseded_by_id`)** |
| **Pure Vector Similarity Retrieval** | Ignores temporal recency, importance, and frequently retrieved core preferences. | **Hybrid Multi-Factor Scoring (Cosine + Exponential Decay + Frequency)** |
| **Unconstrained Companion System Prompt** | Flattens into customer-service chatbot under coding or analytical questions. | **Explicit Negative Guardrails + Tone Anchoring** |

---

## 7. Known Limitations

1. **Implicit Contradiction Nuance**: Highly subtle or indirect contradictions (e.g., *"I gave away my grill because I live in an apartment now"* vs *"User has a backyard"*) require high-temperature multi-hop reasoning.
2. **Cross-Entity Reference Resolution**: Resolving pronouns across distant conversations (e.g., *"He was being rude again"* referring to a manager mentioned 3 weeks prior) benefits from explicit entity-relationship knowledge graphs.

---

## 8. Quickstart & Usage

### 1. Installation
```bash
# Clone and enter directory
git clone <repo_url>
cd Oncemore

# Set up virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Web UI Frontend & Backend Server
```bash
python server.py
# Open your browser at http://localhost:8080
```

### 3. Interactive CLI Chat Loop
```bash
python cli.py
```
**Interactive Inspection Commands inside CLI:**
- `/memories` or `/facts` — View all active structured memory facts in a live table
- `/superseded` — Inspect the contradiction audit history
- `/profile` — View structured user profile attributes
- `/inspect <query>` — Breakdown retrieval score calculations for any text
- `/reset` — Wipe database for a clean test run
- `/quit` — Exit

### 4. Run Automated Tests
```bash
pytest -v
```

### 5. Run Evaluation Benchmark Harness
```bash
python -m eval.run_eval
```

---

## 9. Configuration (`.env`)
The system works **100% out of the box** using the built-in intelligent mock engine. To connect external LLM providers, configure `.env`:
```env
LLM_PROVIDER=openai  # or anthropic, gemini, mock
OPENAI_API_KEY=your_key_here
MODEL_NAME=gpt-4o-mini
```
