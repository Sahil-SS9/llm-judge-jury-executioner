# Operations, release and rollback

This repository is a standalone public skill and CLI. It is not a drop-in replacement for KenseiAgent's internal PRD/spec pipeline council.

## Reproducible setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check scripts tests
```

Production dependencies are pinned in `requirements.txt`. `pyproject.toml` exposes the `llm-jje-council` command after `python -m pip install .`.

## Pre-release gate

A release candidate must satisfy all of these on the exact commit being tagged:

1. CI is green on Python 3.10-3.13.
2. `pytest` and Ruff pass locally.
3. The package installs and `llm-jje-council --help` exits zero.
4. A mocked end-to-end run writes Markdown, JSON and HTML artefacts.
5. No provider key, raw credential or `.env` file is committed.
6. Documentation names only implemented protocol paths.

Mocked tests prove orchestration and failure semantics. They do not prove live-provider output quality. A live provider pilot is a separate, explicit release check.

## Protocol rollout

Start with `synthesize` or `vote` on a low-risk question. Use `deliberate` only after provider credentials and fallbacks have been exercised. The engine fails closed to `REVISE` when quorum is lost, and writes diagnostic artefacts before raising on an overall timeout or token-cap breach.

`adaptive_stopping` applies only when a protocol runs cross-examination and ranking. It compares the initial and revised confidence distributions; when stable, ranking is skipped and the reason is recorded in `phases.adaptive_stopping`.

`scan_context` reads only `AGENTS.md`, `CLAUDE.md`, `README.md` and `pyproject.toml` from one configured root. It is non-recursive, bounded by `context_max_chars`, and never reads `.env` or hidden files.

## Partial failures

- Below quorum: returns top-level `verdict: REVISE` and writes all standard artefacts.
- Provider failure with fallbacks: tries the next configured provider/model.
- Token cap or overall timeout: writes a fail-closed diagnostic `council-verdict.json`, then raises.
- Optional compose/cascade/minority failure: records or logs the failure and preserves the main decision path where safe.

## Rollback

1. Identify the previous signed or reviewed release tag.
2. Stop new council invocations; existing output directories are immutable evidence and should be preserved.
3. Check out or reinstall the previous tag.
4. Re-run its pinned tests and one mocked smoke run.
5. Restore traffic only after the previous tag's artefact contract is confirmed.

For a Git rollback:

```bash
git fetch --tags origin
git checkout <previous-tag>
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

Never delete failed-run artefacts during rollback; they are the diagnosis trail.

## Release process

Changes land through a pull request with green CI. Merge only after reviewing the exact diff, then create an annotated semantic-version tag and GitHub release notes that state whether a real-provider pilot was run. Do not describe a mocked-only release as live-proven or production-proven.
