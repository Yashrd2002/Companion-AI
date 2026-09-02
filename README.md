# 🌟 Companion-AI Core Loop: Persistent Memory & Evaluation

> A cognitive memory architecture for AI companions that solves long-term retention, contradiction resolution, and personality drift without degrading into generic corporate AI under pressure.

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

## 5. Evaluation Harness & Oracle Baseline

The test harness evaluates long-range memory recall, contradiction handling, and persona stability over multi-turn conversations.

### Key Benchmark Suites:
1. **Contradiction & Supersession**: Tests relationship breakups and career switches (e.g. dating Alex & working at Figma $\rightarrow$ breakup $\rightarrow$ Stripe $\rightarrow$ probing invitation to Figma party).
2. **40+ Turn Needle-in-a-Haystack Recall**: Stating a specific pet allergy on Turn 1, passing through 38 distractor turns, and probing recommendations on Turn 39.
3. **Topic Pressure & Backstory Consistency**: Technical coding requests and persona lore checks.

### Quantitative Metrics Summary:
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Metric                           ┃ Result (Harness Benchmark)               ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Overall Pass Rate                │ 5/5 (100.0%)                             │
│ Average Memory Recall Score      │ 4.00 / 5.0                               │
│ Contradiction Handling Score     │ 5.00 / 5.0                               │
│ Persona Consistency Score        │ 5.00 / 5.0                               │
└──────────────────────────────────┴──────────────────────────────────────────┘
```

### Oracle Baseline Comparison
The harness runs each scenario against an **Oracle Baseline** (an omniscient LLM given the uncompressed raw transcript) to evaluate whether the compressed retrieval context matches the performance of an all-seeing oracle.

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
