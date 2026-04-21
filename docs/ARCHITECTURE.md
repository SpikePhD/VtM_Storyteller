# Architecture

## High-Level System

The system is divided into 7 layers.

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
- runs bounded intent interpretation
- grounds targets against world state
- triggers deterministic simulation and social resolution
- commits state updates before presentation
- builds structured render context after truth is settled

### 3. World State (Source of Truth)
Stores:
- player state
- NPC state
- locations
- inventory
- active plots
- time
- story flags
- social variables and topic knowledge

### 4. Simulation Systems
- time engine
- movement engine
- NPC scheduler
- consequence engine
- hunger system
- plot clocks
- social resolution and topic gating
- check and dice resolution

### 5. Social Resolution Layer
This layer is the core of dialogue gameplay.

It decides:
- what the player is trying to do socially
- how the addressed NPC is predisposed toward the player
- whether the topic is known, sensitive, gated, or taboo
- whether the NPC reveals, refuses, deflects, stalls, threatens, cooperates, or disengages
- whether a social check is required
- which variables shift after the exchange

This layer must remain deterministic and state-authoritative.

### 6. Outcome Packet / Context Layer
Builds compact structured packets for the LLM from settled truth.

Typical fields include:
- resolved action
- target NPC
- social outcome
- topic status
- check result
- consequence summary
- active scene facts
- relevant story-bible context

### 7. LLM Realization Layer
- realizes narration and NPC dialogue from structured packets
- gives the conversation a human storyteller feel
- may improvise phrasing, pacing, and tone
- must not invent world truth, legality, roll outcomes, or plot changes

## Core Loop

1. Player input
2. Bounded natural-language intent extraction
3. Deterministic target grounding
4. Deterministic simulation and social resolution
5. Deterministic checks, rolls, and consequences
6. State update
7. Structured outcome packet build
8. LLM realization
9. Wait for next input

## Interaction Model

The player writes naturally, and the engine resolves that input into testable simulation steps and social outcomes.

### Player-facing surface
- expressive, conversational text
- thoughts, intentions, and descriptive actions
- dialogue spoken to NPCs as if in-character
- flexible back-and-forth that feels improvised

### Engine-facing resolution
- bounded intent extraction
- deterministic grounding
- deterministic social evaluation
- deterministic state changes
- logged outcomes that can be tested and replayed

The important distinction is that the player's text is treated as natural-language input, but the game does **not** scale by hand-authoring deterministic dialogue trees for every utterance.

Instead, the game should scale through:
- deterministic world facts
- deterministic social variables
- deterministic topic and plot gates
- structured outcome packets
- LLM-driven expressive realization

## Key Rule

> The system decides what is true. The LLM decides how that truth is interpreted within bounds and how it is presented.
