# 0004. Multimodal Hooks & 4-Bus Client Audio Engine

- **Date**: 2026-11-23
- **Status**: Accepted
- **Deciders**: Maintainers, Architecture Design Session
- **Related Issues / Decisions**: Architectural Decision #4 (`docs/design/system_design_specification.md`)

## Context & Problem Statement
Architectural design constraint and domain resolution for **Multimodal Hooks & 4-Bus Client Audio Engine** in Meddah: The Universal Story Engine.

## Decision
**Optional Pluggable Providers + 4-Bus Web Audio Director (`audio_mixer/` & `SpatialAudioFilter.ts`)**: Pluggable hooks for **AI Image Generation** (Procedural Layered SVGs default in `Tier A`/`Tier B` + optional ComfyUI/A1111/Imagen/DALL-E), **Multi-Voice TTS** (local `Piper`/`Kokoro` ~100–300MB default in `Tier B` + optional XTTS/ElevenLabs/OpenAI, or OS Speech / **Retro CRPG Text-Blip Synth** / Silent Subtitles in `Tier A`), and **4-Bus Client Audio (`Music`, `Ambience`, `SFX`, `Voice`)** featuring: **(1) Live GM Soundboard & Custom Playlist DJ** (local `MP3/OGG/FLAC/WAV/OPUS` + `.m3u` import, Reactive Auto-DJ mood crossfading with TTS ducking, Manual GM DJ override with `[Dramatic Cut to Silence]`, and 1-click programmable SFX pads `> sfx <tag>`); **(2) Diegetic In-Room Emitters, 1-Hop Door Low-Pass Occlusion & Room/Helmet Acoustic DSP** (bards, jukeboxes, and radios sound muffled `~350 Hz` 1 room away through a closed door and sweep open when opened, plus room reverb presets and `#sealed_helmet`/`#vacuum` attenuation); **(3) Player-Broadcast Audio Clips & Bard Performances (`PlayerAudioBroadcaster.ts`)** (abilities, spells, and items bind customizable sound clips via `audio_clip_ref` in the Capabilities Deck with a Sound Binding Picker, authoritatively stored on the Host system under `.rpgcampaign/media/audio/player_clips/` with progressive peer caching, triggered via MUD `> play <clip_id>` or inline `> act [audio: <clip>] "..."` performance emotes, propagating diegetically in-room with 1-hop closed door low-pass occlusion and `#vacuum`/`#silence` gating, protected by Host table policies [`allow_player_audio`], automatic `-14 LUFS` EBU R128 loudness normalization, anti-spam concurrency caps, and per-player client volume/mute controls); and **(4) Independent Per-Player 4-Bus Mixer & Comfort Guards** (local volume/mute autonomy, local Voice vs. Text-Blip toggle, Night-Mode Dynamic Range Compression, and tinnitus-ringing suppression).

## Consequences
### Positive
- Establishes an explicit, version-controlled architectural boundary aligned with Meddah's 4 Golden Rules.

### Negative / Trade-offs
- Requires strict adherence to schema validation, determinism, and modularity contracts during implementation.

### Neutral
- Recorded as part of the initial baseline architecture; revisions require a superseding ADR.

## Compliance & Verification
Enforced by phase DoD suites (`pytest -m zero_ai`, `tools/lint_agnosticism.py`, `tools/lint_modularity.py`, and `import-linter`) as implementation lands.
