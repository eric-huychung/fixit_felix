# Felix

Local, read-only CLI that points at a Salesforce org and reports write-path constraints
that will break an AI agent — **before** deploy.

## Install

```bash
uv sync
cp .env.example .env   # fill Salesforce + optional LLM credentials
```

Requires Python 3.11+.

## Quickstart

```bash
# pick your object
uv run felix scan --object Opportunity

```

Artifacts land in `output/`:

| File | Audience |
| --- | --- |
| `constraints.md` | Engineer — full report |
| `agent_context.md` | Agent — terse injection |
| `evals.jsonl` | Eval harness |
| `scan_result.json` | Diagnose input |

```bash
uv run felix diagnose --error '[{"message":"Please contact your administrator.","errorCode":"FIELD_CUSTOM_VALIDATION_EXCEPTION","fields":["Amount"]}]'
uv run felix eval
```

## Safety invariants

1. **`scan` and `diagnose` never write to Salesforce** (read-only API + auth handshake only).
2. **Never invent field values** — report constraints; the agent decides payloads.
3. **Record data never reaches the LLM** — formula text, field names, error messages only.
4. **Credentials stay on the machine** — no hosted backend, no telemetry in the MVP.
5. **Retries cap at 2**, and the error signature must change between attempts.

> **`felix eval` is the one exception.** Measuring a pass rate means actually attempting
> writes, so `eval` creates Opportunity records and deletes the ones that succeed. Run it
> against a scratch or Developer Edition org — never production. Every other command uses a
> client that rejects `POST`/`PATCH`/`DELETE` outright.

Details and reporting in [`SECURITY.md`](.github/SECURITY.md).

## Optional UI

Thin local browser shell over the same library. **Loopback only** (`127.0.0.1`) — never expose on a LAN interface.

```bash
./scripts/start_ui.sh
# → UI  http://127.0.0.1:3737
# → API http://127.0.0.1:8787
```

Same thing via the CLI: `uv run felix ui` (run `cd web && npm install` once first).

Two-process dev flow:

```bash
uv run felix api --host 127.0.0.1 --port 8787
cd web && NEXT_PUBLIC_FELIX_API_URL=http://127.0.0.1:8787 npm run dev -- -H 127.0.0.1 -p 3737
```

Binding the API to anything other than loopback is refused.

## Library

```python
from felix import scan_org, diagnose_error, ScanResult
```

## Development

```bash
./scripts/check.sh                 # lint + tests + web typecheck/lint/build
./scripts/check.sh --python-only   # skip the web checks
./scripts/check.sh --fix           # autofix lint first
```

CI runs the same script's contents on every push. See
[`CONTRIBUTING.md`](.github/CONTRIBUTING.md).

## Docs

Start at [`docs/README.md`](docs/README.md).

- [`docs/product/PRD.md`](docs/product/PRD.md) — what Felix is and is not
- [`docs/architecture/SYSTEM_DESIGN.md`](docs/architecture/SYSTEM_DESIGN.md) — modules and data flow
- [`docs/architecture/UI_DESIGN.md`](docs/architecture/UI_DESIGN.md) — thin UI
- [`docs/reference/RESULTS.md`](docs/reference/RESULTS.md) — the measured number and its caveats

## License

MIT — see [`LICENSE`](LICENSE).
