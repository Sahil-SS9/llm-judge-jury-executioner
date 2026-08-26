#!/usr/bin/env python3
"""
LLM Judge Jury Executioner Engine — Standalone Multi-Model Deliberation

Runs a 5-phase council deliberation on any question using multiple LLM providers.
Requires only the `openai` Python package (pip install openai) and a YAML parser
(pip install pyyaml). No agent framework needed.

Usage:
    python3 council_engine.py --question "Should I use Postgres or MongoDB?" \
        --config example-config.yaml --output-dir ./council-output

    # Or pipe a question:
    echo "Is this a good idea?" | python3 council_engine.py --config config.yaml

    # Or let the agent call it:
    python3 council_engine.py --question "..." --config config.yaml --json

Phases:
    0. Compose       — Dynamic agent assembly (diverse initial positions)
    1. Independent Review — Parallel responses from all panel members
    2. Cross-Examination + Anonymised Peer Ranking
    2b. Cascade-Breaker — Skeptic re-derives verdict from first principles
    3. Chairman + Minority Report — Synthesis + preserved dissent

Protocols: deliberate (default), vote, synthesize, critique, redteam, mav

License: MIT
Author: Sahil Saghir
"""

import argparse
import hashlib
import json
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# --- Dependencies (graceful) ---
try:
    import yaml
except ImportError:
    yaml = None  # Config can be JSON too

try:
    from openai import OpenAI
except ImportError:
    print("ERROR: 'openai' package required. Install: pip install openai", file=sys.stderr)
    sys.exit(1)


# ============================================================
# CONFIGURATION
# ============================================================

PROVIDER_DEFAULTS = {
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
    },
    "anthropic": {
        "env_key": "ANTHROPIC_API_KEY",
        "base_url": "https://api.anthropic.com/v1",
    },
    "google": {
        "env_key": "GOOGLE_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1",
    },
    "openrouter": {
        "env_key": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
    },
    "custom": {
        "env_key": "CUSTOM_API_KEY",
        "base_url": None,  # Must set CUSTOM_BASE_URL
    },
}

EVIDENCE_LABELS = ["empirical", "mechanistic", "strategic", "ethical", "heuristic"]

DEFAULT_CONFIG = {
    "panel_size": 3,
    "protocol": "deliberate",
    "compose": True,
    "cross_examination": True,
    "cascade_breaker": True,
    "minority_report": True,
    "html_report": True,
    "evidence_labels": True,
    "quorum_min": 2,
    "max_revise_loops": 4,
    "timeout_seconds": 600,
    "member_timeout_seconds": 180,
    "token_cap": 200000,
    "adaptive_stopping": False,
    "scan_context": True,
    "panel": [],
    "chairman": {},
    "fallback_pool": [],
}


@dataclass
class PanelMember:
    provider: str
    model: str
    name: str = ""
    fallback: list = field(default_factory=list)
    api_key: str = ""
    base_url: str = ""


@dataclass
class CouncilConfig:
    panel_size: int = 3
    protocol: str = "deliberate"
    compose: bool = True
    cross_examination: bool = True
    cascade_breaker: bool = True
    minority_report: bool = True
    html_report: bool = True
    evidence_labels: bool = True
    quorum_min: int = 2
    max_revise_loops: int = 4
    timeout_seconds: int = 600
    member_timeout_seconds: int = 180
    token_cap: Optional[int] = 200000
    adaptive_stopping: bool = False
    scan_context: bool = True
    panel: list = field(default_factory=list)
    chairman: dict = field(default_factory=dict)
    fallback_pool: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "CouncilConfig":
        c = cls()
        for k, v in d.items():
            if hasattr(c, k):
                setattr(c, k, v)
        return c

    def validate_diversity(self) -> list[str]:
        """Structural lint: flag cross-owner model duplication and provider concentration."""
        warnings = []
        all_roles = list(self.panel) + [self.chairman] if self.chairman else list(self.panel)
        # Cross-owner model duplication
        model_owners = {}
        for i, m in enumerate(self.panel):
            model = m.get("model", "")
            if model in model_owners:
                warnings.append(f"Model '{model}' appears in multiple panel members (#{model_owners[model]} and #{i})")
            model_owners[model] = i
        # Provider concentration
        provider_counts = {}
        for m in self.panel:
            p = m.get("provider", "")
            provider_counts[p] = provider_counts.get(p, 0) + 1
        if self.chairman:
            p = self.chairman.get("provider", "")
            provider_counts[p] = provider_counts.get(p, 0) + 1
        for p, count in provider_counts.items():
            if count >= 3:
                warnings.append(f"Provider '{p}' has {count} roles — single-provider outage risk")
        return warnings


def load_config(config_path: str) -> CouncilConfig:
    """Load config from YAML or JSON file, merged over defaults."""
    with open(config_path) as f:
        if config_path.endswith((".yaml", ".yml")):
            if yaml is None:
                raise RuntimeError("pyyaml required for YAML config: pip install pyyaml")
            raw = yaml.safe_load(f)
        else:
            raw = json.load(f)
    council_section = raw.get("council", raw)
    return CouncilConfig.from_dict(council_section)


