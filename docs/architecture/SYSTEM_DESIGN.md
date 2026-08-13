# Felix — System Design

Companion to `PRD.md`. Covers the MVP only: Salesforce, write-path failures, one object.

---

## 1. Data flow

```
                    ┌─────────────────────────────────────────┐
   Salesforce org   │  felix scan                             │
   ───────────────► │                                         │
   (read-only)      │  auth ──► describe ──────┐              │
                    │       └─► tooling: rules ├─► normalize  │
                    │       └─► tooling: apex ─┘      │       │
                    │                                 ▼       │
                    │                          translate      │
                    │                        (LLM, cached)    │
                    │                                 │       │
                    └─────────────────────────────────┼───────┘
                                                      ▼
                        ┌──────────────┬──────────────┬──────────────┐
                        │ constraints  │ agent_context│  evals.jsonl │
                        │    .md       │     .md      │              │
                        │ (engineer)   │  (agent)     │  (harness)   │
                        └──────────────┴──────────────┴──────┬───────┘
                                              │              │
                                              ▼              ▼
                                        felix eval ──► pass-rate delta
                                        felix diagnose ──► remediation
```

Everything runs in one local process. No server, no outbound traffic except to the customer's
org and (on cache miss) the LLM provider.

## 2. Package layout

```
felix/
  cli.py                    # typer app: scan, eval, diagnose, api, ui
  api.py                    # loopback-only FastAPI over the same library
  session.py                # owns one scan's lifetime: auth, cache, llm, output dir
  config.py                 # API version, org creds, model choice, cache path
  models.py                 # all Pydantic types
  cache.py                  # sqlite, keyed by org id
  scan.py                   # orchestrates extraction -> ScanResult
  offline.py                # fixture-backed client for the no-org demo
  llm.py                    # swappable provider interface
  salesforce/
    client.py               # httpx wrapper: auth, rest_get, tooling_query, tooling_get
    soql.py                 # the only place SOQL is built; validates object names
    describe.py             # sobject describe   -> FieldConstraint[]
    validation_rules.py     # Tooling API        -> ValidationRuleConstraint[]
    apex.py                 # Tooling API bodies -> ApexConstraint[]
    errors.py               # SF error response  -> ErrorSignature
  translate.py              # formula -> plain English, cached
  emit/
    artifacts.py            # ArtifactStore: owns the output dir, reads and writes
    report.py               # -> constraints.md
    context.py              # -> agent_context.md
    evalset.py              # -> evals.jsonl, with seed provenance
  evals/
    runner.py               # baseline vs treatment, scoring
    reference_agent.py      # minimal tool-calling agent under test
    writer.py               # the one sanctioned write path (eval harness only)
  diagnose.py               # error -> grounded instruction, retry guard
web/                        # Next.js app served by `felix ui`
tests/
  fixtures/                 # recorded Salesforce JSON + golden files
  helpers.py                # shared FIXTURES path + sample ScanResult
  integrity/                # fixture parse/shape checks
  models/ config/ cache/ scan/ translate/   # mirror top-level felix modules
  salesforce/ emit/ cli/ api/ diagnose/ evals/ session/   # mirror packages
```

### Two seams worth naming

**`salesforce/soql.py`** is the only module that builds query text. Untrusted input — the
`--object` flag, an `object_name` in an HTTP body — reaches SOQL through its validator and
nowhere else, so injection has one place to be prevented rather than three.

**`emit/artifacts.py`** is the only module that resolves a path under the output directory.
Callers name an artifact; the store maps names to paths. Reads outside the root are impossible
by construction rather than by a check at each call site.


## 3. Data model

```python
class FieldConstraint(BaseModel):
    object_name: str
    api_name: str
    label: str
    soap_type: str
    required: bool  # describe: nillable == False and not defaulted
    picklist_values: list[str] = []
    max_length: int | None = None
    reference_to: list[str] = []


class ValidationRuleConstraint(BaseModel):
    id: str
    object_name: str
    name: str
    active: bool
    namespace_prefix: str | None  # set => came from a managed package
    error_message: str
    error_display_field: str | None
    formula: str
    formula_hash: str  # cache key for the translation
    plain_english: str | None = None
    fields_referenced: list[str] = []


class ApexConstraint(BaseModel):
    source_name: str  # class or trigger name
    object_name: str | None
    error_messages: list[str]  # string literals passed to addError()
    excerpt: str
    confidence: Literal["high", "best_effort"]


class EvalCase(BaseModel):
    id: str
    object_name: str
    intent: str  # natural-language task handed to the agent
    seed_payload: dict  # otherwise-valid record
    target_rule_id: str  # the rule a naive agent should trip
    expected_error_fragment: str


class ScanError(BaseModel):
    stage: str  # "describe" | "validation_rules" | "apex" | "translate"
    target: str  # object, rule id, or class name
    message: str


class ScanResult(BaseModel):
    org_id: str
    scanned_at: datetime
    fields: list[FieldConstraint]
    rules: list[ValidationRuleConstraint]
    apex: list[ApexConstraint]
    errors: list[ScanError]  # never silently dropped


class ErrorSignature(BaseModel):
    status_code: int
    error_code: str  # e.g. FIELD_CUSTOM_VALIDATION_EXCEPTION
    field: str | None
    message: str
```

## 4. Extraction

### Describe

`GET /services/data/v{V}/sobjects/{object}/describe`. Yields required fields, types, picklist
values, record types. This tier is cheap and also partly available from Salesforce's own hosted
MCP server, so it is context, not differentiation.

### Validation rules — two passes, mandatory

