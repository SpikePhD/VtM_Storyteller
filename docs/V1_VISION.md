# V1 Vision

## Goal

Build a playable vertical slice proving that:
- deterministic simulation and LLM narration can coexist
- a dynamic story bible can be maintained
- a GUI can present a coherent experience

## Scope

### Map
- 1 district
- 6–10 nodes

### Player
- 1 character
- basic stats (hunger, health, willpower)

### NPCs
- 3–5 unique NPCs

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
- input box
- stats display
- clock

## Non-Goals

- no audio
- no large world
- no full VtM ruleset
- no advanced graphics

## Success Criteria

The system is successful if:
- player actions consistently update world state
- time advances correctly
- LLM narration remains consistent with state
- NPCs feel distinct
- story progresses toward an ending

## Guiding Principle

> Anything that must be correct is deterministic. Anything expressive is handled by the LLM.
