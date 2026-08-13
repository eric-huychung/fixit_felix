# Contributing to Felix

Thanks for looking. Felix is small on purpose — read this before opening a large PR, because
scope is the thing most likely to get a change rejected.

## What Felix is measured by

The deliverable is a **measured pass-rate delta**, not a feature count. A change that grows
the codebase without moving that number, or without making it easier to trust, is likely out
of scope. [`docs/product/PRD.md`](../docs/product/PRD.md) §4 lists the non-goals; they stay closed
unless there's a reason to reopen them.

## Setup

```bash
git clone https://github.com/eric-huychung/fixit_felix.git
cd fixit_felix
uv sync
cp .env.example .env    # only needed for live-org work
```

You do not need a Salesforce org to develop. The recorded fixtures cover the whole scan path:

```bash
uv run felix scan --fixtures tests/fixtures
```

## Before you push

```bash
scripts/check.sh
```

That runs ruff format and lint, pytest with coverage, and the web typecheck/lint/build — the
same gates CI runs. `scripts/check.sh --fix` applies formatting and lint fixes;
`--python-only` skips the web checks when Node isn't installed.

## Conventions

**Python.** 3.11+, Pydantic v2 for anything crossing a boundary, `typing.Protocol` over ABCs
for swappable dependencies, Google-style docstrings kept to a line or two. Modules stay under
~500 lines and functions under ~30.

**TypeScript.** snake_case for files, variables, and types; PascalCase for React components;
a JSDoc header at the top of every file.

**Tests.** No network in unit tests — every Salesforce interaction runs against recorded
fixtures in `tests/fixtures/` with `respx`. Tests that need a live org are marked
`@pytest.mark.live` and are excluded by default.

**Comments.** Explain a constraint the code can't show. Don't narrate what the next line does.

## Things that need care

Some parts of the codebase carry an invariant. Changing them is fine; changing them without
noticing is not.

- **`felix/salesforce/soql.py`** is the only module that builds query text. Build SOQL anywhere
  else and you reopen an injection hole.
- **`felix/salesforce/client.py`** rejects every non-`GET`. Write access is granted only through
  `grant_write_capability()`, and only the eval harness may call it.
- **`felix/emit/artifacts.py`** owns the output directory. Callers name an artifact; they never
  supply a path.
- **`felix/api.py`** binds to loopback only. Keep it that way.
- **`felix/emit/evalset.py`** decides what the pass rate means. Seeds fitted to a specific org
  belong in `_ORG_SEED_PACK` and must be marked `org_pack`, so results stay honest about how
  much was hand-tuned.

## Pull requests

Keep them focused, explain the "why" in the description, and add a test that fails without the
change. If you're proposing something architectural, open an issue first — it's cheaper to
disagree in prose than in a diff.

## Reporting bugs

Use the issue templates. For anything security-related, follow [`SECURITY.md`](SECURITY.md)
instead of filing publicly.
