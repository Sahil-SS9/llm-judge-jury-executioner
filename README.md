# LLM Council — Multi-Model Deliberation Skill

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

## Why This Is Different

| Feature | Karpathy | aiwithremy | tenfoldmarc | magnus919 | rachittshah | **This Skill** |
|---------|----------|------------|-------------|-----------|-------------|----------------|
| Multi-provider panel | Via OpenRouter | ❌ (Claude only) | ❌ (Claude only) | ❌ (single) | ✅ | ✅ |
| Fallback chains | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (per-member + shared pool) |
| Quorum + error handling | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Dynamic agent composition | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ |
| Cross-examination | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ |
| Cascade-breaker (skeptic) | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Minority report | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Evidence labeling | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| HTML visual report | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| Protocol selection | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ (6 protocols) |
| Adaptive stopping | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| REVISE loop with cap | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Token cap tracking | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Diversity validation | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Skill format (portable) | ❌ (web app) | ✅ | ✅ | ❌ (plugin) | ✅ | ✅ |
| Research-backed | ❌ | ❌ | ❌ | Partial | Partial | ✅ (10+ citations) |
| Production-hardened | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (20+ pitfalls fixed) |

## Installation

### In Claude Code / Hermes Agent

```bash
git clone https://github.com/Sahil-SS9/llm-council-skill ~/.claude/skills/llm-council
# or for Hermes:
git clone https://github.com/Sahil-SS9/llm-council-skill ~/.hermes/skills/llm-council
```

### Direct CLI

```bash
git clone https://github.com/Sahil-SS9/llm-council-skill
cd llm-council-skill
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

## Credits

- [Andrej Karpathy](https://github.com/karpathy/llm-council) — original LLM Council concept
- [Ole Lehmann (aiwithremy)](https://github.com/aiwithremy/claude-skills-llm-council) — Claude Code skill format
- [tenfoldmarc](https://github.com/tenfoldmarc/llm-council-skill) — HTML report + advisor personas
- [magnus919](https://github.com/magnus919/hermes-council) — dynamic agent composition + cross-examination
- [rachittshah](https://github.com/rachittshah/llmcouncil) — protocol selection + adaptive stopping
- [MAGI](https://magi-council.org) — minority report pattern
- Academic research: Du et al. (2023), Liang et al. (2023), Choi et al. (2025),
  Kaesberg et al. (2025), and others — see `references/research-basis.md`