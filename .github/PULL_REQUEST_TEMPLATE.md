## Summary

<!-- Concise summary of changes and link to ROADMAP phase ID (e.g., P1.2, P6.4) -->

- **Roadmap Item(s)**: `P...`
- **Related Issue / ADR**:

## Checklist

- [ ] Commit messages follow Conventional Commits (`<type>(<scope>): <summary>`).
- [ ] Zero hardcoded game terms (`HP`, `AC`, `d20`, etc.) added to core or modules (`Golden Rule #1`).
- [ ] Feature works deterministically with `AI_PROVIDER=none` (`0` LLM calls) and passes `pytest -m zero_ai` (`Golden Rule #2`).
- [ ] Any new optional subsystem registers a `MeddahModule` manifest, starts `dormant` without required primitives, ships outcome-altering levers off (`RAW` default), and passes replay round-trip checks (`Golden Rule #4`).
- [ ] Documentation, `ROADMAP.md`, and `docs/adr/` updated if architecture/scope changed.
- [ ] No `.env` or secret files included.
