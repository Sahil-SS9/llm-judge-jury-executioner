# Configuration reference

The standalone CLI accepts YAML or JSON. Unknown fields and invalid values fail before any provider call.

## Complete shape

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
    - provider: openai
      model: your-model
      fallback:
        - {provider: openrouter, model: your-fallback}

  chairman: {provider: openai, model: your-chairman}
  fallback_pool: []

  quorum_min: 2
  timeout_seconds: 600
  member_timeout_seconds: 180
  token_cap: 200000

  adaptive_stopping: false
  scan_context: true
  context_root: ""
  context_max_chars: 16000
```

## Core fields

### `panel_size`

- Integer, 2-10; default `3`.
- The configured panel is truncated or repeated to this size.

### `panel`

- List of mappings containing non-empty `provider` and `model`.
- Required at runtime.
- Each optional `fallback` is an ordered list of provider/model mappings.

### `chairman`

- Mapping containing `provider` and `model`.
- If omitted, the first panel member is used.
- Protocols without a chairman phase (`vote`, `critique`, `mav`) still need panel members but do not call the chairman.

### `fallback_pool`

- Ordered shared list tried after one member's own fallbacks.
- Provider/model collisions are prevented only while a call is active. A model can be reused safely by a later phase.
- Both transient and permanent primary-provider failures can fall through to an explicitly configured alternative.

## Protocols

Unknown protocols raise `ValueError` before any provider call.

| Protocol | Executed phases | Closure |
|---|---|---|
| `deliberate` | compose → independent → cross-exam → ranking → cascade → chairman | chairman judgment |
| `vote` | independent → ranking | majority; ties revise |
| `synthesize` | independent → chairman | chairman synthesis |
| `critique` | independent → cross-exam | any revise vote blocks |
| `redteam` | independent → cascade → chairman | chairman judgment |
| `mav` | independent → ranking | unanimous approval required |

### Optional phase flags

- `compose` (bool, default `true`): enables Phase 0 only for `deliberate`.
- `cross_examination` (bool, default `true`): enables cross-exam when the protocol includes it.
- `cascade_breaker` (bool, default `true`): enables independent re-derivation when the protocol includes it.
- `minority_report` (bool, default `true`): asks the lowest-confidence successful member to preserve dissent after closure.
- `html_report` (bool, default `true`): writes escaped `council-report.html`.
- `evidence_labels` (bool, default `true`): adds the evidence-tagging directive to Phase 1.

Flags can remove optional work; they do not expand a protocol beyond its table row.

## Reliability and budget fields

### `quorum_min`

- Integer between `1` and `panel_size`; default `2`.
- Below quorum, the run closes `REVISE` and writes standard artefacts.

### `timeout_seconds`

- Positive number; default `600`.
- Overall wall-clock deadline. Every phase receives only the remaining time.
- On breach, diagnostic artefacts are written before `TimeoutError` is raised.

### `member_timeout_seconds`

- Positive number; default `180`.
- Per-call limit, capped to the remaining overall deadline.

### `token_cap`

- Positive integer or `null`; default `200000`.
- Checked after every executed phase, including composition and the final phase.
- On breach, fail-closed diagnostic artefacts are written before `RuntimeError` is raised.

This standalone CLI has no `max_revise_loops`. It performs one immutable council run; an external workflow must own any edit-and-rerun loop.

## Adaptive stopping

`adaptive_stopping` is a boolean, default `false`.

It currently applies to `deliberate` when cross-examination and ranking are both selected. The engine compares initial and revised confidence distributions with a KS statistic. If stable, ranking is skipped and the reason is recorded under `phases.adaptive_stopping`.

## Workspace context

### `scan_context`

- Boolean, default `true`.
- Reads only `AGENTS.md`, `CLAUDE.md`, `README.md` and `pyproject.toml` from one root.

### `context_root`

- String path; empty means the current working directory.
- Scanning is non-recursive; symlinks and hidden files are not read.

### `context_max_chars`

- Positive integer; default `16000`.
- Shared cap across all allowlisted context files.

Question/context/model payloads are fenced as untrusted data in downstream prompts.

## Providers

| Provider | Credential environment variable | OpenAI-compatible base URL |
|---|---|---|
| `openai` | `OPENAI_API_KEY` | `https://api.openai.com/v1` |
| `anthropic` | `ANTHROPIC_API_KEY` | `https://api.anthropic.com/v1` |
| `google` | `GOOGLE_API_KEY` | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| `openrouter` | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` |
| `custom` | `CUSTOM_API_KEY` | `CUSTOM_BASE_URL` (required) |

A member-level `base_url` overrides the built-in route. Model IDs are provider-specific. Keep secrets out of YAML.

## Machine output contract

`council-verdict.json` has `schema_version: 1` and stable top-level fields:

```json
{
  "schema_version": 1,
  "protocol": "deliberate",
  "verdict": "APPROVED",
  "issues": [],
  "recommendation": "...",
  "total_tokens": 1234,
  "elapsed_seconds": 12.3,
  "phases_executed": ["..."],
  "phases": {"verdict": {"verdict": "APPROVED"}}
}
```

The public schema is portable and independent of KenseiAgent's internal pipeline contract.
