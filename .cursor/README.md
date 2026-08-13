# Cursor agent config (Felix)

How this repo wires Cursor. Keep **rules** always-on; use **skills** as on-demand workflows.

## Layout

```text
.cursor/
├── README.md          ← this file
├── rules/             ← always-on product + coding law
└── skills/            ← optional workflows (slash / auto when relevant)
```

| Path | Role |
|------|------|
| `.cursor/rules/` | Always loaded. Product scope, safety, coding standards, collaboration. |
| `.cursor/skills/` | Loaded when invoked (`/skill-name`) or when the agent decides they match. |

Do **not** put skills under `.agents/` in this repo — we standardize on `.cursor/skills/`.

## Rules (keep these)

- `rules/specification/product.mdc` — Felix scope + safety invariants
- `rules/collaboration.mdc` — architect-first, ask vs implement
- `rules/coding-practices/*` — Python / TS / testing / production principles
- `rules/api/salesforce.mdc` — Salesforce API conventions

Rules are the product bible. Do not replace them with Matt Pocock skills.

## Skills installed

From [mattpocock/skills](https://github.com/mattpocock/skills):

| Skill | When to use |
|-------|-------------|
| `grill-me` | Align on a plan/design before coding |
| `to-spec` | After alignment: write a feature spec → publish to issue tracker |
| `tdd` | Implement with red → green → refactor |
| `improve-codebase-architecture` | Periodic architecture health check |
| `setup-matt-pocock-skills` | **Once per repo** — wire tracker + domain docs |

### Suggested flow

```text
/grill-me  →  /to-spec  →  /tdd  →  (every few days) /improve-codebase-architecture
```

### Name clash to remember

- `docs/product/PRD.md` = Felix **product** PRD (source of truth)
- `/to-spec` output = **feature-sized** specs in the issue tracker — do not overwrite `docs/product/PRD.md`

## How to use skills in chat

1. Type `/` in Agent chat → pick the skill, **or** say “use grill-me on …”
2. Skills with `disable-model-invocation: true` only run when you invoke them (setup is one of these)

## Add / update skills later

```bash
# Browse
npx skills find <keyword>

# Install into this project for Cursor (then move if CLI drops into .agents/)
npx skills@latest add <owner/repo> --skill <name> -a cursor -y

# Prefer landing here
# .cursor/skills/<skill-name>/SKILL.md

# Update installed packs
npx skills update
```

If the installer writes to `.agents/skills/`, move into `.cursor/skills/` and delete `.agents/`.

## Setup files (written by `/setup-matt-pocock-skills`)

- `AGENTS.md` (repo root) — pointers for engineering skills
- `docs/agents/issue-tracker.md` — GitHub Issues via `gh` (`eric-huychung/fixit_felix`)
- `docs/agents/domain.md` — single-context `CONTEXT.md` + `docs/adr/`

Later (lazy): `CONTEXT.md`, `docs/adr/` — shared domain language. They do **not** replace `docs/product/PRD.md` / `docs/architecture/SYSTEM_DESIGN.md`.

Prerequisite for publishing specs: `brew install gh && gh auth login`.
