# 0003. MUD Command Routing, Social DSL, Custom Host Commands/Emotes, Languages & Diegetic Comms

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #3 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **MUD Command Routing, Social DSL, Custom Host Commands/Emotes, Languages & Diegetic Comms** in Meddah: The Universal Story Engine.

## Decision
**Two-Tier Command Router + Rich Roleplay DSL (`mud_social_dsl.py`) + Host-Created Custom MUD Commands & Emotes (`custom_commands.py`) + Diegetic Languages (`LanguageBlock`) + Communication Mediums (`CommunicationMediumBlock`)**: Standard MUD commands (`look`, `n/s/e/w`, `inventory`, `use <action>`, `roll`), **Core In-Game & OOC Communication** (`say`/`'`, `say to`/`to <target>`, `whisper <target>` [with non-interrupting passive/stance `Eavesdrop` checks], `shout`/`yell` [1–2 hop room bleed + dungeon alert ticks], `tell`/`ooc`/`//`, `act`/`emote`/`:`/`::`), **Mixed Action + Speech Interleaving**, **Vocal Prosody Emphasis** (`(tone)`, `*italics*`, `**bold**`, `...` pauses), **60+ Parameterized 3-Perspective Social Emotes with Semantic Valence Tagging**, **Host-Created Custom MUD Commands, Declarative `ECA` Action Chains & Custom Emotes (`CustomMudCommandBlock` & `CustomEmoteBlock`)** (allowing the Host or authorized GM to define custom 3-perspective social emotes and custom MUD commands wired to a 4-step sandboxed declarative `ECA` pipeline—*1. AST Precondition & Cost Gate $\rightarrow$ 2. Optional Skill Check / Contested Prompt / Table Roll $\rightarrow$ 3. Ordered Deterministic Payloads [3-perspective text/SFX/VFX, condition/pool/inventory updates, room contraption/clock/portal triggers, or handout/drawer popups] $\rightarrow$ 4. Optional Interruptible Channeling Condition*—with zero arbitrary code execution, plus player shorthand `> alias` macros and live `/` autocomplete sync), **Ruleset-Grounded Diegetic Languages, Dialects, Written Scripts & Secret Cants (`LanguageBlock`)** (per-seat fluency wire-filtering across `Fluent`, `Partial/Dialect`, and `Non-Speaker` phonetic ciphers + dual-layer *Thieves' Cant*), AND **Ruleset/World-Defined Diegetic Communication Mediums** (*Tactical Radio / Subspace Frequencies* with a **Three-Tier Alias Registry**, *Telepathic / Hive-Mind / Patron Links*, *Spell / Artifact Channels*, *Aetherchannels / Matrix / BBS Networks*, *Public Broadcasts*, and *Asynchronous Physical Couriers*, governed by per-medium `audibility_mode`, **Vocal/Somatic/Mental Condition Gating**, **Sealed-Helmet Isolation + Optional/Fine-Grained Suit PA Voice Modulation [`VoiceModulatorProfile`: `clean_natural`, `loud_hailer`, `booming_resonance`, `scrambled_anonymous`, `voice_mimic`]** & **`#vacuum`/`touch-helmet` Physics**, and a **Unified Comms & Channels Pill Bar**) resolve deterministically in `<5ms` (`0` LLM calls).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
