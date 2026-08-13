# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security

- All SOQL is now built in `felix/salesforce/soql.py`, which validates sObject API names before
  interpolation. Previously the `--object` flag and the `object_name` field on `POST /scan`
  reached three separate query strings unescaped.
- `POST /diagnose` no longer accepts a `scan_result_path`. The scan result is read from the
  server's own output directory through `ArtifactStore`, so a caller can no longer name an
  arbitrary file on disk.
- Write access to Salesforce is granted explicitly via
  `SalesforceClient.grant_write_capability()` instead of exposing the bearer token as a
  property. The eval harness is the only consumer.

### Added

- `felix/session.py` — owns one scan's lifetime (settings, auth, cache, provider, output
  directory) and closes what it opened.
- `ArtifactStore` in `felix/emit/artifacts.py` — the single owner of the output directory,
  with an allowlist of artifact names.
- Eval seed provenance: each `EvalCase` records whether its payload was hand-fitted to the org
  (`org_pack`) or derived from the rule's referenced fields (`derived`). Both `felix scan` and
  `felix eval` report the split, because a pass rate over hand-fitted seeds does not
  generalise.
- `felix scan --output-dir` to match `felix api --output-dir`.
- `felix scan` prints a summary of what it found (rules, required fields, picklists, Apex
  call sites) instead of only listing the files it wrote.
- `felix api --web-port` so the CORS allowlist follows the UI port.
- `scripts/check.sh` — lint, tests with coverage, and the web build in one command.
- GitHub Actions CI, issue and PR templates, Dependabot, `.github/CONTRIBUTING.md`,
  `.github/SECURITY.md`.

### Fixed

- `POST /scan` wrote artifacts to `OUTPUT_DIR` while `GET /artifacts/{name}` read from the
  directory passed to `felix api --output-dir`. With a custom output directory the UI returned
  404 for every artifact after a successful live scan.
- The CLI and the API leaked a SQLite connection and an HTTP client on every scan; neither
  used the context managers those classes already provided. On the long-running API this
  accumulated per request.
- Apex class extraction caught every exception and returned an empty list, reporting a
  permissions error as "no Apex constraints found". Failures now surface as `ScanError`
  entries, and a failure in one Apex source no longer discards results from the other.
- Scanning an object whose name contained "Metadata" raised
  `RuntimeError: Batched Metadata query must never be constructed`. The guard inspected a
  string literal it could not affect and only ever produced false positives; it is gone.
- The CORS allowlist was hardcoded to port 3737, so the UI failed with an opaque
  "Failed to fetch" on any other port, including Next.js's default 3000.
- `felix eval` did not close its HTTP clients when a run raised partway through.
- Offline mode now reports a missing or incomplete fixture directory clearly instead of
  raising a bare `FileNotFoundError`.
- Offline scans described all eight fixture rules with the same invented sentence, because
  the fixture session used a stub LLM whose canned reply was written to `constraints.md` and
  `agent_context.md` as each rule's "Meaning". Offline scans no longer translate; untranslated
  rules fall back to their own formula and referenced fields.
- Salesforce reports page-level validation errors with the sentinel display field
  `Top of Page`. Felix printed it verbatim as `Field: Top of Page`, which reads like a real
  field name. It is now normalised to "no field".

### Changed

- Docs reorganised into `docs/product/`, `docs/architecture/`, and `docs/reference/`, with an
  index at `docs/README.md`. Personal working notes are kept locally and no longer published.
- `docs/product/PRD.md` and `docs/architecture/SYSTEM_DESIGN.md` corrected: authentication is
  OAuth client-credentials (not username-password), there are five commands and four
  artifacts, and `felix eval` writes to the org by design.
- `pyproject.toml` now declares its MIT license, project URLs, and classifiers.

[Unreleased]: https://github.com/eric-huychung/fixit_felix/commits/main
