# Felix eval results

**Date:** 2026-08-12  
**Org:** Developer Edition (`orgfarm-4c46e537d0-dev-ed`)  
**Object:** Opportunity  
**Active validation rules:** 8  
**Model:** `google/gemini-2.5-flash-lite` via Vercel AI Gateway  
**Harness:** reference agent, max 2 attempts, baseline = seed payload only, treatment = seed + `agent_context.md`

## Numbers

| Arm | Pass rate | Passes | Attempts / success | API calls |
| --- | --- | --- | --- | --- |
| Baseline | 25% | 2 / 8 | 2.00 | 18 |
| Treatment | 50% | 4 / 8 | 2.00 | 20 |
| **Delta** | **+25 pp** | | | |

## What this number does and does not show

All 8 eval seeds were **hand-fitted to this org** (`seed_provenance: org_pack`), meaning each
payload was written to trip its specific rule. That makes the two arms comparable to each
other, which is what the delta measures. It does **not** show that Felix produces a +25 pp
lift on an arbitrary org: point it at one whose rules are not in the seed pack and the cases
fall back to derived seeds, which may not trip their rule at all. `felix scan` prints the
org-pack/derived split for exactly this reason — quote it whenever you quote a pass rate.

## Reading

Constraint injection helped on this seeded org: treatment doubled the pass rate
(+25 percentage points) without a large API-call penalty. Remaining failures are
expected — at least one rule uses stage picklist values that do not match the org
(`Proposal` / `Negotiation` vs `Proposal/Price Quote` / `Negotiation/Review`), and
some constraints (e.g. hard amount caps framed as “VP review”) cannot be satisfied
by field edits alone. A negative or mixed result would still have been publishable;
this run is a positive but modest signal, not proof that context always wins.
