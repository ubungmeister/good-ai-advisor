# Domain Docs

How engineering skills should consume this repo's domain documentation.

## Before exploring

- Read the root `GLOSSARY.md`, or `GLOSSARY-MAP.md` if present (then read the relevant context glossary).
- Read relevant decisions in `docs/adr/` before proposing changes in that area.
- If these files do not exist, proceed silently. Create them only when domain terms or decisions are resolved through domain modeling.

## Layout

This is a **single-context** repo: keep `GLOSSARY.md` and ADRs under `docs/adr/` at the repository root. Revisit this layout if the repo becomes a true multi-context monorepo.

## Vocabulary and decisions

- Use the glossary's terms in issues, proposals, tests, and refactors; flag a genuine vocabulary gap for domain modeling.
- If output contradicts an existing ADR, identify the ADR and explain why it may need to be reopened rather than silently overriding it.