def resolve_provider(member: dict) -> tuple[str, str]:
    """Resolve API key and base_url for a provider entry."""
    provider = member.get("provider", "openai")
    model = member.get("model", "")

    if provider in PROVIDER_DEFAULTS:
        defaults = PROVIDER_DEFAULTS[provider]
        api_key = os.environ.get(defaults["env_key"], "")
        base_url = member.get("base_url") or defaults["base_url"] or os.environ.get("CUSTOM_BASE_URL", "")
    else:
        # Custom provider name
        env_key = f"{provider.upper().replace('-', '_')}_API_KEY"
        api_key = os.environ.get(env_key, os.environ.get("CUSTOM_API_KEY", ""))
        base_url = member.get("base_url", os.environ.get("CUSTOM_BASE_URL", ""))

    return api_key, base_url, model, provider


# ============================================================
# LLM CALLING
# ============================================================

TRANSIENT_ERRORS = {429, 402, 408, 409, 500, 502, 503, 504, 529}
PERMANENT_ERRORS = {400, 401, 403, 404, 422}


def call_llm(
    member: dict,
    system_prompt: str,
    user_prompt: str,
    timeout: int = 180,
    max_tokens: int = 4000,
    temperature: float = 0.7,
    active_models: Optional[set] = None,
    fallback_pool: Optional[list] = None,
) -> tuple[str, int]:
    """
    Call an LLM with fallback chain support.
    Returns (response_text, total_tokens).
    Raises RuntimeError on permanent failure or all fallbacks exhausted.
    """
    # Build the call chain: primary → per-member fallbacks → shared pool
    call_chain = [member]
    for fb in member.get("fallback", []):
        call_chain.append(fb)
    if fallback_pool:
        for fp in fallback_pool:
            call_chain.append(fp)

    total_tokens = 0
    last_error = ""

    for candidate in call_chain:
        api_key, base_url, model, provider = resolve_provider(candidate)

        if not api_key:
            last_error = f"No API key for provider '{provider}'"
            continue
        if not base_url:
            last_error = f"No base_url for provider '{provider}'"
            continue

        # Runtime model deduplication
        model_name = candidate.get("model", "")
        if active_models and model_name in active_models:
            continue  # Skip — model already in use by another active member
        if active_models:
            active_models.add(model_name)

        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            text = resp.choices[0].message.content.strip()
            usage = getattr(resp, "usage", None)
            tokens = getattr(usage, "total_tokens", 0) if usage else 0
            return text, tokens

        except Exception as e:
            err_str = str(e)
            last_error = err_str
            # Check if transient
            status = getattr(e, "status_code", None)
            if status and status in PERMANENT_ERRORS:
                # Permanent error — fail immediately
                raise RuntimeError(f"Permanent error from {provider}/{model}: {err_str}")
            # Transient — try next fallback
            if active_models and model_name:
                active_models.discard(model_name)  # Release for retry
            continue

    raise RuntimeError(f"All fallbacks exhausted. Last error: {last_error}")


def parse_json_response(text: str) -> dict:
    """Lenient JSON parser for LLM output."""
    text = text.strip()
    # Strip markdown fences
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("{") or p.startswith("["):
                text = p
                break
    # Remove leading/trailing non-JSON
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try fixing unescaped newlines
        try:
            fixed = text.replace("\n", "\\n").replace("\r", "\\r")
            return json.loads(fixed)
        except json.JSONDecodeError:
            return {"raw": text, "parse_error": True}


# ============================================================
# PHASE 0: COMPOSE — Dynamic Agent Assembly
# ============================================================

COMPOSE_SYSTEM = "You are an expert at designing diverse debate panels."
COMPOSE_PROMPT = """Design {n} expert debating advisors for the question: "{question}"

CRITICAL DIRECTIVE: Prioritize diversity of INITIAL POSITION over diversity of expertise.
Research shows that a group with distinct approaches to a problem outperforms a group
with more expertise but shared framing.

For each advisor provide:
- name: first and last name
- background: one paragraph
- expertise: their domain
- analytical_approach: how they think about problems
- bias: their known lean
- confidence_calibration: 0.0-1.0
- initial_position: a brief stance they'd take BEFORE seeing evidence

At least one advisor should be structurally skeptical (red-team role).
At least one should approach from a fundamentally different cognitive frame.
Every position should be defensible. No strawman positions.

Return ONLY a raw JSON array. No markdown, no code fences. Start with [ and end with ]."""


