# Architecture Decision Records (ADRs)

Architectural decisions, trade-offs, and design modifications for **Meddah** are recorded in this directory as immutable Markdown records.

## Governance Rules

1. **Numbering Scheme**:
   - `0000-template.md`: Standard ADR template.
   - `0001`–`0050`: Locked Architectural Decisions from [`docs/design/system_design_specification.md`](../design/system_design_specification.md).
   - `0051`–`0127`: Grill-Me Resolutions (`0050 + Resolution #`) from [`docs/design/technical_specification_and_plan.md`](../design/technical_specification_and_plan.md).
   - `0128+`: Golden Rule ADRs and subsequent implementation decisions.
2. **Immutability & Superseding**: Accepted ADRs are never silently altered or deleted. To revise an accepted decision, create a new ADR (`NNNN-new-decision.md`) referencing `Supersedes ADR-XXXX`, and update the old ADR's header to `Status: Superseded by ADR-NNNN`.
3. **Phase Definition of Done**: Any PR altering system architecture must include its accompanying ADR update.
