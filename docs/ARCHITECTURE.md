# Architecture

## High-Level System

The system is divided into 6 layers.

### 1. GUI Layer
- map display
- narrative panel
- input box
- stats (hunger, health, etc.)
- clock
- inventory

### 2. Orchestrator (Game Loop)
Handles each player action:
- receives input
- triggers simulation tick
- coordinates all systems
- builds LLM context

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

## Core Loop

1. Player input
2. Intent parsing
3. Deterministic simulation
4. Narrative decision
5. Context compression
6. LLM generation
7. State update
8. Wait for next input

## Key Rule

> The system decides what is true. The LLM decides how it is presented.