def phase_compose(question: str, n: int, chairman: dict, fallback_pool: list, active_models: set) -> list[dict]:
    """Phase 0: Generate diverse advisor personas using the chairman model."""
    print("[Phase 0] Composing diverse advisor panel...")

    prompt = COMPOSE_PROMPT.format(n=n, question=question)
    text, tokens = call_llm(
        chairman,
        COMPOSE_SYSTEM,
        prompt,
        timeout=180,
        max_tokens=8000,
        active_models=active_models,
        fallback_pool=fallback_pool,
    )

    advisors = parse_json_response(text)
    if isinstance(advisors, dict) and "raw" in advisors:
        # Parse failed — try to extract array
        raw = advisors["raw"]
        start = raw.find("[")
        end = raw.rfind("]")
        if start != -1 and end != -1:
            try:
                advisors = json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                advisors = []
        else:
            advisors = []

    if not isinstance(advisors, list) or len(advisors) < 2:
        print(f"  [WARN] Compose returned {len(advisors) if isinstance(advisors, list) else 0} advisors, falling back to generic personas")
        # Fallback generic personas
        personas = ["The Contrarian", "The First Principles Thinker", "The Expansionist", "The Outsider", "The Executor"]
        advisors = [{"name": p, "background": "Expert advisor", "expertise": "General",
                      "analytical_approach": "Independent reasoning", "bias": "None",
                      "confidence_calibration": 0.5, "initial_position": "Neutral"} for p in personas[:n]]

    print(f"  Composed {len(advisors)} advisors:")
    for a in advisors[:n]:
        print(f"    {a.get('name', '?')} — {a.get('expertise', '?')[:60]}")
    return advisors[:n]


# ============================================================
# PHASE 1: INDEPENDENT REVIEW (Parallel)
# ============================================================

PHASE1_SYSTEM = """You are {name}, a debate panelist with the following profile:
BACKGROUND: {background}
EXPERTISE: {expertise}
APPROACH: {analytical_approach}
BIAS: {bias}

You are answering the following question as this persona. Be specific and grounded."""

PHASE1_PROMPT = """Question: {question}

Form your position on this question. Be specific and grounded in your experience.

{evidence_directive}

Return JSON only:
{{"position": "your position statement", "reasoning": ["point 1", "point 2", ...],
"concerns": ["concern 1", ...], "confidence": 0.0-1.0,
"evidence_needed": "single piece of evidence that would change your mind"}}"""


def phase_independent_review(
    question: str,
    panel: list[dict],
    config: CouncilConfig,
    active_models: set,
    fallback_pool: list,
    advisors: Optional[list[dict]] = None,
) -> tuple[list[dict], int]:
    """Phase 1: Each panel member answers independently in parallel."""
    print("[Phase 1] Independent review (parallel)...")

    evidence_directive = ""
    if config.evidence_labels:
        evidence_directive = (
            "EVIDENCE LABELING: Tag every claim with its evidence type in brackets: "
            "[empirical] [mechanistic] [strategic] [ethical] [heuristic]. "
            "This prevents hiding opinion as fact."
        )

    results = {}
    total_tokens = 0
    errors = []

    def run_member(idx, member):
        nonlocal total_tokens
        persona = advisors[idx] if advisors and idx < len(advisors) else None

        if persona:
            system = PHASE1_SYSTEM.format(
                name=persona.get("name", f"Advisor {chr(65 + idx)}"),
                background=persona.get("background", "Expert advisor"),
                expertise=persona.get("expertise", "General"),
                analytical_approach=persona.get("analytical_approach", "Independent reasoning"),
                bias=persona.get("bias", "None"),
            )
        else:
            system = f"You are Advisor {chr(65 + idx)}, an independent expert answering a question."

        prompt = PHASE1_PROMPT.format(question=question, evidence_directive=evidence_directive)

        try:
            text, tokens = call_llm(
                member,
                system,
                prompt,
                timeout=config.member_timeout_seconds,
                max_tokens=4000,
                active_models=active_models,
                fallback_pool=fallback_pool,
            )
            data = parse_json_response(text)
            if persona:
                data["persona"] = persona
            data["member_index"] = idx
            data["member_model"] = member.get("model", "")
            return idx, data, tokens
        except Exception as e:
            return idx, {"error": str(e), "member_index": idx}, 0

    with ThreadPoolExecutor(max_workers=len(panel)) as executor:
        futures = {executor.submit(run_member, i, m): i for i, m in enumerate(panel)}
        for future in as_completed(futures):
            idx, data, tokens = future.result()
            total_tokens += tokens
            if "error" in data:
                errors.append(f"Member {idx}: {data['error']}")
                print(f"  Member {chr(65 + idx)} — ERROR: {data['error'][:80]}")
            else:
                results[idx] = data
                print(f"  Advisor {chr(65 + idx)} (confidence: {data.get('confidence', '?')}) — {data.get('position', 'N/A')[:80]}")

    critiques = [results[i] for i in sorted(results.keys())]
    print(f"  {len(critiques)}/{len(panel)} members responded successfully")

    if len(critiques) < config.quorum_min:
        print(f"  [WARN] Quorum failure: only {len(critiques)} members, need {config.quorum_min}")

    return critiques, total_tokens


# ============================================================
# PHASE 2: CROSS-EXAMINATION + ANONYMISED PEER RANKING
# ============================================================

CROSS_EXAM_SYSTEM = """You are {name}, a debate panelist. You have read the other panelists'
positions and now respond to them. Your identity is hidden from them and theirs from you."""

CROSS_EXAM_PROMPT = """Question: {question}

Here are the other panelists' positions (anonymised):
{positions}

Review their arguments. Where do you concede? Where do you disagree? What new insights emerge?

Return JSON only:
{{"revised_position": "your updated position",
"conceded_to": [{{"advisor": "A", "point": "...", "what_changed_my_mind": "..."}}],
"disagrees_with": [{{"advisor": "B", "point": "..."}}],
"new_insights": ["..."],
"updated_confidence": 0.0-1.0}}"""

