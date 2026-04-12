# V1 Vision

## Goal

Build a playable vertical slice proving that:
- deterministic simulation and LLM narration can coexist
- a dynamic story bible can be maintained
- a GUI can present a coherent experience
- players can speak and act naturally without learning command syntax

## Scope

### Map
- 1 district
- 6-10 nodes

### Player
- 1 character
- basic stats (hunger, health, willpower)

### NPCs
- 3-5 unique NPCs

### Systems
- time progression
- movement
- hunger system
- simple inventory
- dice system

### Story
- 1 short chronicle arc
- 1 main hook (e.g., letter delivery)
- 1 ending

### GUI
- map panel
- narrative panel
- natural-language input box
- stats display
- clock

## Non-Goals

- no audio
- no large world
- no full VtM ruleset
- no advanced graphics

## Success Criteria

The system is successful if:
- player input is interpreted into consistent world-state updates
- time advances correctly
- LLM narration remains consistent with state
- NPCs feel distinct
- story progresses toward an ending

## Player Experience

The player should be able to write thoughts, intentions, descriptive actions, and dialogue in ordinary language. The engine then resolves that input into deterministic simulation results.

Example:

> "I feel disturbed by the environment. I take a look around to see if something is wrong."

Under the hood:
- the engine interprets this as a search or perception intent
- it checks location state, visible entities, and any active triggers
- it applies the relevant deterministic rule if a test is needed
- the resulting state change is recorded before narration is generated

Example:

> "You're hiding something. Tell me what happened here."

Under the hood:
- the engine treats this as a dialogue-driven social pressure attempt
- it resolves any social check, attitude shift, or clue reveal deterministically
- NPC knowledge, disposition, and current scene state determine the response
- the LLM presents the exchange as natural dialogue, but does not decide the outcome

## Guiding Principle

> Anything that must be correct is deterministic. Anything expressive is handled by the LLM after the simulation has resolved.
