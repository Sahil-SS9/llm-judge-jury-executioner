---
name: llm-council
version: 1.1.0
description: >
  Multi-LLM deliberation council with six honest protocol paths, bounded
  context, fail-closed budgets, anonymised peer review and preserved dissent.
author: Sahil Saghir
license: MIT
platforms: [linux, macos, windows]
tags: [council, deliberation, multi-llm, decision-making, peer-review, debate]
---

# LLM Judge Jury Executioner

Use this skill when a decision is genuinely uncertain, several perspectives add value, and the cost of a weak first answer is material.

Do not use it for simple factual lookup, routine drafting or tasks with one mechanically verifiable answer.

## Choose the protocol

| Protocol | Executed phases | Decision rule | Best for |
|---|---|---|---|
| `deliberate` | compose → independent → cross-exam → ranking → cascade → chairman | chairman judgment | High-stakes decisions |
| `vote` | independent → ranking | majority; ties revise | Prioritisation and binary choices |
| `synthesize` | independent → chairman | chairman synthesis | Combining perspectives |
| `critique` | independent → cross-exam | any material revise blocks | Code, writing and plan review |
| `redteam` | independent → cascade → chairman | chairman weighs adversarial findings | Security and failure modes |
| `mav` | independent → ranking | unanimous approval required | Verification and fact-checking |

The selected protocol is enforced by code. Unknown values fail before any provider call.

## Execution

1. Restate the exact question without adding assumptions.
2. Pick the smallest protocol that answers it. Use `deliberate` only when the extra phases earn their cost.
3. Copy `examples/example-config.yaml` and replace placeholder model IDs with models available from the user's configured providers.
4. Keep credentials in environment variables, never in YAML or prompts.
5. Run:

```bash
python3 scripts/council_engine.py \
  --question "<question>" \
  --config council-config.yaml \
  --output-dir ./council-output
```

6. Read `council-verdict.json` first. Its top-level `verdict` and `issues` are the machine contract. Use the Markdown/HTML as presentation, not as a stronger claim than the JSON supports.
7. State whether the run used mocked providers or real providers. Never call a mocked-only result live-proven.

## Configuration

```yaml
council:
  panel_size: 3
  protocol: deliberate

  compose: true
  cross_examination: true
  cascade_breaker: true
  minority_report: true
  html_report: true
  evidence_labels: true

  panel:
    - {provider: openai, model: your-openai-model}
    - {provider: google, model: your-google-model}
    - {provider: openrouter, model: your-openrouter-model}

  chairman: {provider: openai, model: your-chairman-model}

  fallback_pool:
    - {provider: openrouter, model: your-fallback-model}

  quorum_min: 2
  timeout_seconds: 600
  member_timeout_seconds: 180
  token_cap: 200000

  adaptive_stopping: false
  scan_context: true
  context_root: ""
  context_max_chars: 16000
```

`max_revise_loops` is intentionally not part of this standalone engine. A revision loop requires an external author/operator that can change the decision input; this CLI performs one auditable council run.

See `references/config-reference.md` for field validation and provider routes.

## Trust and privacy boundaries

- The question, workspace context and prior model outputs are fenced as untrusted data in downstream prompts.
- Cross-examination/ranking payloads remove model, provider and persona identity.
- The cascade-breaker does not receive panel signals.
- HTML escapes every model-controlled value.
- Workspace scanning reads only `AGENTS.md`, `CLAUDE.md`, `README.md` and `pyproject.toml`, non-recursively and within `context_max_chars`.
- `.env`, hidden files, arbitrary source files and symlinks are not scanned.

Never paste secrets into the question. The engine does not need them in prompt content.

## Failure semantics

- Below quorum: top-level `REVISE`; standard artefacts are written.
- Provider failure: configured fallbacks are tried in order, including after a permanent primary-provider error.
- Token cap or overall timeout: diagnostic artefacts are written, then the process raises/exits non-zero.
- Invalid config: fails before any provider call.
- Optional compose/cascade/minority failures do not manufacture evidence.

## Adaptive stopping

This is implemented only where two confidence rounds exist. In `deliberate`, stable confidence after cross-examination skips peer ranking and records `phases.adaptive_stopping`. It does not claim multi-round debate beyond the phases actually executed.

## Outputs

- `council-verdict.json` — stable machine contract and all phase data
- `council-verdict.md` — human-readable decision
- `council-report.html` — escaped visual report
- `council-transcript.json` — phase transcript
- `minority-report.md` — optional dissent

## Release status

v1.1 includes tests, pinned dependencies, CI and rollback documentation. Those prove engineering behaviour, not model quality. A release may be called live-proven only when its notes identify an approved real-provider pilot and evidence.

See `references/operations.md` for release, canary and rollback steps.