RANKING_SYSTEM = "You are evaluating responses to a question. Rank them anonymously."
RANKING_PROMPT = """Question: {question}

Here are {n} anonymised responses:
{responses}

Rank these responses from best to worst based on:
- Accuracy and correctness
- Completeness and depth
- Clarity and usefulness

Provide your ranking as a list of labels (e.g., ["A", "C", "B"]) with brief justification.

Return JSON only:
{{"ranking": ["A", "C", "B"], "justification": "...",
"strengths": {{"A": "...", "B": "...", "C": "..."}},
"weaknesses": {{"A": "...", "B": "...", "C": "..."}}}}"""


def phase_cross_examination_and_ranking(
    question: str,
    critiques: list[dict],
    panel: list[dict],
    config: CouncilConfig,
    active_models: set,
    fallback_pool: list,
    advisors: Optional[list[dict]] = None,
) -> tuple[list[dict], dict, int]:
    """Phase 2: Cross-examination then anonymised peer ranking."""
    print("[Phase 2] Cross-examination + peer ranking...")

    total_tokens = 0
    cross_exam_results = {}
    rankings = {}

    # --- Cross-Examination ---
    if config.cross_examination and len(critiques) > 1:
        print("  [Cross-examination] Each member reviews others' positions...")
        labels = [chr(65 + i) for i in range(len(critiques))]

        def run_cross(idx, member):
            persona = advisors[idx] if advisors and idx < len(advisors) else None
            name = persona.get("name", f"Advisor {labels[idx]}") if persona else f"Advisor {labels[idx]}"
            system = CROSS_EXAM_SYSTEM.format(name=name)
            positions = "\n\n".join(
                f"Advisor {labels[j]}:\n{json.dumps(critiques[j], indent=2)}"
                for j in range(len(critiques)) if j != idx
            )
            prompt = CROSS_EXAM_PROMPT.format(question=question, positions=positions)
            try:
                text, tokens = call_llm(
                    member, system, prompt,
                    timeout=config.member_timeout_seconds, max_tokens=4000,
                    active_models=active_models, fallback_pool=fallback_pool,
                )
                return idx, parse_json_response(text), tokens
            except Exception as e:
                return idx, {"error": str(e)}, 0

        with ThreadPoolExecutor(max_workers=len(critiques)) as executor:
            futures = {executor.submit(run_cross, i, p): i for i, p in enumerate(panel[: len(critiques)])}
            for future in as_completed(futures):
                idx, data, tokens = future.result()
                total_tokens += tokens
                if "error" not in data:
                    cross_exam_results[idx] = data
                    conceded = data.get("conceded_to", [])
                    disagrees = data.get("disagrees_with", [])
                    conf = data.get("updated_confidence", "?")
                    print(f"    Advisor {labels[idx]} (conf: {conf}) — conceded {len(conceded)}, disagrees {len(disagrees)}")

    # --- Anonymised Peer Ranking ---
    print("  [Ranking] Anonymised peer ranking...")
    labels = [chr(65 + i) for i in range(len(critiques))]
    responses_text = "\n\n".join(
        f"Advisor {labels[i]}:\n{json.dumps(critiques[i], indent=2)}"
        for i in range(len(critiques))
    )

    def run_ranking(idx, member):
        prompt = RANKING_PROMPT.format(question=question, n=len(critiques), responses=responses_text)
        try:
            text, tokens = call_llm(
                member, RANKING_SYSTEM, prompt,
                timeout=config.member_timeout_seconds, max_tokens=3000,
                active_models=active_models, fallback_pool=fallback_pool,
            )
            return idx, parse_json_response(text), tokens
        except Exception as e:
            return idx, {"error": str(e)}, 0

    with ThreadPoolExecutor(max_workers=len(critiques)) as executor:
        futures = {executor.submit(run_ranking, i, p): i for i, p in enumerate(panel[: len(critiques)])}
        for future in as_completed(futures):
            idx, data, tokens = future.result()
            total_tokens += tokens
            if "error" not in data:
                rankings[idx] = data
                print(f"    Advisor {labels[idx]} ranking: {data.get('ranking', '?')}")

    return cross_exam_results, rankings, total_tokens


# ============================================================
# PHASE 2b: CASCADE-BREAKER
# ============================================================

CASCADE_BREAKER_SYSTEM = """You are the Cascade-Breaker, a skeptic who must re-derive the verdict
from first principles. You do NOT see other advisors' signals. You independently evaluate
the question and the available evidence. Your job is to catch plausible-but-wrong shortcuts
that could propagate through deliberation dynamics."""

CASCADE_BREAKER_PROMPT = """Question: {question}

Available responses from the panel (for reference only — do NOT build on their reasoning):
{responses}

Re-derive your own independent verdict from first principles. Do not defer to the majority.
Look for:
1. Plausible-but-wrong shortcuts that the panel might be cascading on
2. Claims that sound reasonable but lack empirical grounding
3. Areas where the panel's consensus could be a socially propagated shortcut

Return JSON only:
{{"independent_verdict": "your verdict",
"shortcut_cascade_risk": "any cascade risk identified or 'none'",
"disagreements_with_panel": ["point 1", ...],
"confidence": 0.0-1.0}}"""


