# Felix — Thin Local UI

Companion to `SYSTEM_DESIGN.md`. Browser-only viewer for scan / diagnose / results.
Not a hosted product, not a monitoring dashboard.

---

## 1. Goal

Make Felix easier to **demo and navigate** without replacing the CLI.

- Browse scan artifacts (constraints, agent context, evals)
- Pick an object and trigger `scan`
- Paste a Salesforce error and run `diagnose`
- Show the headline eval delta from `docs/reference/RESULTS.md`

CLI remains the source of truth. The UI is a thin shell over the same library.

## 2. Non-goals

- Hosted multi-tenant app, auth portal, or cloud backend
- Writing to Salesforce
- Autonomously “fixing” org rules
- Replacing `felix eval` with a fancy chart suite (one clear before/after number is enough)

## 3. Stack

| Layer | Choice |
| --- | --- |
| UI | Next.js (App Router), React, TypeScript |
| Style | Vercel-like: clean type, sparse chrome, **light + dark** via `next-themes` |
| Data | Local only — read `output/` + call Felix over a tiny local API |
| API | FastAPI or Typer-mounted HTTP on `127.0.0.1` wrapping `scan_org` / `diagnose_error` |
| Browser | Desktop Chrome/Firefox/Safari only — no mobile redesign |

Run: `felix ui` (or `npm run dev` + `uv run felix api`) → `http://127.0.0.1:3737`

## 4. Screens (one composition)

**Home / Scan**
- Object picker (default `Opportunity`)
- Run Scan button + status
- Headline strip: last **local** eval when present, else published `RESULTS.md`

**Artifacts**
- Tabs: Constraints · Test cases · Agent context · Evals
- Test cases: LLM drafts → approve / reject → **Run eval** (writes Opportunities)
- Evals: full report (baseline / treatment / delta / per-case) after a run
- Hard empty state when the scan has **0 active validation rules**
- Copy button for agent context

**Diagnose**
- Paste error JSON + optional payload
- Show matched rule, instruction, or labeled GUESS / escalation

Theme toggle (sun/moon) in the header — persists in `localStorage`.


## 4b. Public flow (post-MVP) — Test cases

User-facing name for eval seeds: **Test cases** (never “seeds” in the UI).

1. **Scan** — searchable object picker → extract constraints  
2. **Review test cases** — LLM proposes failing create payloads; FDE approves / edits / drops  
3. **Run eval** — UI or CLI; runs only on **approved** cases; returns full baseline/treatment/per-case report  

Persist approvals under `output/challenge_cases.json` and the last report under
`output/eval_report.json`. `proposed` cases never enter the headline pass-rate.

API: `POST /challenge-cases/propose`, `GET /challenge-cases`, `PATCH /challenge-cases/{id}`,
`POST /eval`, `GET /eval/latest`.
`felix eval` / `POST /eval` refuse when test cases exist but none are approved.

## 5. Data flow

```
Browser (Next.js)
    │  fetch localhost
    ▼
Local Felix API  ──► salesforce (read-only) / llm (translate)
    │
    ▼
output/*.md, evals.jsonl, scan_result.json
```

Credentials stay in `.env` on the machine. No telemetry.

## 6. Safety (same invariants)

1. Scan and diagnose never write to Salesforce  
2. **Eval is the sole write path** — `felix eval` or `POST /eval` (creates/deletes Opportunities); UI must warn before running  
3. No record data sent to the LLM beyond formula / field names / error messages  
4. API binds to loopback only (`127.0.0.1`)  
5. Diagnose retries still capped at 2 with signature change  

## 7. Look & feel (short)

- Dark default optional; user-switchable light/dark  
- Near-black / near-white backgrounds, one accent (avoid purple glow cliché)  
- Inter/geist-style UI font is fine here (product shell, not a marketing landing)  
- No card grids in the hero; one primary action per view  

## 8. Success

Someone can: open the UI → scan Opportunity → read constraints → paste a useless-admin error → see the real rule — without memorizing CLI flags.
