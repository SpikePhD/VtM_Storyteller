# Architecture

## High-Level System

The system is divided into 6 layers.

### 1. GUI Layer
- map display
- narrative panel
- natural-language input box
- stats (hunger, health, etc.)
- clock
- inventory

### 2. Orchestrator (Game Loop)
Handles each player input:
- receives freeform text from the player
- interprets the input into structured intent and action candidates
- triggers the deterministic simulation tick
- coordinates all systems
- builds LLM context after the world state is settled

### 3. World State (Source of Truth)
Stores:
- player state
- NPCs
- locations
- inventory
- active plots
- time

### 4. Simulation Systems
- time engine
- movement engine
- NPC scheduler
- consequence engine
- hunger system
- plot clocks

### 5. Narrative Control
- decides scene purpose
- triggers story hooks
- manages pacing and escalation
- enforces endings

### 6. LLM Layer
- narration
- NPC dialogue
- tone and atmosphere
- presentation only, not state authority

## Core Loop

1. Player input
2. Natural-language intent interpretation
3. Deterministic simulation
4. Narrative decision
5. Context compression
6. LLM generation
7. State update
8. Wait for next input

## Interaction Model

The player writes naturally, and the engine resolves that input into testable simulation steps.

### Player-facing surface
- expressive, conversational text
- thoughts, intentions, and descriptive actions
- dialogue spoken to NPCs as if in-character

### Engine-facing resolution
- structured intent extraction
- rule-based adjudication
- deterministic state changes
- logged outcomes that can be tested and replayed

The important distinction is that the player's text is treated as input for interpretation, not as a command syntax they must learn.

## Key Rule

> The system decides what is true. The LLM decides how it is presented.