def phase_cascade_breaker(
    question: str,
    critiques: list[dict],
    chairman: dict,
    config: CouncilConfig,
    active_models: set,
    fallback_pool: list,
) -> tuple[dict, int]:
    """Phase 2b: Cascade-breaker re-derives verdict from first principles."""
    print("[Phase 2b] Cascade-breaker (skeptic role)...")

    responses = "\n\n".join(
        f"Advisor {chr(65 + i)}:\n{json.dumps(c.get('position', ''), indent=2)}"
        for i, c in enumerate(critiques)
    )
    prompt = CASCADE_BREAKER_PROMPT.format(question=question, responses=responses)

    try:
        text, tokens = call_llm(
            chairman, CASCADE_BREAKER_SYSTEM, prompt,
            timeout=config.member_timeout_seconds, max_tokens=4000,
            active_models=active_models, fallback_pool=fallback_pool,
        )
        result = parse_json_response(text)
        print(f"  Cascade risk: {result.get('shortcut_cascade_risk', 'unknown')}")
        print(f"  Confidence: {result.get('confidence', '?')}")
        return result, tokens
    except Exception as e:
        print(f"  [WARN] Cascade-breaker failed: {e}")
        return {"error": str(e), "shortcut_cascade_risk": "unknown"}, 0


# ============================================================
# PHASE 3: CHAIRMAN SYNTHESIS + MINORITY REPORT
# ============================================================

CHAIRMAN_SYSTEM = """You are the Chairman of the LLM Judge Jury Executioner council. Your job is to synthesize
all responses, cross-examination output, rankings, and the cascade-breaker output into
a single final verdict. You are NOT averaging — you are judging. Where advisors agree,
state the consensus. Where they clash, surface the tension. Where the cascade-breaker
identified risk, weigh it carefully."""

CHAIRMAN_PROMPT = """Question: {question}

Panel responses:
{critiques}

Cross-examination results:
{cross_exam}

Peer rankings:
{rankings}

Cascade-breaker output:
{cascade_breaker}

Synthesize these into a final verdict. Your output:

Return JSON only:
{{"verdict": "APPROVED" or "REVISE",
"recommendation": "clear recommendation to the user",
"where_they_agree": ["point 1", ...],
"where_they_clash": ["point 1", ...],
"blind_spots": ["anything the council missed"],
"issues": ["specific issues if REVISE, empty if APPROVED"],
"concrete_next_step": "one concrete action to take",
"evidence_quality": "assessment of evidence labeling quality"}}"""


def phase_chairman(
    question: str,
    critiques: list[dict],
    cross_exam: dict,
    rankings: dict,
    cascade_breaker: dict,
    chairman: dict,
    config: CouncilConfig,
    active_models: set,
    fallback_pool: list,
) -> tuple[dict, int]:
    """Phase 3: Chairman synthesis."""
    print("[Phase 3] Chairman synthesis...")

    prompt = CHAIRMAN_PROMPT.format(
        question=question,
        critiques=json.dumps(critiques, indent=2),
        cross_exam=json.dumps(cross_exam, indent=2),
        rankings=json.dumps(rankings, indent=2),
        cascade_breaker=json.dumps(cascade_breaker, indent=2),
    )

    try:
        text, tokens = call_llm(
            chairman, CHAIRMAN_SYSTEM, prompt,
            timeout=config.timeout_seconds, max_tokens=6000,
            active_models=active_models, fallback_pool=fallback_pool,
        )
        verdict = parse_json_response(text)
        print(f"  Verdict: {verdict.get('verdict', '?')}")
        print(f"  Recommendation: {verdict.get('recommendation', '?')[:120]}")
        return verdict, tokens
    except Exception as e:
        print(f"  [ERROR] Chairman failed: {e}")
        return {"verdict": "REVISE", "error": str(e),
                "issues": [f"Chairman synthesis failed: {e}"]}, 0


def phase_minority_report(
    question: str,
    critiques: list[dict],
    chairman: dict,
    config: CouncilConfig,
    active_models: set,
    fallback_pool: list,
) -> tuple[Optional[dict], int]:
    """Phase 3b: Lowest-confidence member writes a minority report."""
    if not critiques:
        return None, 0

    # Find lowest-confidence member
    min_conf = 1.0
    min_idx = 0
    for i, c in enumerate(critiques):
        conf = c.get("confidence", c.get("updated_confidence", 0.5))
        try:
            conf = float(conf)
        except (ValueError, TypeError):
            conf = 0.5
        if conf < min_conf:
            min_conf = conf
            min_idx = i

    member = critiques[min_idx]
    print(f"[Phase 3b] Minority report from Advisor {chr(65 + min_idx)} (confidence: {min_conf})...")

    system = """You are writing a minority report. The council has deliberated but your
    position was not adopted. You must clearly state why you disagree with the likely
    majority direction and what risk the council may be overlooking."""

    prompt = f"""Question: {question}

Your position (confidence: {min_conf}):
{json.dumps(member, indent=2)}

Write a concise minority report explaining your dissent. What does the council risk
by not considering your position more seriously?

Return JSON only:
{{"minority_position": "your position",
"dissent_reasoning": "why you disagree with the majority",
"risk_if_ignored": "what could go wrong if the council ignores this",
"confidence_in_dissent": 0.0-1.0}}"""

    # Use the panel member's own model for the minority report
    panel_member = config.panel[min_idx] if min_idx < len(config.panel) else config.chairman

    try:
        text, tokens = call_llm(
            panel_member, system, prompt,
            timeout=config.member_timeout_seconds, max_tokens=3000,
            active_models=active_models, fallback_pool=fallback_pool,
        )
        result = parse_json_response(text)
        print(f"  Dissent confidence: {result.get('confidence_in_dissent', '?')}")
        return result, tokens
    except Exception as e:
        print(f"  [WARN] Minority report failed: {e}")
        return {"error": str(e)}, 0


