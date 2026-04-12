# VtM AI Storyteller

## Project Overview

This project is a GUI-based single-player Vampire: The Masquerade (VtM) storytelling application.

The system combines:
- deterministic simulation (world state, time, rules)
- narrative control (story structure and pressure)
- LLM-based presentation (scene description, narration, and dialogue feel)

The player-facing goal is to make the experience feel natural-language-first:
- players can write thoughts, intentions, descriptive actions, and dialogue in their own words
- the engine interprets that freeform input into deterministic actions and state changes
- the underlying world state remains the source of truth
- LLMs shape the presentation, not the authority over what is true
- NPC interaction should feel like real dialogue while still resolving through structured simulation rules

The system should behave like this:

> The world is simulated deterministically, and the LLM renders that world as a personalized chronicle.

## Player Experience

The surface interaction should feel expressive and conversational, not like a command parser.

### Player-facing input
- natural language
- thoughts and internal reactions
- intentions and plans
- descriptive actions
- spoken dialogue to NPCs

### Engine-facing resolution
- structured interpretation of what the player likely meant
- deterministic action selection
- rule-based checks, rolls, and consequences
- state updates applied to the world model
- narrative output generated after the state is settled

### Examples

Player input:

> "I feel disturbed by the environment. I take a look around to see if something is wrong."

Underlying resolution:
- the engine treats this as an investigation / look-around intent
- it checks the current location, visible entities, and relevant triggers
- if needed, it resolves a perception or awareness test using deterministic rules
- it updates state only if the investigation reveals something concrete
- the LLM then narrates the result in tone and style

Player input:

> "You're hiding something. Tell me what happened here."

Underlying resolution:
- the engine interprets this as a dialogue challenge or interrogation attempt
- it resolves any social checks, trust changes, or clue reveals using deterministic rules
- the NPC's disposition, knowledge, and schedule determine what can actually be said
- the LLM renders the exchange as natural dialogue, but the state change comes from the simulation

## Core Principles

1. The LLM is **not** the source of truth.
2. All world state is deterministic and structured.
3. The LLM shapes narration and dialogue feel after resolution, but does not author state.
4. Each player input triggers a simulation "tick" after interpretation.
5. The system must converge toward meaningful story outcomes.

## Tech Stack (v1)

- Backend: Python
- GUI: PySide6 (Qt for Python)
- Storage: JSON / SQLite
- LLM: Local model (primary), OpenAI API (optional fallback)

## Version 1 Goal

A vertical slice where the player can:
- move around a small map
- interact with a few NPCs
- hold natural dialogue with NPCs
- experience one short chronicle arc
- see time, hunger, and state change
- receive narrated scenes via LLM
