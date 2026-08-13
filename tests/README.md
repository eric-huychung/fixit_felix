# Tests layout

Mirrors `felix/` so you can find the matching tests quickly.

| Path | What it covers |
|------|----------------|
| `fixtures/` | Recorded Salesforce JSON + golden output files (shared; used by CLI `--fixtures`) |
| `helpers.py` | Shared `FIXTURES` path and sample `ScanResult` |
| `integrity/` | Fixture parse/shape checks only |
| `models/` | Pydantic models |
| `config/` | Settings / env loading |
| `cache/` | SQLite cache |
| `llm/` | Provider clients and `build_provider` selection |
| `salesforce/` | Client, describe, validation rules, Apex, SOQL building |
| `scan/` | Scan orchestration |
| `session/` | Session wiring and resource teardown |
| `translate/` | Formula → plain English + translation cache |
| `diagnose/` | Error → constraint matching and the retry guard |
| `emit/` | `constraints.md`, `agent_context.md`, `evals.jsonl`, artifact store |
| `evals/` | Reference agent and the baseline/treatment scoring |
| `api/` | HTTP surface, including the artifact allowlist and CORS |
| `cli/` | `felix scan` wiring (offline fixtures) |

Unit tests stay offline (fixtures + `respx`). Live org tests use `@pytest.mark.live` and are skipped by default.

## Security regression tests

These exist to keep the invariants in [`SECURITY.md`](../.github/SECURITY.md) from silently regressing. Do not delete them without replacing the coverage.

| Invariant | Test |
|-----------|------|
| No SOQL injection through object/rule names | `salesforce/test_soql.py` |
| Read-only client rejects write verbs | `salesforce/test_client.py` |
| Artifacts cannot escape the output directory | `emit/test_artifacts.py`, `api/test_api.py` |
| CORS stays on an explicit allowlist | `api/test_api.py` |
| Record data never reaches the LLM | `translate/test_translate.py` |

## Running

```bash
./scripts/check.sh --python-only   # lint + tests
uv run pytest -q                   # tests only
uv run pytest -q --cov=felix --cov-report=term-missing
```