# ============================================================
# ADAPTIVE STOPPING (KS Statistic — optional)
# ============================================================

def ks_statistic(dist_a: list[float], dist_b: list[float]) -> float:
    """Kolmogorov-Smirnov statistic for two distributions. Simplified."""
    if not dist_a or not dist_b:
        return 1.0
    combined = sorted(set(dist_a + dist_b))
    cdf_a = [sum(1 for x in dist_a if x <= v) / len(dist_a) for v in combined]
    cdf_b = [sum(1 for x in dist_b if x <= v) / len(dist_b) for v in combined]
    return max(abs(a - b) for a, b in zip(cdf_a, cdf_b))


def should_stop_adaptive(prev_round: list[dict], curr_round: list[dict], epsilon: float = 0.1) -> bool:
    """Check if response distributions have converged (KS statistic < epsilon)."""
    prev_confs = [float(c.get("confidence", c.get("updated_confidence", 0.5))) for c in prev_round]
    curr_confs = [float(c.get("confidence", c.get("updated_confidence", 0.5))) for c in curr_round]
    ks = ks_statistic(prev_confs, curr_confs)
    return ks < epsilon


# ============================================================
# VERDICT FORMATTING
# ============================================================

def format_verdict_markdown(question: str, verdict: dict, critiques: list, cross_exam: dict,
                           rankings: dict, cascade_breaker: dict, minority: Optional[dict]) -> str:
    """Format the verdict as human-readable markdown."""
    lines = [
        "# LLM Judge Jury Executioner Verdict",
        "",
        f"**Question:** {question}",
        f"**Verdict:** {verdict.get('verdict', 'UNKNOWN')}",
        f"**Recommendation:** {verdict.get('recommendation', 'N/A')}",
        "",
        "## Where the Council Agrees",
        "",
    ]
    for point in verdict.get("where_they_agree", []):
        lines.append(f"- {point}")

    lines += ["", "## Where the Council Clashes", ""]
    for point in verdict.get("where_they_clash", []):
        lines.append(f"- {point}")

    lines += ["", "## Blind Spots Identified", ""]
    for spot in verdict.get("blind_spots", []):
        lines.append(f"- {spot}")

    lines += [f"", "## Concrete Next Step", "", verdict.get("concrete_next_step", "N/A"), ""]

    if cascade_breaker and "error" not in cascade_breaker:
        lines += [
            "## Cascade-Breaker Assessment",
            "",
            f"**Independent verdict:** {cascade_breaker.get('independent_verdict', 'N/A')}",
            f"**Cascade risk:** {cascade_breaker.get('shortcut_cascade_risk', 'N/A')}",
            f"**Confidence:** {cascade_breaker.get('confidence', 'N/A')}",
            "",
        ]
        for d in cascade_breaker.get("disagreements_with_panel", []):
            lines.append(f"- {d}")

    if minority and "error" not in minority:
        lines += [
            "## Minority Report",
            "",
            f"**Position:** {minority.get('minority_position', 'N/A')}",
            f"**Reasoning:** {minority.get('dissent_reasoning', 'N/A')}",
            f"**Risk if ignored:** {minority.get('risk_if_ignored', 'N/A')}",
            f"**Confidence in dissent:** {minority.get('confidence_in_dissent', 'N/A')}",
            "",
        ]

    if verdict.get("issues"):
        lines += ["## Issues (REVISE)", ""]
        for issue in verdict["issues"]:
            lines.append(f"- {issue}")
        lines.append("")

    lines += [
        "## Evidence Quality",
        "",
        verdict.get("evidence_quality", "N/A"),
        "",
    ]

    return "\n".join(lines)


