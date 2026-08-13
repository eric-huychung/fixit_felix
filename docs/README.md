# Felix documentation

What to read, depending on why you're here.

## Using Felix

Start with the [root README](../README.md) — install, quickstart, and the CLI commands.

## Reference

| Doc | What it is |
|-----|------------|
| [`reference/RESULTS.md`](reference/RESULTS.md) | The measured pass-rate delta, with the caveats that qualify it |

## Understanding the design

| Doc | What it is |
|-----|------------|
| [`product/PRD.md`](product/PRD.md) | What Felix is for, who it's for, and what it deliberately is not |
| [`architecture/SYSTEM_DESIGN.md`](architecture/SYSTEM_DESIGN.md) | Module layout, data model, and the safety invariants |
| [`architecture/UI_DESIGN.md`](architecture/UI_DESIGN.md) | The thin local UI over the same library |

## Contributing

See [`CONTRIBUTING.md`](../.github/CONTRIBUTING.md) for setup, the check script, and the
conventions the codebase follows. Security reports go through
[`SECURITY.md`](../.github/SECURITY.md).

## Working documents

`agents/` holds conventions for AI coding agents working in this repo. Ignore it unless
you are configuring one.
