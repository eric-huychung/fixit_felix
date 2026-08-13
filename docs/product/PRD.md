# Felix — Product Requirements

**Status:** MVP built. Measured result in [`../reference/RESULTS.md`](../reference/RESULTS.md).
**Scope:** MVP, two weeks
**One line:** Point Felix at a Salesforce org and it tells you everything that will break your AI agent, before you deploy it.

---

## 1. Problem

Enterprise AI agents fail when they write to Salesforce, because every org enforces hidden,
customer-specific business rules that exist nowhere in the API schema:

- Validation rules with formulas an admin wrote three years ago
- Apex triggers calling `addError()` with custom messages
- Fields that are business-required but not schema-required
- Picklist and record-type restrictions

The agent cannot know these. The error it gets back is frequently useless — a common real-world
validation rule message is literally *"Please contact your administrator."*

Today a Forward Deployed Engineer discovers these by asking the customer's Salesforce admin,
clicking through Setup, and reproducing failures one at a time. It is never complete and it
produces no reusable artifact.

One detail makes this worse than it looks: **validation rules evaluate the entire record on
every save**, not just the fields being changed. An agent updating one field can be blocked by
a rule about a completely unrelated field, on a record that was created before the rule existed.

### Evidence

- Sweep's [catalog of Agentforce errors](https://www.sweep.io/blog/catalog-of-agentforce-errors)
  lists `FIELD_CUSTOM_VALIDATION_EXCEPTION` and `REQUIRED_FIELD_MISSING` among the five biggest
  production blockers, describing the former as "when an agent action collides with a validation
  rule built for human input."
- The same pain predates AI agents. Salto, BlueCanvas, StoreConnect and Salesforce StackExchange
  all carry long-running "how do I fix this" content about validation rules breaking API
  integrations. Agents made an old problem far more frequent.
- Managed-package validation rules do not appear under Setup → Validation Rules at all, and the
  Apex behind them is unreadable. Even a diligent engineer cannot enumerate them by hand.
