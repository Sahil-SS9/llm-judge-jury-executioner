# Changelog

## 1.1.0 — 2026-08-27

### Added

- Six explicit protocol execution plans.
- Strict config validation and stable JSON schema v1.
- Bounded workspace-context scanning and prompt trust fences.
- Overall deadline, per-phase token enforcement and diagnostic artefacts.
- Adaptive ranking stop, correct minority-member identity and provider fallbacks.
- Python 3.10-3.13 CI, pinned dependencies, installable CLI and operations guide.

### Fixed

- Top-level JSON arrays now parse correctly, restoring dynamic composition.
- Google uses its official OpenAI-compatible endpoint.
- Anonymous peer prompts no longer expose model/persona metadata.
- Cascade-breaking no longer receives panel signals.
- HTML and Markdown reports escape model-controlled markup.
- Concurrent model reservations are released after each call.

### Changed

- The public skill is documented as a standalone product rather than a drop-in KenseiAgent replacement.
- Removed the non-operational `max_revise_loops` option and production-proof overclaims.
- Removed the unreferenced `header.jpg` binary.

Mocked CI proves engineering behaviour. Real-provider output quality remains a separately recorded pilot boundary.
