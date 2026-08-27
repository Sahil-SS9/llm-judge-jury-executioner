# Research Basis

This document lists the academic and community sources that inform the LLM Judge Jury Executioner
skill architecture, with the specific findings incorporated into the design.

## Community Repositories

### 1. Karpathy's LLM Council (24k stars)
**Repo:** https://github.com/karpathy/llm-council
**Created:** 2025-11-22

The original LLM Council concept. A local web app that sends queries to multiple
LLMs via OpenRouter, asks them to review and rank each other's work, and a Chairman
LLM produces the final response.

**Findings incorporated:**
- 3-phase deliberation pattern: independent review → anonymised peer ranking → chairman synthesis
- Anonymisation prevents model identity bias in peer review
- Chairman synthesizes rather than averages — incorporates strongest reasoning while acknowledging disagreement

**Limitations (why we don't just fork it):**
- Explicitly unsupported ("vibe coded", "I don't intend to improve it")
- Web app only — not a skill, not headless, not CI/CD compatible
- Single provider (OpenRouter) — no fallback chains
- No quorum, no error classification, no token cap, no REVISE loop

### 2. aiwithremy/claude-skills-llm-council (1.7k stars)
**Repo:** https://github.com/aiwithremy/claude-skills-llm-council
**Created:** 2026-04-25

A Claude Code skill by Ole Lehmann. Runs 5 advisors with different thinking styles,
peer-review each other, and a chairman delivers a verdict.

**Findings incorporated:**
- Skill format (SKILL.md) as delivery vehicle
- Trigger phrases ("council this", "pressure-test this")
- Clear when-to-use / bad-questions guidance
- Beginner-friendly installation instructions

**Limitations:**
- Single-model sub-agents (all Claude) — no multi-provider diversity
- No cross-examination, no cascade-breaking, no minority report
- No fallback chains, no quorum, no error handling

### 3. tenfoldmarc/llm-judge-jury-executioner (674 stars)
**Repo:** https://github.com/tenfoldmarc/llm-judge-jury-executioner
**Created:** 2026-04-18

A Claude Code skill with 5 advisor personas: Contrarian, First Principles Thinker,
Expansionist, Outsider, Executor. Generates visual HTML report + markdown transcript.

**Findings incorporated:**
- HTML visual report output (agreement map, clash points, recommendation, next step)
- Workspace context scanning (CLAUDE.md, memory files) for question framing
- Fixed advisor personas as a starting point (we make them dynamic)
- "About 4 minutes" — realistic time expectation

**Limitations:**
- All sub-agents are the same model (Claude) — no provider diversity
- No cross-examination, no cascade-breaking
- No fallback chains, no quorum, no error handling
- No research basis cited

### 4. magnus919/hermes-council (52 stars)
**Repo:** https://github.com/magnus919/hermes-council
**Created:** 2026-05-20

A pip-installable plugin foundation for Hermes Agent. Includes a standalone demo
script with multi-phase debate: compose → positions → cross-examination.

**Findings incorporated:**
- Phase 0: Dynamic agent composition (LLM generates diverse advisors with distinct initial positions)
- Cross-examination round (each member sees others' positions, concedes/disagrees/revises)
- Position diversity > expertise diversity (from their compose prompt)
- Threaded parallel execution with ThreadPoolExecutor
- Structured JSON output with conceded_to, disagrees_with, new_insights, updated_confidence
- Standalone demo runner (no framework needed — just openai library)

**Limitations:**
- Plugin foundation only — no actual council behavior implemented yet
- Single provider (DeepSeek) in demo — no multi-provider, no fallback
- No chairman synthesis, no cascade-breaking, no minority report
- No quorum, no error handling, no token cap

### 5. rachittshah/llmcouncil (26 stars)
**Repo:** https://github.com/rachittshah/llmcouncil
**Created:** 2026

Multi-LLM deliberation council as MCP server + Claude Code skill. 6 protocols:
vote, debate, synthesize, critique, redteam, MAV (Model as Verifier).

**Findings incorporated:**
- Protocol selection (6 protocols for different question types)
- Adaptive stopping via KS statistic (cuts costs up to 94.5%)
- Key research insight: "Scale agents, not rounds" — adding models improves quality more than adding debate turns
- Heterogeneous models outperform homogeneous (mixing providers produces stronger consensus)

## Academic Research

### Du et al. (2023) — Improving Factuality and Reasoning Through Multiagent Debate
**Paper:** https://arxiv.org/abs/2305.14325

**Finding:** Multi-agent debate improves factuality and reasoning over single-model
responses. Agents exchange responses over multiple rounds, iteratively refining.

**Incorporated:** Foundation for the cross-examination phase. Each member seeing
others' positions and revising produces better outcomes than independent-only review.

### Liang et al. (2023) — Encouraging Divergent Thinking in Multi-Agent LLMs
**Paper:** arXiv:2305.19118 (MAD framework)

**Finding:** Heterogeneous mixture of roles and LLMs produces better debate outcomes
than homogeneous panels. Different roles (optimist, pessimist, mediator) reduce
groupthink.

**Incorporated:** Dynamic agent composition (Phase 0) generates advisors with diverse
initial positions, not just diverse expertise. At least one structurally skeptical
advisor is mandatory.

### Choi et al. (2025) — Debate or Vote: Which Yields Better Decisions?
**Paper:** NeurIPS 2025

**Finding:** Direct comparison of debate vs voting protocols for multi-agent LLMs.
Different question types benefit from different decision protocols.

**Incorporated:** Protocol selection (6 protocols). `vote` for quick consensus,
`deliberate` for high-stakes, `critique` for peer review, `redteam` for adversarial.

### Kaesberg et al. (2025) — Voting or Consensus? Decision-Making in Multi-Agent Debate
**Paper:** ACL 2025 Findings

**Finding:** Systematic comparison of voting vs consensus mechanisms in multi-agent
debate. Neither dominates — the optimal mechanism depends on question type.

**Incorporated:** Chairman makes a judgment call (not a vote, not a consensus).
The chairman sees rankings and cross-examination but produces a deliberate verdict.

### Emergence of Biased Consensus in Multi-Agent LLM Debates (2026)
**Paper:** arXiv:2608.02827

**Finding:** Multi-agent LLM debates can produce biased consensus through deliberation
dynamics. Agent heterogeneity (different models/providers) reduces biased lock-in
and improves decision quality on real-world tasks.

**Incorporated:** Multi-provider panel (not same-model sub-agents). Diversity
validation flags provider concentration. Runtime model deduplication prevents
same-model collisions.

### Shortcut Cascades in Multi-Agent Committees (2026)
**Paper:** arXiv:2608.03744 (in KENSEI wiki as `shortcut-cascades-multi-agent-committees`)

**Finding:** Multi-agent committees resist benchmark-gaming shortcuts in isolation
(5-16% flip rate) but a socially plausible cascade can propagate gaming through
the committee despite individual resistance. The failure mode is the interaction
pattern, not any single agent.

**Incorporated:** Cascade-Breaker (Phase 2b). A designated skeptic re-derives the
verdict from first principles, ignoring all prior agent signals. The chairman
sees both the cascade-breaker output and the original deliberation, breaking
plausible-but-wrong cascades.

### Σ-Mem: Online Reliability Memory for LLM Multi-Agent Systems (2026)
**Paper:** arXiv:2607.27958 (in KENSEI wiki as `sigma-mem-reliability-memory`)

**Finding:** Existing memory systems in LLM agents preserve interaction content
but don't model peer trustworthiness or reliability. Σ-Mem records historical
competence evidence and peer relationship evidence, updated from post-decision
correctness feedback.

**Incorporated:** Plugin hook interface for reliability-weighted aggregation.
The council defines a `get_reliability(member_id) → float` interface that
external plugins can implement to weight chairman synthesis by learned
member reliability. Not a core dependency — optional module.

### GroupDebate: Enhancing Multi-Agent Debate Efficiency (2026)
**Paper:** AAMAS 2026 (arXiv:2409.14051)

**Finding:** Multi-agent debate with 3 agents in 5 rounds can raise accuracy from
50% to 98% but introduces 101x token cost. Group discussion reduces token cost
significantly while maintaining quality.

**Incorporated:** Token cap tracking across all phases. Adaptive stopping option
(KS statistic) for debate-style protocols to eliminate wasted rounds.

### 18-Agent Council (Towards AI article, 2026)
**Source:** https://towardsai.com/p/machine-learning/one-ai-cant-really-disagree-with-itself-so-i-wired-up-a-council-of-18

**Finding:** A single LLM has one prior. When you ask one model to argue against
itself, the rebuttal isn't independent thinking. Structured multi-persona
deliberation with adversarial design (consensus mechanically harder to reach
than dissent) produces genuinely independent perspectives.

**Incorporated:** Evidence labeling (empirical / mechanistic / strategic / ethical /
heuristic). Anti-recursion rule concept — the cascade-breaker prevents infinite
questioning loops. Consensus is a flag, not a conclusion.

### MAGI: Deliberative Multi-LLM Council (2026)
**Source:** https://jasontc.net/work/magi.html

**Finding:** Three LLMs answer in parallel, then optionally review each other's
anonymised responses and revise. A rapporteur writes the synthesis; the
lowest-confidence model writes the minority report.

**Incorporated:** Minority Report (Phase 3b). The lowest-confidence panel member
writes a dissenting opinion preserved alongside the verdict. Disagreement is
recorded, not averaged away. Fallback chains handle permanent-error cases without
dropping below quorum.

## KenseiAgent lineage and separation

The standalone skill was informed by KenseiAgent's internal council, but the two are separate products with different contracts:

- KenseiAgent consumes task IDs plus PRD/spec artefacts and participates in a governed revision pipeline.
- This public repository accepts a free-form question and performs one immutable, portable council run.
- KenseiAgent uses Hermes-native provider routing; this CLI uses OpenAI-compatible endpoints and environment credentials.
- The public JSON schema is stable and portable, but it is not described as Kensei's internal pipeline schema.

Patterns carried across in standalone form include fallback chains, quorum failure, diversity warnings, token/deadline governance and fail-closed verdicts. Kensei-only mechanisms such as the external REVISE loop, cached pipeline verdicts, `custom:Name` routing and feature-stage gates are deliberately not claimed here.

Engineering tests demonstrate that the standalone mechanisms execute as documented. They do not transfer Kensei's operational history or prove live-provider quality; release notes must record those evidence levels separately.
