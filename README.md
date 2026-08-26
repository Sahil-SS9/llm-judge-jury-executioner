# LLM Judge Jury Executioner — Multi-Model Deliberation Skill

![LLM Judge Jury Executioner](assets/banner.png)

Stop trusting a single LLM's first answer for high-stakes decisions. Run any
question through a council of diverse AI advisors who independently reason,
cross-examine each other's positions, rank responses anonymously, and produce
a chairman-synthesized verdict — with dissent preserved as a minority report.

## What It Does

```
Your Question
    ↓
Phase 0: Compose       — LLM generates N diverse advisors (distinct positions, not just expertise)
    ↓
Phase 1: Independent   — All advisors answer in parallel, evidence-labeled claims
    ↓
Phase 2: Cross-Exam    — Advisors see each other's positions (anonymised), concede/disagree/revise
         + Ranking     — Anonymised peer ranking (no model identity bias)
    ↓
Phase 2b: Cascade-Breaker — Skeptic re-derives verdict from first principles
    ↓
Phase 3: Chairman      — Synthesizes APPROVED/REVISE verdict
         + Minority    — Lowest-confidence advisor writes dissent report
    ↓
Verdict (MD) + HTML Report + JSON Transcript + Minority Report
```

## Comparison with Karpathy's LLM Council

| Feature | Karpathy LLM Council | LLM Judge Jury Executioner |
|---------|---------------------|---------------------------|
| Format | Local web app (Python + JS) | Portable skill (SKILL.md + standalone Python engine) |
| Provider model | Single provider (OpenRouter) | Multi-provider with per-member fallback chains + shared pool |
| Panel composition | Static config | Dynamic agent composition (Phase 0 generates diverse personas) |
| Deliberation phases | 3 (review → rank → chairman) | 5 (compose → review → cross-exam + rank → cascade-breaker → chairman + minority) |
| Cross-examination | No — ranking only | Yes — members concede, disagree, and revise before ranking |
| Cascade-breaking | No | Yes — skeptic re-derives verdict from first principles |
| Minority report | No | Yes — lowest-confidence member preserves dissent |
| Evidence labeling | No | Yes — every claim tagged [empirical] [mechanistic] [strategic] [ethical] [heuristic] |
| Protocol selection | Single protocol | 6 protocols: deliberate, vote, synthesize, critique, redteam, mav |
| Adaptive stopping | No | Yes — KS statistic convergence detection |
| Fallback chains | No | Per-member + shared fallback pool (13 entries, 4 providers) |
| Quorum handling | No | Quorum minimum with auto-REVISE on failure |
| Error classification | No | Transient vs permanent error handling |
| Token cap | No | Enforced mid-deliberation |
| REVISE loop | No | Capped loop with escalation |
| Diversity validation | No | Cross-owner model duplication + provider concentration warnings |
| HTML report | No | Yes — visual report with agreement map and clash points |
| Research backing | None cited | 10+ academic papers cited |
| Production-hardened | No (vibe-coded, unsupported) | Yes — 20+ pitfalls fixed in production |
| Platform | Web browser only | Claude Code, Hermes Agent, CLI, CI/CD |

## Installation

### In Claude Code / Hermes Agent

```bash
git clone https://github.com/Sahil-SS9/llm-judge-jury-executioner ~/.claude/skills/llm-council
# or for Hermes:
git clone https://github.com/Sahil-SS9/llm-judge-jury-executioner ~/.hermes/skills/llm-council
```

### Direct CLI

```bash
git clone https://github.com/Sahil-SS9/llm-judge-jury-executioner
cd llm-judge-jury-executioner
pip install openai pyyaml
```

## Configuration

Copy the example config and add your API keys:

```bash
cp examples/example-config.yaml council-config.yaml
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="..."
```

Or use OpenRouter as a unified provider (one key, all models):

```bash
export OPENROUTER_API_KEY="sk-or-..."
```

See `references/config-reference.md` for the full schema.

## Usage

### From Claude Code / Hermes

Type any trigger phrase followed by your question:

```
council this: Should I use Postgres or MongoDB for a social app with 10k users?
```

### Direct CLI

```bash
python3 scripts/council_engine.py \
  --question "Should I launch a $97 workshop or a $497 course?" \
  --config council-config.yaml \
  --output-dir ./council-output
```

### Pipe input

```bash
echo "Is this architecture a good idea?" | python3 scripts/council_engine.py --config council-config.yaml
```

### JSON output (for pipelines)

```bash
python3 scripts/council_engine.py \
  --question "Which framework should I use?" \
  --config council-config.yaml \
  --json
```

## Outputs

| File | Description |
|------|-------------|
| `council-verdict.md` | Human-readable verdict: APPROVED/REVISE + issues |
| `council-verdict.json` | Machine-readable verdict + all phase data |
| `council-report.html` | Visual report: agreement map, clash points |
| `minority-report.md` | Dissenting position from lowest-confidence member |
| `council-transcript.json` | Full transcript of all phases |

## Protocols

| Protocol | When to use |
|----------|-------------|
| `deliberate` | High-stakes decisions (default) |
| `vote` | Quick consensus, multiple choice |
| `synthesize` | Open-ended questions |
| `critique` | Peer review of code/writing |
| `redteam` | Adversarial testing, security |
| `mav` | Model-as-verifier, fact-checking |

## Research Basis

This skill synthesizes findings from 10+ academic papers and 5 community repos.
See `references/research-basis.md` for full citations.

Key findings:
- **Scale agents, not rounds** — adding models improves quality more than adding debate turns
- **Heterogeneous models outperform homogeneous** — mixing providers produces stronger consensus
- **Anonymous peer review prevents provider bias**
- **Cascade-breaking prevents socially plausible shortcut propagation**
- **Minority reports preserve dissent and improve auditability**
- **Evidence labeling prevents hiding opinion as fact**

## License

MIT — see [LICENSE](LICENSE).