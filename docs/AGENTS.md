# Agents

## Overview

The system is composed of logical modules, not autonomous gameplay agents.

The project now treats dialogue as a **deterministic social simulation plus LLM realization**:
- the deterministic layer owns truth, rules, legality, checks, consequences, plot gates, and state mutation
- the LLM owns interpretation within bounded schemas and expressive realization of scenes and dialogue
- the project should avoid scaling through hand-authored deterministic dialogue scripts for every utterance

Each module has a narrow responsibility and should hand structured outputs to the next layer.

## Agents / Modules

### 1. Intent Adapter
- receives freeform player input
- extracts bounded structured intent from natural language
- identifies likely action, target, topic, tone, and social pressure
- may use an LLM, but only to produce schema-bound intent proposals
- must never invent world facts or mutate state

### 2. Target Grounding Engine
- resolves player references against actual world state
- validates locations, NPCs, items, and active conversation focus
- turns interpreted intent into canonical engine-facing actions
- fails safely when target grounding is ambiguous or invalid

### 3. Social Resolution Engine
- evaluates NPC-facing actions against deterministic social state
- owns relationship, trust, hostility, fear, willingness, secrecy, and topic sensitivity
- decides reveal / refuse / deflect / cooperate / escalate / disengage
- decides whether a social check is required
- should scale through social variables and topic rules, not hardcoded dialogue trees

### 4. Adjudication Engine
- decides whether a non-social or social roll is required
- selects roll type
- determines difficulty and modifiers
- emits structured adjudication outcomes

### 5. Dice Engine
- executes deterministic dice rolls
- returns structured results
- remains the sole authority over check success or failure

### 6. Consequence Engine
- applies results of actions and checks
- updates world state deterministically
- records trust shifts, plot progression, story flags, time changes, and other explicit effects

### 7. NPC Engine
- tracks NPC state, schedules, goals, knowledge, and availability
- updates NPC positions and non-player actions
- exposes social facts needed by the Social Resolution Engine

### 8. Plot Engine
- manages story hooks and plot progression
- enforces plot gates and reveal conditions
- exposes story-bible facts that constrain what NPCs can actually say or do

### 9. Time / Map Engine
- advances time based on actions
- handles movement, travel time, and day/night cycle
- provides scene constraints to the simulation

### 10. Outcome Packet Builder
- compresses settled world truth into a structured render packet
- includes only relevant facts for narration and dialogue realization
- prevents the LLM from needing raw unrestricted state

### 11. Dialogue / Narrative Realizer
- turns structured outcome packets into player-facing prose
- may use a local model or API model
- renders tone, atmosphere, NPC voice, and dialogue flow
- must not invent legality, plot progression, check results, or state changes

### 12. Event Logger
- records interpreted intent, adjudication, checks, consequences, and narrative-relevant events
- supports debugging, replayability, and story-bible compression