`ValidationRule.Metadata` carries `errorConditionFormula`, but Salesforce rejects it for
multi-record queries. So:

1. `SELECT Id, ValidationName, Active, ErrorMessage, ErrorDisplayField, NamespacePrefix
    FROM ValidationRule WHERE EntityDefinition.QualifiedApiName = '{object}'`
2. For each id, `GET /tooling/sobjects/ValidationRule/{id}` to obtain `Metadata`.

Field references are pulled out of the formula with a regex over identifier tokens, filtered
against the known field list from describe. Imperfect and adequate — it exists only to tell the
engineer which fields a rule touches.

### Apex — best effort

Query `ApexTrigger` and `ApexClass` bodies, find `addError(` calls, capture the string literal
and surrounding lines. Dynamic and concatenated messages are unrecoverable; those get
`confidence="best_effort"` and are reported as "this trigger can reject writes, message unknown."
Managed-package Apex is not readable at all. Do not overpromise here.

## 5. Formula translation

The only LLM call in the system.

- Input: formula text, the rule's error message, and field labels. **Never record data.**
- Output: one or two sentences of plain English plus the field(s) to change.
- Cached in sqlite by `(rule_id, formula_hash)`. Changing the formula invalidates it; renaming
  the rule does not.
- Runs at scan time, never during `diagnose` when a cached translation exists.

## 6. Output artifacts

**`constraints.md`** — grouped by object, then by field. Each rule shows its name, plain-English
meaning, the raw formula in a collapsed block, and whether it is active or packaged. This is the
handoff document.

**`agent_context.md`** — terse, token-efficient, written for a model rather than a person:

```markdown
## Opportunity — constraints

- `Amount` over 100000 requires `Executive_Sponsor__c` to be set.
- `StageName` = "Closed Won" requires `CloseDate` to be today or earlier.
- `Discount__c` cannot exceed 30 unless `Approval_Status__c` = "Approved".
- Allowed `StageName`: Prospecting, Qualification, Proposal, Negotiation, Closed Won, Closed Lost
```

**`evals.jsonl`** — one `EvalCase` per active rule.

## 7. Eval harness

Two runs over the same cases:

- **Baseline** — the agent gets only the tool schema from describe.
- **Treatment** — the agent additionally gets `agent_context.md`.

Reported per run: pass rate, attempts per success, API calls consumed. Attempts-per-success
matters independently, because Salesforce orgs have hard daily API limits and a thrashing agent
burns them.

The reference agent is deliberately minimal — one tool-calling loop, one `create_opportunity`
tool, retry capped at 2. It is a measuring instrument, not a product.

## 8. Diagnose

1. Parse the Salesforce error into an `ErrorSignature` (status code, error code, field, message).
2. Match against scanned rules — first on `ErrorDisplayField` plus message, then on exact
   `ErrorMessage` text.
3. On a hit, return the cached plain-English instruction.
4. On a miss, fall back to describe-level constraints for the field, clearly labeled as a guess.
5. Retry guard: maximum 2 attempts, and the signature must differ between them. An identical
   signature twice means the enrichment did not help — stop and emit the escalation payload.

The escalation payload names the rule, states why the agent cannot satisfy it, and identifies
what a human must do. Knowing when to quit is a feature.

## 9. Safety invariants

1. Read-only. `GET` only, plus the auth `POST`. `ValidationRule` supports writes — never call them.
   `SalesforceClient._request` raises `ReadOnlyViolation` on any non-`GET`, so this is enforced
   in code rather than by convention.
2. Felix never invents field values. It reports constraints; the agent decides.
3. Record data never reaches the LLM. Only formulas, field names, and error messages.
4. Credentials stay on the machine. No hosted backend, no telemetry.
5. Retries capped at 2 with a changed-signature requirement.
6. All SOQL is built in `salesforce/soql.py`, which validates object names before
   interpolation.
7. The local API binds to loopback only and refuses any other host. It serves an allowlist of
   four artifact names from one directory; callers cannot name a path.

### The one exception

`felix eval` must create records to score a pass rate. That capability is granted explicitly:
`SalesforceClient.grant_write_capability()` returns a `WriteCapability`, and
`OpportunityWriter` is the only consumer. Every write path in the codebase therefore starts at
one greppable call site. The read-only client never exposes its token any other way.

## 10. Tech stack

Python 3.11+ with `uv`. `httpx`, `pydantic` v2, `pydantic-settings`, `typer`, `rich`, stdlib
`sqlite3`, and `fastapi` + `uvicorn` for the loopback API. Model provider behind a thin
interface so it can be swapped. Tests with `pytest` and `respx`; lint with `ruff`.

The UI under `web/` is Next.js 15 and React 19. It is a view over the same library and holds no
logic of its own.

## 11. Testing

Unit tests run entirely against recorded fixtures in `tests/fixtures/` — no network. Live tests
against a Developer Edition org are marked `@pytest.mark.live` and skipped by default.

The dev org is seeded with roughly 20 validation rules chosen to span the realistic failure
space: cross-field conditions, threshold rules, stage-dependent requirements, regex format
constraints, and at least three with deliberately useless error messages such as
*"Please contact your administrator."* Those last ones are the whole reason the product exists,
and they are what a generic error-reading tool cannot solve.

## 12. Open questions

- Does constraint injection actually improve pass rate? The eval answers this, and a negative
  result is still worth publishing.
- Should `agent_context.md` be one block per object or per tool? Token budget will decide.
- Is generating a Pydantic model from org metadata (for Instructor) a better front-end than the
  decorator? More novel, but out of the two-week window.
