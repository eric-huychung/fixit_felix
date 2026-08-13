# Agent notes

Product law for this repo lives in `.cursor/rules/` and `docs/`. Start at [`docs/README.md`](docs/README.md); the binding scope document is [`docs/product/PRD.md`](docs/product/PRD.md). Skills live in `.cursor/skills/`, cheat sheet in `.cursor/README.md`.

## Before you change anything

Felix's deliverable is a **measured pass-rate number**, not a feature set. Changes that grow the build without moving that number are out of scope by default — see the non-goals in the PRD.

## Safety invariants

These are enforced by tests; do not weaken them to make a change land.

1. `scan` and `diagnose` are read-only. `SalesforceClient` rejects `POST`/`PATCH`/`DELETE`.
2. `felix eval` is the sole writer, and only through `OpportunityWriter` holding an explicit `WriteCapability`.
3. All SOQL goes through `felix/salesforce/soql.py`. Never interpolate a name into a query.
4. Artifact paths go through `ArtifactStore`. Never join a user-supplied string onto a path.
5. Record data never reaches the LLM — formula text, field names, and error messages only.

Full statement and reporting process: [`SECURITY.md`](.github/SECURITY.md).

## Checks

```bash
./scripts/check.sh                 # lint + tests + web typecheck/lint/build
./scripts/check.sh --python-only   # skip web
```

Conventions and PR expectations: [`CONTRIBUTING.md`](.github/CONTRIBUTING.md).

## Agent skills

### Issue tracker

GitHub Issues via `gh` CLI (`eric-huychung/fixit_felix`). See [`docs/agents/issue-tracker.md`](docs/agents/issue-tracker.md).

### Domain docs

See [`docs/agents/domain.md`](docs/agents/domain.md).