def format_html_report(question: str, verdict: dict, critiques: list, cross_exam: dict,
                       rankings: dict, cascade_breaker: dict, minority: Optional[dict]) -> str:
    """Format the verdict as a standalone HTML report."""
    # Load template and inject data
    template_path = Path(__file__).parent.parent / "templates" / "html-report-template.html"
    if template_path.exists():
        template = template_path.read_text()
    else:
        template = "<html><body><pre>{content}</pre></body></html>"

    # Build report data as JSON for the template
    report_data = {
        "question": question,
        "verdict": verdict.get("verdict", "UNKNOWN"),
        "recommendation": verdict.get("recommendation", ""),
        "agreements": verdict.get("where_they_agree", []),
        "clashes": verdict.get("where_they_clash", []),
        "blind_spots": verdict.get("blind_spots", []),
        "next_step": verdict.get("concrete_next_step", ""),
        "advisors": [
            {
                "label": chr(65 + i),
                "position": c.get("position", c.get("revised_position", "N/A")),
                "confidence": c.get("confidence", c.get("updated_confidence", 0.5)),
                "model": c.get("member_model", ""),
            }
            for i, c in enumerate(critiques)
        ],
        "cascade_breaker": cascade_breaker if cascade_breaker and "error" not in cascade_breaker else None,
        "minority_report": minority if minority and "error" not in minority else None,
    }

    # Simple template injection
    html = template.replace("__QUESTION__", question)
    html = html.replace("__VERDICT__", verdict.get("verdict", "UNKNOWN"))
    html = html.replace("__RECOMMENDATION__", verdict.get("recommendation", ""))
    html = html.replace("__NEXT_STEP__", verdict.get("concrete_next_step", ""))

    # Build advisor cards
    advisor_cards = ""
    for a in report_data["advisors"]:
        advisor_cards += f"""
        <div class="advisor-card">
            <div class="advisor-label">Advisor {a['label']}</div>
            <div class="advisor-position">{a['position'][:200]}...</div>
            <div class="advisor-confidence">Confidence: {a['confidence']}</div>
        </div>"""

    html = html.replace("__ADVISOR_CARDS__", advisor_cards)

    # Agreement/clash lists
    agree_list = "".join(f"<li>{p}</li>" for p in report_data["agreements"])
    clash_list = "".join(f"<li>{p}</li>" for p in report_data["clashes"])
    blind_list = "".join(f"<li>{p}</li>" for p in report_data["blind_spots"])

    html = html.replace("__AGREE_LIST__", agree_list or "<li>None</li>")
    html = html.replace("__CLASH_LIST__", clash_list or "<li>None</li>")
    html = html.replace("__BLIND_LIST__", blind_list or "<li>None</li>")

    # Cascade breaker
    cb_html = ""
    if report_data["cascade_breaker"]:
        cb = report_data["cascade_breaker"]
        cb_html = f"""
        <div class="cascade-section">
            <h3>Cascade-Breaker Assessment</h3>
            <p><strong>Independent verdict:</strong> {cb.get('independent_verdict', 'N/A')}</p>
            <p><strong>Cascade risk:</strong> {cb.get('shortcut_cascade_risk', 'N/A')}</p>
            <p><strong>Confidence:</strong> {cb.get('confidence', 'N/A')}</p>
        </div>"""
    html = html.replace("__CASCADE_BREAKER__", cb_html)

    # Minority report
    mr_html = ""
    if report_data["minority_report"]:
        mr = report_data["minority_report"]
        mr_html = f"""
        <div class="minority-section">
            <h3>Minority Report</h3>
            <p><strong>Position:</strong> {mr.get('minority_position', 'N/A')}</p>
            <p><strong>Reasoning:</strong> {mr.get('dissent_reasoning', 'N/A')}</p>
            <p><strong>Risk if ignored:</strong> {mr.get('risk_if_ignored', 'N/A')}</p>
        </div>"""
    html = html.replace("__MINORITY_REPORT__", mr_html)

    return html


# ============================================================
# MAIN COUNCIL DELIBERATION
# ============================================================

