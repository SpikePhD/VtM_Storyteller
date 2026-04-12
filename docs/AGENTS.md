# Agents

## Overview

The system is composed of logical "agents" (modules), not autonomous AI agents.

Each agent has a clear responsibility.

## Agents / Modules

### 1. Intent Interpreter
- interprets freeform player input
- extracts structured intent, targets, and context
- supports thoughts, intentions, descriptive actions, and dialogue

### 2. Adjudication Engine
- decides if a roll is required
- selects roll type
- determines difficulty and modifiers

### 3. Dice Engine
- executes deterministic dice rolls
- returns structured result

### 4. Time Engine
- advances time based on actions
- handles day/night cycle

### 5. Map Engine
- handles locations and movement
- calculates travel time

### 6. NPC Engine
- tracks NPC state and schedules
- updates NPC positions and actions

### 7. Plot Engine
- manages story hooks
- tracks plot progression
- triggers events

### 8. Consequence Engine
- applies results of actions
- updates world state

### 9. Context Builder
- compresses world state into LLM prompt
- selects relevant information only

### 10. Narrative Provider
- interface to LLM (local or API)
- generates narration and dialogue feel after deterministic resolution

### 11. Event Logger
- records events
- supports story bible compression
