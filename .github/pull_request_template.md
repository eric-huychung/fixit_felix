## What and why

<!-- What changes, and what problem it solves. Lead with the why. -->

## How to verify

<!-- The command a reviewer should run, or the test that fails without this change. -->

## Checklist

- [ ] `scripts/check.sh` passes
- [ ] Added or updated a test that fails without this change
- [ ] Docs updated if behaviour or setup changed
- [ ] No credentials, org URLs, or record data in the diff or in test fixtures

## Invariants

Tick any this PR touches, and say how the guarantee still holds:

- [ ] Read-only access to Salesforce (`felix/salesforce/client.py`)
- [ ] SOQL is built only in `felix/salesforce/soql.py`
- [ ] The API binds to loopback only (`felix/api.py`)
- [ ] Artifact reads stay inside the output directory (`felix/emit/artifacts.py`)
- [ ] Record data never reaches the LLM (`felix/translate.py`)
- [ ] Eval seed provenance stays accurate (`felix/emit/evalset.py`)