- On the buyer side, a working FDE describes the job as
  ["the customer pays for a number to move... if the number does not move, the work did not
  happen"](https://rohitt.hashnode.dev/what-does-a-forward-deployed-engineer-actually-do) —
  which is why `felix eval` matters as much as `felix scan`.

### What this does *not* claim

FDEs report spending the first two to three weeks of an engagement on discovery, but that is
mostly *business* discovery: stakeholder interviews, finding the real problem, choosing the
metric. Felix compresses *technical* discovery only. Honest saving is hours to a day or two of
spelunking, plus the failures avoided later — not weeks.

## 2. Who this is for

**Primary: Forward Deployed Engineers** at AI companies deploying agents into customer orgs.
They are measured on time-to-working-integration and have no tooling for the technical discovery
half of their job.

**Secondary: solutions and platform engineers** building internal agents against their own
company's Salesforce.

**Not for:** Salesforce admins doing change governance. That is Elements.cloud's market.

### The positioning line that matters

Felix is for agents built **outside** Salesforce — LangGraph, OpenAI, Claude, custom stacks —
that reach **into** a customer's org. It is not for Agentforce agents built inside the platform.

This is deliberate. Sweep, Elements.cloud, and Salesforce's own Testing Center are all
converging on reliability for agents that live inside Salesforce. The FDEs at AI companies, who
are the primary user here, are doing the opposite: pointing an external agent at a customer's
org. They get none of the platform's internal context, which is exactly the gap Felix fills.

## 3. What it is

A local CLI. Three product commands — `scan`, `eval`, `diagnose` — plus `api` and `ui`, which
serve the same library to a loopback-only browser view.

`scan` and `diagnose` are strictly read-only. `eval` is the single exception: it creates and
deletes Opportunities, because a pass rate cannot be measured without attempting writes.

### `felix scan`

Connects to an org, extracts every agent-relevant constraint, and emits four artifacts:

| Artifact | Audience | Purpose |
| --- | --- | --- |
| `constraints.md` | The engineer | Readable inventory of what will break the agent |
| `agent_context.md` | The agent | Drop-in system prompt block / tool description |
| `evals.jsonl` | The eval harness | One test case per active rule |
| `scan_result.json` | Other commands | Structured result `diagnose` reads back |

### `felix eval`

Runs a reference agent against `evals.jsonl` twice — once with the bare tool schema, once with
`agent_context.md` injected — and reports the pass-rate delta.

### `felix diagnose`

Takes a failed write (error text, object, attempted payload) and returns a plain-English
remediation instruction grounded in the actual rule that fired.

## 4. Goals and non-goals

**Goals**
- Replace manual constraint spelunking with one command, and make the result complete rather
  than "whatever the admin remembered"
- Produce a measured, quotable pass-rate improvement on real rules
- Require zero infrastructure and zero security review to try

**Non-goals**
- Syntax and JSON repair (solved by strict-mode decoding and Invari, for free)
- Read-path drift detection (reads return 200; there is no error to catch)
- Multi-CRM support, a hosted backend, a dashboard, or autonomous remediation

## 5. User stories

1. As an FDE on day one at a new customer, I run one command and get a complete list of the
   business rules their agent will violate, without booking time with their admin.
2. As an FDE building the integration, I paste a generated context block into my agent's prompt
   instead of hand-writing field constraints I guessed at.
3. As an FDE at the end of an engagement, I show the customer that their agent went from X% to
   Y% success on rules taken from their own org.
4. As an engineer debugging a production failure, I get the specific rule and what to change,
   instead of an opaque error and a log dive.
5. As a customer receiving a handoff, I keep a constraints document that stays useful after the
   FDE leaves.

## 6. Functional requirements

**Scan**
- Authenticate to a Salesforce org via the OAuth client-credentials flow against the org's
  My Domain host (External Client App). The username-password grant is not supported.
- Extract from `describe`: required fields, types, picklist values, record types, max lengths
- Extract from Tooling API: active and inactive `ValidationRule` records including
  `errorConditionFormula`, `ErrorMessage`, `ErrorDisplayField`, `NamespacePrefix`
- Extract from Tooling API: `ApexTrigger` and `ApexClass` bodies, isolating `addError()` calls
- Translate each formula to plain English exactly once, cached by rule id and formula hash
- Emit all four artifacts; report any objects that failed to scan rather than skipping silently

**Eval**
- Generate one case per *active* rule (inactive rules are reported but never tested)
- Run baseline and treatment, report pass rate, attempts per success, and API calls consumed

**Diagnose**
- Match an incoming error to a known rule by signature
- Return the rule, its plain-English meaning, and the field to change
- Cap retries at 2 and require the error signature to change between attempts
- Escalate with a structured payload when the rule cannot be satisfied by the agent
  (for example, one requiring a specific human approver)

## 7. Success metrics

**Primary:** pass-rate delta between baseline and treatment on a seeded org of real rules.
A meaningful result in either direction ships. The delta must be quoted with the number of
eval seeds that were hand-fitted to the org versus derived — a pass rate over hand-fitted
seeds does not generalise, and `felix scan` prints the split for that reason.

**Secondary:** scan wall-clock under five minutes for one object; zero writes to the org from
`scan` and `diagnose` (the `eval` harness writes by design, and cleans up after itself); the
full flow demonstrable in a 90-second video.

**The headline demo must be an unreadable error.** Every competitor's advice for
`FIELD_CUSTOM_VALIDATION_EXCEPTION` reduces to "read the error message." That works until the
message is *"Please contact your administrator"* — or until the rule lives in a managed package
and is invisible in Setup. Those cases are the only ones that require reading the org, so they
are the demo. Seed at least three of them.

## 8. Competitive positioning

- **Syntax repair** (Invari, OpenAI strict mode, Speakeasy) — no overlap; we assume it is solved
- **Runtime healers** (SelfHeal, Instructor, Magentic, LangGraph retries) — they react to the
  error string alone. We read the org. Overlap is limited to `diagnose`.
- **Salesforce org intelligence** (Elements.cloud, Metazoa, Salto) — closest on capability,
  furthest on audience. They produce governance documentation for admins. Elements and Metazoa
  now both advertise "prepare your metadata for Agentforce."
- **Agentforce reliability** (Sweep) — the nearest competitor. Sweep publishes the Agentforce
  error catalog and recommends exactly our approach: *"Map the metadata, not just the schema...
  a metadata index that captures all of these, and keeps them current."* The separation is
  audience, not capability: Sweep serves agents built inside Salesforce, Felix serves agents
  built outside it. Assume this boundary erodes.
- **Platform-native testing** (Agentforce Testing Center) — auto-generates agent test cases,
  which overlaps eval generation, but only for agents built on the platform.
- **FDE ops platforms** (Nixo, Rocketlane) — organize the engineer's tasks; never touch customer
  systems. Complementary.
- **Eval platforms** (Braintrust, LangSmith, Promptfoo) — you supply the test cases. We generate
  them from the customer's system, so we feed them.

**The gap:** everyone either reads the org *for humans*, or heals errors *without reading the
org*. Nobody reads the org to make agents work.

## 9. Risks

| Risk | Mitigation |
| --- | --- |
| An engineer just hardcodes the five rules they hit | Lead with the long tail and admin-introduced drift; the eval either proves this matters or it does not |
| Salesforce closes the gap themselves | Real and unmitigable. Their hosted MCP server already exposes describe metadata, which is why we skip that tier and go straight to rules and Apex |
| Apex reasoning is unreliable | Ship it as clearly-labeled best-effort; validation rules alone carry the MVP |
| Not enough teams write to Salesforce from agents | Confirm with real engineers before building tier 2 |
| Sweep extends from Agentforce to external agents | The most likely competitive move. Our defence is being the tool that works when the customer's agent is not a Salesforce product |

### Viability, graded honestly

**As a business: 5/10.** The problem is confirmed by independent sources and the gap is real, but
it is closing from two directions at once — Salesforce from above, Sweep and Elements from the
side. Not a category to raise money against without a sharper wedge.

**As a portfolio project for an FDE role: 8.5/10.** Third parties document the problem, so it can
be cited rather than asserted. Technical risk is low. It produces a number, which is the unit FDE
work is judged in. Build it for this reason.

## 10. Milestones

**Week 1** — Salesforce client and auth; describe extraction; Tooling API rule extraction;
`constraints.md`; a dev org seeded with ~20 deliberately nasty validation rules.

**Week 2** — Formula translation with caching; `agent_context.md` and `evals.jsonl`; the eval
harness and the headline number; `diagnose`; demo video and writeup.

**Out of the two-week window** — Apex extraction, MCP tool front-end, a second object, generated
Pydantic models for Instructor.
