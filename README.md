# LLM Judge Jury Executioner — Multi-Model Deliberation Skill

![LLM Judge Jury Executioner](assets/banner.png)

Run a decision through several independent models, then apply the protocol that fits the job: majority vote, chairman synthesis, peer critique, adversarial red-team review, model-as-verifier, or full deliberation.

Status: v1.1 is tested as a standalone public skill/CLI. Mocked tests and CI prove orchestration, safety boundaries and failure semantics. Real-provider output quality is not claimed unless a release explicitly records a live pilot. This repository is not a drop-in replacement for KenseiAgent's internal PRD/spec council.

## What it does

The full `deliberate` path is:

```text
Question + bounded workspace context
  → Phase 0: dynamic panel composition
  → Phase 1: independent reviews in parallel
  → Phase 2: anonymised cross-examination and peer ranking
  → adaptive-stop check (optional)
  → Phase 2b: independent cascade-breaker
  → Phase 3: chairman synthesis
  → minority report (optional)
  → Markdown + stable JSON + escaped HTML + transcript
```

Other protocols intentionally run smaller, distinct phase sets.

## Key properties

- Six implemented protocols with fail-closed config validation.
- Per-member and shared provider fallback chains.
- Runtime model collision prevention without blocking sequential model reuse.
- Overall deadline and token cap checked after every phase.
- Quorum failure returns top-level `REVISE` and still writes audit artefacts.
- Questions, workspace files and model outputs are fenced as untrusted data in downstream prompts.
- Cross-examination and ranking strip provider, model and persona identity.
- Cascade-breaking is genuinely independent: it is not shown panel signals.
- HTML output escapes every model-controlled value.
- Workspace context scanning is allowlisted, non-recursive and bounded.
- Pinned runtime/dev dependencies, Python 3.10-3.13 CI and an installable CLI.

## Protocols

| Protocol | Executed phases | Decision rule | Use case |
|---|---|---|---|
| `deliberate` | compose → independent → cross-exam → ranking → cascade → chairman | chairman judgment | High-stakes decisions |
| `vote` | independent → ranking | simple majority; ties revise | Prioritisation and binary choices |
| `synthesize` | independent → chairman | chairman synthesis | Open-ended questions |
| `critique` | independent → cross-exam | any material revise vote blocks | Code, writing and plan review |
| `redteam` | independent → cascade → chairman | chairman weighs adversarial findings | Security and failure modes |
| `mav` | independent → ranking | unanimous approval required | Fact-checking and validation |

Feature flags can disable optional phases that belong to a protocol. They do not add phases to a smaller protocol.

`adaptive_stopping` currently applies to `deliberate` when both cross-examination and ranking are enabled. It compares initial and revised confidence distributions; when stable, ranking is skipped and the reason is recorded.

## Installation

### Hermes Agent or Claude Code skill

```bash
git clone https://github.com/Sahil-SS9/llm-judge-jury-executioner ~/.hermes/skills/llm-council
# Claude Code users can clone the same repository into their skills directory.
```

### Standalone CLI

```bash
git clone https://github.com/Sahil-SS9/llm-judge-jury-executioner
cd llm-judge-jury-executioner
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install .
llm-jje-council --help
```

For development:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check scripts tests
```

## Configuration

Copy the safe placeholder config and replace model IDs with models available from providers you already use:

```bash
cp examples/example-config.yaml council-config.yaml
export OPENAI_API_KEY="..."
export GOOGLE_API_KEY="..."
export OPENROUTER_API_KEY="..."
```

Do not put credentials in the YAML file. Provider credentials stay in environment variables. See `references/config-reference.md` for the full schema.

## Usage

```bash
llm-jje-council \
  --question "Should this architecture ship?" \
  --config council-config.yaml \
  --output-dir ./council-output
```

Or without package installation:

```bash
python3 scripts/council_engine.py \
  --question "Should this architecture ship?" \
  --config council-config.yaml \
  --output-dir ./council-output
```

Pipe input:

```bash
echo "Is this plan safe?" | python3 scripts/council_engine.py --config council-config.yaml
```

Override a configured protocol:

```bash
python3 scripts/council_engine.py -c council-config.yaml -p redteam -q "Threat-model this"
```

## Outputs

| File | Description |
|---|---|
| `council-verdict.md` | Human-readable APPROVED/REVISE decision |
| `council-verdict.json` | Stable schema with top-level `verdict`, `issues`, phase data and budgets |
| `council-report.html` | Escaped standalone visual report |
| `minority-report.md` | Optional dissent from the correct originating member |
| `council-transcript.json` | Full phase outputs |

On token-cap or timeout failure, the engine writes fail-closed diagnostic artefacts and then raises. This keeps automation honest without losing evidence.

## Context scanning

When `scan_context: true`, the engine reads only these files from `context_root` (or the current directory):

- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `pyproject.toml`

The scan is non-recursive, ignores symlinks and hidden files, and is capped by `context_max_chars`. It never reads `.env`.

## Provider compatibility

The engine uses OpenAI-compatible APIs. Built-in routes exist for OpenAI, Anthropic's compatibility endpoint, Google's official OpenAI compatibility endpoint, OpenRouter and a custom endpoint. Model IDs remain provider-specific; the example config uses placeholders rather than recommending a subscription or model.

## Release and rollback

See `references/operations.md` for the pre-release gate, live-pilot boundary, partial-failure behaviour, rollout and rollback procedure.

## Research basis

The architecture is research-informed. See `references/research-basis.md` for citations and the distinction between source findings, design inspiration and behaviour actually implemented here.

## License

MIT — see [LICENSE](LICENSE).
