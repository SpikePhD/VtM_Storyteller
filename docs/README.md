# VtM AI Storyteller

## Project Overview

This project is a GUI-based single-player Vampire: The Masquerade storytelling application.

The system combines:
- deterministic backend truth (world state, time, rules, checks, consequences)
- deterministic social state (relationship, trust, hostility, secrecy, topic gating, willingness)
- OpenAI storyteller realization (scene description, NPC dialogue, tone, atmosphere, and storyteller feel)

The player-facing goal is to make the experience feel natural-language-first:
- players can write thoughts, intentions, descriptive actions, and dialogue in their own words
- the engine interprets that freeform input into bounded structured intent
- the world state remains the source of truth
- LLMs shape interpretation within bounded schemas and realize the final presentation, but they do not own truth
- NPC interaction should feel flexible and human, without requiring the project to hand-author deterministic dialogue for every possible utterance

The system should behave like this:

> The world is simulated deterministically, and the LLM realizes that world as a personalized chronicle.

## Player Experience

The surface interaction should feel expressive and conversational, not like a command parser and not like a hand-authored keyword tree.

### Player-facing input
- natural language
- thoughts and internal reactions
- intentions and plans
- descriptive actions
- spoken dialogue to NPCs
- flexible follow-up lines within an active conversation

### Engine-facing resolution
- bounded interpretation of what the player likely meant
- deterministic target grounding
- deterministic action selection
- deterministic social evaluation
- rule-based checks, rolls, and consequences
- state updates applied to the world model
- narrative and dialogue output generated after the state is settled

### Dialogue Philosophy

Dialogue should scale through **social simulation**, not through ever-growing deterministic dialogue scripts.

The deterministic layer should own:
- who is present
- what they know
- how they feel about the player
- what topics are sensitive or revealable
- whether they cooperate, refuse, deflect, escalate, or disengage
- whether a social check is required
- whether trust, fear, or plot state changes

The LLM should own:
- the exact phrasing of the NPC's reply
- tone, pacing, subtext, atmosphere, and storyteller voice
- expressive variation that still remains faithful to the structured outcome packet

### Examples

Player input:

> "I feel disturbed by the environment. I take a look around to see if something is wrong."

Underlying resolution:
- the engine treats this as an investigation / look-around intent
- it checks the current location, visible entities, and relevant triggers
- if needed, it resolves a perception or awareness test using deterministic rules
- it updates state only if the investigation reveals something concrete
- the LLM narrates the result after the world state is settled

Player input:

> "You're hiding something. Tell me what happened here."

Underlying resolution:
- the engine interprets this as a social pressure attempt against a topic
- it evaluates the NPC's current predisposition, secrecy, knowledge, and willingness
- it resolves any required social check deterministically
- it applies any state shifts, clue reveals, or refusals deterministically
- the LLM realizes the exchange as natural dialogue, but the state change comes from the simulation

## Core Principles

1. The LLM is **not** the source of truth.
2. All world state and social state are deterministic and structured.
3. The LLM shapes interpretation within bounded schemas and realizes narration after resolution, but does not author state.
4. Each player input triggers a simulation tick after interpretation.
5. The project should scale through deterministic facts and social variables, not through bespoke deterministic dialogue scripting for every utterance.
6. The system must converge toward meaningful story outcomes.

## Tech Stack (v1)

- Backend: Python
- GUI: PySide6 (Qt for Python)
- Storage: JSON / SQLite
- LLM: OpenAI API

## Version 1 Goal

A vertical slice where the player can:
- move around a small map
- interact with a few NPCs
- hold flexible natural dialogue with NPCs
- experience one short chronicle arc
- see time, hunger, and state change
- receive narrated scenes and dialogue via LLM realization grounded in deterministic outcomes
