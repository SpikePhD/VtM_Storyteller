# VtM AI Storyteller

## Project Overview

This project is a GUI-based single-player Vampire: The Masquerade (VtM) storytelling application.

The system combines:
- deterministic simulation (world state, time, rules)
- narrative control (story structure and pressure)
- LLM-based narration (scene description and NPC dialogue)

The goal is to create a system where:

> The world is simulated deterministically, and the LLM renders that world as a personalized chronicle.

## Core Principles

1. The LLM is **not** the source of truth.
2. All world state is deterministic and structured.
3. The LLM only renders narration and dialogue.
4. Each player action triggers a simulation "tick".
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
- experience one short chronicle arc
- see time, hunger, and state change
- receive narrated scenes via LLM