def run_council(question: str, config: CouncilConfig, output_dir: str = ".") -> dict:
    """
    Run the full council deliberation.
    Returns the full result dict and writes output files.
    """
    start_time = time.time()
    active_models: set = set()
    fallback_pool = config.fallback_pool

    print(f"\n{'='*60}")
    print(f"  LLM COUNCIL — Protocol: {config.protocol}")
    print(f"  Question: {question[:100]}{'...' if len(question) > 100 else ''}")
    print(f"  Panel size: {config.panel_size} | Quorum: {config.quorum_min}")
    print(f"{'='*60}\n")

    # Validate config
    warnings = config.validate_diversity()
    for w in warnings:
        print(f"[CONFIG WARNING] {w}")

    if not config.panel:
        print("[ERROR] No panel members configured. See examples/example-config.yaml.")
        return {"error": "No panel configured"}

    # Ensure panel matches panel_size
    panel = config.panel[: config.panel_size]
    while len(panel) < config.panel_size and len(config.panel) > 0:
        panel.append(config.panel[len(panel) % len(config.panel)])

    chairman = config.chairman or panel[0]

    result = {
        "question": question,
        "protocol": config.protocol,
        "config": {
            "panel_size": config.panel_size,
            "compose": config.compose,
            "cross_examination": config.cross_examination,
            "cascade_breaker": config.cascade_breaker,
            "minority_report": config.minority_report,
            "evidence_labels": config.evidence_labels,
        },
        "phases": {},
    }

    total_tokens = 0
    cascade_breaker_result = None
    cross_exam = {}
    rankings = {}

    # --- Phase 0: Compose ---
    advisors = None
    if config.compose:
        try:
            advisors = phase_compose(question, config.panel_size, chairman, fallback_pool, active_models)
            result["phases"]["compose"] = advisors
        except Exception as e:
            print(f"  [WARN] Compose failed: {e} — proceeding with generic personas")
            advisors = None

    # --- Phase 1: Independent Review ---
    critiques, tokens = phase_independent_review(question, panel, config, active_models, fallback_pool, advisors)
    total_tokens += tokens
    result["phases"]["independent_review"] = critiques

    # Check token cap
    if config.token_cap and total_tokens > config.token_cap:
        raise RuntimeError(f"Token cap exceeded: {total_tokens} > {config.token_cap}")

    # Check quorum
    if len(critiques) < config.quorum_min:
        print(f"\n[QUORUM FAILURE] Only {len(critiques)} of {config.panel_size} members responded.")
        print("Returning auto-REVISE with quorum failure note.")
        verdict = {
            "verdict": "REVISE",
            "recommendation": "Quorum failure — insufficient panel members responded.",
            "issues": [f"Only {len(critiques)} members responded, quorum_min={config.quorum_min}"],
        }
        result["phases"]["quorum_failure"] = True
        result["phases"]["verdict"] = verdict
    else:
        # --- Phase 2: Cross-Examination + Ranking ---
        cross_exam, rankings, tokens2 = phase_cross_examination_and_ranking(
            question, critiques, panel, config, active_models, fallback_pool, advisors
        )
        total_tokens += tokens2
        result["phases"]["cross_examination"] = cross_exam
        result["phases"]["rankings"] = rankings

        # --- Phase 2b: Cascade-Breaker ---
        cascade_breaker_result = None
        if config.cascade_breaker:
            cascade_breaker_result, tokens3 = phase_cascade_breaker(
                question, critiques, chairman, config, active_models, fallback_pool
            )
            total_tokens += tokens3
            result["phases"]["cascade_breaker"] = cascade_breaker_result

        # --- Phase 3: Chairman ---
        verdict, tokens4 = phase_chairman(
            question, critiques, cross_exam, rankings,
            cascade_breaker_result or {}, chairman, config, active_models, fallback_pool
        )
        total_tokens += tokens4
        result["phases"]["verdict"] = verdict

        # --- Phase 3b: Minority Report ---
        if config.minority_report:
            minority, tokens5 = phase_minority_report(
                question, critiques, chairman, config, active_models, fallback_pool
            )
            total_tokens += tokens5
            result["phases"]["minority_report"] = minority

    # Token tracking
    result["total_tokens"] = total_tokens
    result["elapsed_seconds"] = round(time.time() - start_time, 1)

    # --- Write outputs ---
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # council-verdict.md
    verdict_md = format_verdict_markdown(
        question, verdict, critiques, cross_exam, rankings,
        cascade_breaker_result or {},
        result["phases"].get("minority_report"),
    )
    (out / "council-verdict.md").write_text(verdict_md)

    # council-verdict.json
    (out / "council-verdict.json").write_text(json.dumps(result, indent=2, default=str))

    # council-transcript.json
    (out / "council-transcript.json").write_text(json.dumps(result["phases"], indent=2, default=str))

    # minority-report.md
    if result["phases"].get("minority_report") and "error" not in result["phases"]["minority_report"]:
        mr = result["phases"]["minority_report"]
        mr_md = f"""# Minority Report

**Position:** {mr.get('minority_position', 'N/A')}
**Reasoning:** {mr.get('dissent_reasoning', 'N/A')}
**Risk if ignored:** {mr.get('risk_if_ignored', 'N/A')}
**Confidence in dissent:** {mr.get('confidence_in_dissent', 'N/A')}
"""
        (out / "minority-report.md").write_text(mr_md)

    # council-report.html
    if config.html_report:
        html = format_html_report(
            question, verdict, critiques, cross_exam, rankings,
            cascade_breaker_result or {},
            result["phases"].get("minority_report"),
        )
        (out / "council-report.html").write_text(html)

    print(f"\n{'='*60}")
    print(f"  COUNCIL COMPLETE — {result['elapsed_seconds']}s | {total_tokens} tokens")
    print(f"  Verdict: {verdict.get('verdict', '?')}")
    print(f"  Outputs in: {out.absolute()}")
    print(f"{'='*60}\n")

    return result


# ============================================================
# CLI ENTRY POINT
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="LLM Judge Jury Executioner — Multi-Model Deliberation Engine")
    parser.add_argument("--question", "-q", help="The question to deliberate")
    parser.add_argument("--config", "-c", required=True, help="Path to config file (YAML or JSON)")
    parser.add_argument("--output-dir", "-o", default="./council-output", help="Output directory")
    parser.add_argument("--json", action="store_true", help="Output JSON verdict to stdout")
    parser.add_argument("--protocol", "-p", help="Override protocol (deliberate|vote|synthesize|critique|redteam|mav)")

    args = parser.parse_args()

    # Get question
    question = args.question
    if not question and not sys.stdin.isatty():
        question = sys.stdin.read().strip()
    if not question:
        print("ERROR: Provide a question via --question or stdin", file=sys.stderr)
        sys.exit(1)

    # Load config
    config = load_config(args.config)
    if args.protocol:
        config.protocol = args.protocol

    # Run council
    result = run_council(question, config, args.output_dir)

    if args.json:
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()