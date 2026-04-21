# V1 Vision

## Goal

Build a playable vertical slice proving that:
- deterministic simulation and OpenAI storyteller realization can coexist
- deterministic social state can drive flexible NPC dialogue
- a dynamic story bible can be maintained
- a GUI can present a coherent experience
- players can speak and act naturally without learning command syntax
- the project does not need hand-authored deterministic dialogue for every possible utterance

## Scope

### Map
- 1 district
- 6-10 nodes

### Player
- 1 character
- basic stats (hunger, health, willpower)

### NPCs
- 3-5 unique NPCs
- each with distinct social profiles, knowledge, goals, and topic sensitivities

### Systems
- time progression
- movement
- hunger system
- simple inventory
- dice system
- deterministic social resolution
- bounded intent extraction
- OpenAI dialogue and scene realization

### Story
- 1 short chronicle arc
- 1 main hook
- 1 ending
- topic-gated clue progression

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
- no sprawling hand-authored dialogue tree for every NPC utterance

## Success Criteria

The system is successful if:
- player input is interpreted into consistent world-state updates
- time advances correctly
- social checks and consequences remain deterministic
- LLM dialogue remains consistent with state and social outcome packets
- NPCs feel distinct and flexible
- the same NPC can respond naturally to varied phrasing without bespoke scripting for every line
- story progresses toward an ending without losing state authority

## Player Experience

The player should be able to write thoughts, intentions, descriptive actions, and dialogue in ordinary language. The engine then resolves that input into deterministic simulation and social outcomes, and OpenAI realizes those outcomes as natural narration and dialogue.

Example:

> "I feel disturbed by the environment. I take a look around to see if something is wrong."

Under the hood:
- the engine interprets this as a search or perception intent
- it checks location state, visible entities, and active triggers
- it applies the relevant deterministic rule if a test is needed
- the resulting state change is recorded before narration is generated

Example:

> "You're hiding something. Tell me what happened here."

Under the hood:
- the engine treats this as a social pressure attempt against a topic
- it resolves the NPC's response mode from deterministic social variables and topic gates
- it resolves any social check, attitude shift, or clue reveal deterministically
- the LLM presents the exchange as natural dialogue, but does not decide the outcome

## Guiding Principle

> Anything that must be correct is deterministic. Anything expressive is realized by the LLM from structured outcomes after the simulation has resolved.
