# Security policy

## Reporting a vulnerability

Please report security issues privately through
[GitHub's private vulnerability reporting](https://github.com/eric-huychung/fixit_felix/security/advisories/new)
rather than opening a public issue. Expect an initial response within a few days.

Include what you did, what happened, and the impact you think it has. A proof of concept
helps but is not required.

## Threat model

Felix runs on an engineer's machine, holds Salesforce credentials, and talks to a live org.
The guarantees it makes:

| Guarantee | Enforced by |
|-----------|-------------|
| Only `GET` reaches the org, plus the auth `POST` | `SalesforceClient._request` raises `ReadOnlyViolation` on any other method |
| The one write path is explicit | `grant_write_capability()` — the eval harness is the sole consumer |
| All SOQL is built in one place, with object names validated | `felix/salesforce/soql.py` |
| The local API binds to loopback only | `assert_loopback_host` at serve time |
| Artifact reads cannot escape the output directory | `ArtifactStore` maps names to paths; callers cannot supply one |
| Record data never reaches the LLM | Only formula text, API names, labels, and error messages are sent |
| Credentials stay on the machine | No hosted backend, no telemetry |

## The local API is unauthenticated by design

`felix api` and `felix ui` serve an HTTP API on `127.0.0.1` with no authentication. That is
appropriate for a single-user local tool, and it means:

- **Any process on your machine can call it** while it is running. Do not run it on a shared
  or multi-user host.
- `POST /scan` with `use_fixtures: false` will authenticate to your org and consume API calls.
- The CORS allowlist covers only the loopback UI origin, and the server refuses to bind to a
  non-loopback address. Neither is a substitute for the above.

Stop the server when you are not using it.

## Credentials

Felix reads credentials from the environment or a local `.env`, which is gitignored. It never
writes them to artifacts, logs, or the cache. If you believe a credential was exposed, rotate
the External Client App secret in Salesforce Setup immediately.

## Supported versions

Felix is pre-1.0. Fixes land on `main` only.
