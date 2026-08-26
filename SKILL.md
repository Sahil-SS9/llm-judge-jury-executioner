---
name: llm-council
version: 1.0.0
description: >
  Multi-LLM deliberation council. Run any decision through N diverse AI advisors
  who argue, cross-examine, peer-review, and hand you a verdict with preserved
  dissent. Research-backed synthesis of Karpathy's LLM Council, dynamic agent
  composition, cascade-breaking, and minority report patterns.
author: Sahil Saghir
license: MIT
platforms: [linux, macos, windows]
tags: [council, deliberation, multi-llm, decision-making, peer-review, debate]
---

# LLM Judge Jury Executioner

Stop trusting a single LLM's first answer for high-stakes decisions. Run any
question through a council of diverse AI advisors who independently reason,
cross-examine each other's positions, rank responses anonymously, and produce
a chairman-synthesized verdict — with dissent preserved as a minority report.

## When to Use

**Good council questions** — genuine uncertainty, high cost of a bad call:
- "Should I launch a $97 workshop or a $497 course?"
- "Which of these 3 architecture approaches is strongest for a real-time collab app?"
- "I'm thinking of pivoting from X to Y. Am I crazy?"
- "Here's my API contract. What will break in production?"
- "Should I hire a VA or build an automation first?"

**Bad council questions** — one right answer, no need for perspectives:
- "What's the capital of France?"
- "Write me a tweet"
- "Summarize this article"

## How It Works

The council runs 5 phases (0-4):

```
Question → Phase 0: Compose → Phase 1: Independent Review →
Phase 2: Cross-Examination + Ranking → Phase 2b: Cascade-Breaker →
Phase 3: Chairman + Minority Report → Verdict + Artifacts
```

### Phase 0 — Compose (Dynamic Agent Assembly)
An LLM generates N diverse advisor personas, each with a distinct INITIAL
POSITION (not just distinct expertise). Research shows position diversity
outperforms expertise diversity for group decision quality. At least one
advisor is structurally skeptical (red-team role). At least one approaches
from a fundamentally different cognitive frame.

### Phase 1 — Independent Review (Parallel)
All panel members answer independently in parallel. Each response is
evidence-labeled: every claim tagged as [empirical], [mechanistic],
[strategic], [ethical], or [heuristic]. Prevents hiding opinion as fact.

### Phase 2 — Cross-Examination + Anonymised Peer Ranking
Each member sees the others' positions under anonymised labels (Advisor A/B/C).
They concede, disagree, and revise. Then all members rank each other's
responses on accuracy, insight, and completeness — without knowing who said
what. Anonymous review prevents provider/identity bias.

### Phase 2b — Cascade-Breaker (Skeptic Role)
A designated skeptic re-derives the verdict from first principles, ignoring
all prior agent signals. This breaks "socially plausible cascades" where one
agent's plausible-but-wrong shortcut propagates through deliberation dynamics
even when no individual member would accept it. Based on research on shortcut
cascades in multi-agent committees.

### Phase 3 — Chairman Synthesis + Minority Report
The chairman model sees all responses, cross-examination output, rankings,
and the cascade-breaker output. It produces an APPROVED or REVISE verdict with
deduplicated issues. The lowest-confidence panel member writes a minority
report preserving dissent — disagreement is recorded, not averaged away.

## Protocols

The council supports 6 protocols (configurable):

| Protocol | Phases | When to use |
|----------|--------|-------------|
| `deliberate` | 0→1→2→2b→3 | Full deliberation (default) — high-stakes decisions |
| `vote` | 1→2 (ranking only) | Quick consensus — multiple choice, prioritization |
| `synthesize` | 1→3 (chairman only) | Combine perspectives — open-ended questions |
| `critique` | 1→2 (critique only) | Peer review — code, writing, plans |
| `redteam` | 1→2b→3 (adversarial) | Adversarial testing — security, failure modes |
| `mav` | 1→2 (verification) | Model-as-verifier — fact-checking, validation |

## Trigger Phrases

- `council this`
- `run the council`
- `pressure-test this`
- `stress-test this`
- `debate this`
- `war room this`

## Configuration

Create a `council-config.yaml` or define inline:

```yaml
council:
  panel_size: 3                    # Number of panel members (2-10)
  protocol: deliberate             # deliberate|vote|synthesize|critique|redteam|mav

  compose: true                    # Phase 0: dynamic agent composition
  cross_examination: true          # Phase 2: cross-exam before ranking
  cascade_breaker: true            # Phase 2b: skeptic role
  minority_report: true            # Phase 3: preserve dissent
  html_report: true                # Generate HTML visual report
  evidence_labels: true            # Tag claims with evidence types

  panel:
    - provider: openai             # Any OpenAI-compatible provider
      model: gpt-5
      fallback:
        - {provider: anthropic, model: claude-sonnet-4}
    - provider: anthropic
      model: claude-sonnet-4
    - provider: google
      model: gemini-3-pro

  chairman:
    provider: openai
    model: gpt-5

  fallback_pool:                    # Shared pool tried after per-member fallbacks
    - {provider: openai, model: gpt-5-mini}
    - {provider: anthropic, model: claude-haiku}

  quorum_min: 2                     # Minimum members for valid deliberation
  max_revise_loops: 4               # REVISE bounce cap before escalation
  timeout_seconds: 600              # Total council timeout
  member_timeout_seconds: 180      # Per-member timeout
  token_cap: 200000                 # Total token budget

  adaptive_stopping: false          # KS statistic early stopping (debate only)
  scan_context: true                # Scan workspace files for question framing
```

See `references/config-reference.md` for the full schema.

## Outputs

| File | Description |
|------|-------------|
| `council-verdict.md` | Human-readable verdict: APPROVED/REVISE + issues |
| `council-verdict.json` | Machine-readable verdict + all phase data |
| `council-report.html` | Visual report: agreement map, clash points, recommendation |
| `minority-report.md` | Dissenting position from lowest-confidence member |
| `council-transcript.json` | Full transcript of all phases |

## Execution

### From an agent (Claude Code, Hermes, etc.)

The agent loads this SKILL.md, reads the question, and follows the protocol.
The engine at `scripts/council_engine.py` is a standalone Python script that
can be invoked directly for headless/automated runs.

### Direct CLI invocation

```bash
python3 scripts/council_engine.py \
  --question "Should I use Postgres or MongoDB for a social app with 10k users?" \
  --config examples/example-config.yaml \
  --output-dir ./council-output
```

### Provider Configuration

The engine uses any OpenAI-compatible API. Set environment variables:

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="..."
# Or use a unified provider like OpenRouter:
export OPENROUTER_API_KEY="sk-or-..."
```

The `provider` field in config maps to:
- `openai` → `OPENAI_API_KEY`, `https://api.openai.com/v1`
- `anthropic` → `ANTHROPIC_API_KEY`, `https://api.anthropic.com/v1`
- `google` → `GOOGLE_API_KEY`, `https://generativelanguage.googleapis.com/v1`
- `openrouter` → `OPENROUTER_API_KEY`, `https://openrouter.ai/api/v1`
- `custom` → `CUSTOM_API_KEY`, `CUSTOM_BASE_URL` (any OpenAI-compatible endpoint)

## Research Basis

This skill synthesizes findings from multiple sources. See
`references/research-basis.md` for full citations.

Key findings incorporated:
- Scale agents, not rounds (adding models > adding debate turns)
- Heterogeneous models outperform homogeneous (mix providers)
- Anonymous peer review prevents provider bias
- Cascade-breaking prevents socially plausible shortcut propagation
- Minority reports preserve dissent and improve decision auditability
- Evidence labeling prevents hiding opinion as fact
- Reliability-weighted aggregation improves ensemble quality

## Pitfalls

- **Quorum failure degrades to auto-REVISE.** If fewer than `quorum_min`
  members produce non-ERROR critiques, the council returns REVISE with a
  quorum failure note rather than a potentially biased small-sample verdict.
- **REVISE loop is capped.** After `max_revise_loops` bounces, the task
  escalates to the human operator rather than looping forever.
- **Token cap is enforced mid-deliberation.** If exceeded, the council
  raises RuntimeError. Set `token_cap: null` to disable.
- **Custom providers need base_url.** The `custom` provider requires
  `CUSTOM_BASE_URL` to be set — it doesn't default to any endpoint.
- **Cascade-breaker is advisory, not blocking.** The chairman sees the
  cascade-breaker output but is not forced to adopt it. The chairman still
  makes the final call.
- **Minority report is from the lowest self-reported confidence member.**
  This is a proxy for genuine dissent. It's not a guarantee the minority
  report is correct — it's a guarantee the disagreement is visible.
- **Adaptive stopping is protocol-gated.** Only applies to `deliberate`
  and `vote` protocols with multiple rounds. Single-pass protocols ignore it.

## Platform Compatibility

Works in:
- Claude Code (skill format)
- Hermes Agent (skill format)
- Any agent that reads SKILL.md files
- Direct CLI (`python3 scripts/council_engine.py`)
- CI/CD pipelines (headless, non-interactive)

## License

MIT — see [LICENSE](LICENSE).