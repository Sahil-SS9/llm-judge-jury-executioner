# Config Reference

Full schema for `council-config.yaml` (or JSON equivalent).

## Top-Level Structure

```yaml
council:
  # Panel configuration
  panel_size: 3
  panel: [...]

  # Chairman
  chairman: {...}

  # Fallback pool (shared)
  fallback_pool: [...]

  # Protocol
  protocol: deliberate

  # Feature flags
  compose: true
  cross_examination: true
  cascade_breaker: true
  minority_report: true
  html_report: true
  evidence_labels: true

  # Operational
  quorum_min: 2
  max_revise_loops: 4
  timeout_seconds: 600
  member_timeout_seconds: 180
  token_cap: 200000

  # Optional
  adaptive_stopping: false
  scan_context: true
```

## Fields

### panel_size
- **Type:** int
- **Default:** 3
- **Range:** 2-10
- Number of panel members. Each member runs on a separate model/provider.

### panel
- **Type:** list of dicts
- **Required:** Yes (at least one entry)
- Each entry defines a panel member:

```yaml
panel:
  - provider: openai           # Provider name (see below)
    model: gpt-5               # Model slug
    base_url: "https://..."    # Optional: override provider default
    fallback:                  # Optional: per-member fallback chain
      - {provider: anthropic, model: claude-sonnet-4}
      - {provider: google, model: gemini-3-pro}
```

### chairman
- **Type:** dict
- **Default:** First panel member
- The chairman model that synthesizes the final verdict.

```yaml
chairman:
  provider: openai
  model: gpt-5
  fallback:
    - {provider: anthropic, model: claude-sonnet-4}
```

### fallback_pool
- **Type:** list of dicts
- **Default:** Empty
- Shared pool tried after per-member fallbacks are exhausted. Ordered by
  cost/speed. Runtime model deduplication prevents same-model collisions.

```yaml
fallback_pool:
  - {provider: openai, model: gpt-5-mini}
  - {provider: anthropic, model: claude-haiku}
  - {provider: google, model: gemini-3-flash}
```

### protocol
- **Type:** string
- **Default:** `deliberate`
- Options: `deliberate`, `vote`, `synthesize`, `critique`, `redteam`, `mav`

| Protocol | Phases | Use case |
|----------|--------|----------|
| deliberate | 0→1→2→2b→3 | High-stakes decisions (default) |
| vote | 1→2 (ranking only) | Quick consensus, prioritization |
| synthesize | 1→3 (chairman only) | Open-ended questions |
| critique | 1→2 (critique only) | Peer review of code/writing |
| redteam | 1→2b→3 | Adversarial testing, security |
| mav | 1→2 (verification) | Model-as-verifier, fact-checking |

### compose
- **Type:** bool
- **Default:** true
- Phase 0: Dynamic agent composition. An LLM generates N diverse advisor personas
  with distinct initial positions before Phase 1.

### cross_examination
- **Type:** bool
- **Default:** true
- Phase 2: Each member sees others' positions (anonymised), concedes/disagrees/revises.

### cascade_breaker
- **Type:** bool
- **Default:** true
- Phase 2b: A skeptic re-derives the verdict from first principles, breaking
  socially plausible cascades.

### minority_report
- **Type:** bool
- **Default:** true
- Phase 3b: The lowest-confidence panel member writes a minority report
  preserving dissent.

### html_report
- **Type:** bool
- **Default:** true
- Generate a visual HTML report alongside the markdown verdict.

### evidence_labels
- **Type:** bool
- **Default:** true
- Require panel members to tag every claim with evidence type:
  [empirical] [mechanistic] [strategic] [ethical] [heuristic]

### quorum_min
- **Type:** int
- **Default:** 2
- Minimum number of panel members that must respond successfully. Below this,
  the council returns auto-REVISE with a quorum failure note.

### max_revise_loops
- **Type:** int
- **Default:** 4
- Maximum REVISE bounces before escalating to the human operator.

### timeout_seconds
- **Type:** int
- **Default:** 600
- Total council timeout in seconds.

### member_timeout_seconds
- **Type:** int
- **Default:** 180
- Per-member call timeout in seconds.

### token_cap
- **Type:** int or null
- **Default:** 200000
- Total token budget across all phases. If exceeded mid-deliberation, raises
  RuntimeError. Set to `null` to disable.

### adaptive_stopping
- **Type:** bool
- **Default:** false
- KS statistic convergence detection for debate-style protocols. If distribution
  shift between rounds drops below epsilon for consecutive rounds, stops early.
- **Note:** Only applies to `deliberate` and `vote` protocols with multiple rounds.

### scan_context
- **Type:** bool
- **Default:** true
- Scan workspace files (CLAUDE.md, project files) for additional context when
  framing the question.

## Providers

| Provider | Env Var | Base URL |
|----------|---------|----------|
| openai | OPENAI_API_KEY | https://api.openai.com/v1 |
| anthropic | ANTHROPIC_API_KEY | https://api.anthropic.com/v1 |
| google | GOOGLE_API_KEY | https://generativelanguage.googleapis.com/v1 |
| openrouter | OPENROUTER_API_KEY | https://openrouter.ai/api/v1 |
| custom | CUSTOM_API_KEY | CUSTOM_BASE_URL (must set) |

For custom providers, set:
```bash
export CUSTOM_API_KEY="your-key"
export CUSTOM_BASE_URL="https://your-endpoint/v1"
```

## Fallback Resolution Order

For each panel member or the chairman, the engine tries:
1. **Primary** — member.provider / member.model
2. **Per-member fallbacks** — member.fallback list, in order
3. **Shared fallback_pool** — council-wide, in order

At each step:
- If the model is already in use by another active member → SKIP (deduplication)
- Transient errors (429, 402, 408, 500, 502, 503, 504, 529) → try next fallback
- Permanent errors (400, 401, 403, 404, 422) → fail immediately, no retry

## Diversity Validation

At config load time, the engine checks:
- **Cross-owner model duplication** — same model appearing in multiple panel members
- **Provider concentration** — >=3 roles on one provider (single-provider outage risk)

Same-member primary/fallback duplication is intentional (provider failover) and
NOT flagged.