#!/usr/bin/env python3
"""Synthetic trace generator for the decision layer demo.

EVERY NUMBER THIS SCRIPT PRODUCES IS SYNTHETIC. Nothing here is measured, and
nothing here is copied from a measurement. The shape of the distributions is
authored on purpose to show a decision problem clearly; it is not evidence
about any model, vendor, or workload.

What it emits
-------------
``data/traffic.json``
    The call site definitions, the delegation edges with co-occurrence counts,
    and thirty days of per call site daily aggregates broken out by environment
    and by team. Aggregates are computed from distributions rather than by
    materialising two million spans.

``data/sample_trajectories.json``
    Two hundred complete trajectories, call by call, with parent links. These
    drive the beat one animation. One of them is the featured trajectory and
    has exactly forty seven calls.

``data/traces_sample.jsonl``
    Canonical trace records for the first twenty trajectories. Every line
    validates against ``schema/trace.schema.json``.

``data/langfuse_export_sample.jsonl``
    The same calls in the shape a Langfuse observation export has. This file
    and the canonical file above are a matched pair, which makes this generator
    a converter fixture: ``langfuse_record_to_trace`` turns one into the other
    and the tests assert the round trip.

The world
---------
A generic enterprise customer support agent. Nineteen call sites across the
four behaviour classes that decide which instrument can measure them:

    transform            one call in, one structured object out
    tool decider         which tool to call, and with what arguments
    retrieval            what to fetch, and whether the answer is supported
    orchestration        when to loop, when to delegate, when to stop

Usage:

    python3 scripts/gen_demo_traces.py
    python3 scripts/gen_demo_traces.py --seed 20260818 --trajectories 50000
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"

# --------------------------------------------------------------------------
# Fixture constants. All synthetic.
# --------------------------------------------------------------------------

DEFAULT_SEED = 20260818
DEFAULT_TRAJECTORIES = 50_000
WINDOW_DAYS = 30
WINDOW_END = date(2026, 8, 17)  # last full day in the synthetic window
SAMPLE_TRAJECTORY_COUNT = 200
FEATURED_CALL_COUNT = 47  # the beat one counter ticks to this

# A synthetic price book. These are not any vendor's prices; they exist so the
# fixture's dollar figures are internally consistent with its token figures.
PRICE_INPUT_PER_MILLION = 0.30
PRICE_OUTPUT_PER_MILLION = 2.50

# Placeholder model identifiers. Deliberately vendor neutral: this demo makes
# no claim about any real model, so it names none.
MODEL_INCUMBENT = "incumbent-general-v1"

ENVIRONMENTS = [("production", 0.82), ("staging", 0.18)]
TEAMS = [
    ("Billing Support", 0.44),
    ("Technical Support", 0.36),
    ("Account Management", 0.20),
]

BEHAVIOR_TRANSFORM = "transform"
BEHAVIOR_TOOL_DECIDER = "tool decider"
BEHAVIOR_RETRIEVAL = "retrieval"
BEHAVIOR_ORCHESTRATION = "orchestration"

# Which behaviour classes have an instrument that can return a verdict today.
# This drives the beat five badges. It is a statement about method, not a
# measurement of anything.
INSTRUMENT_READINESS = {
    BEHAVIOR_TRANSFORM: "measurable now",
    BEHAVIOR_TOOL_DECIDER: "measurable now",
    BEHAVIOR_RETRIEVAL: "needs trajectory instrument",
    BEHAVIOR_ORCHESTRATION: "measure last",
}


# --------------------------------------------------------------------------
# Call sites
# --------------------------------------------------------------------------
# calls  : mean calls per trajectory. These sum to FEATURED_CALL_COUNT.
# layer  : vertical band for the layout. Zero is the orchestrator, at the top.
# in_tok : mean input tokens per call.
# out_tok: mean BILLED output tokens per call — the visible answer plus any
#          reasoning tokens the caller never receives. A bill counts both.
# reason : share of those billed output tokens that is reasoning. The hottest
#          call site carries the largest share on purpose; that is beat four.
#
# Spend share is NOT authored here. It emerges from volume times tokens times
# the price book, and the aggregator computes it from the generated data. The
# token counts above were chosen so the emergent shape is the one the story
# needs — four call sites carrying roughly seventy percent — and the tests
# assert that shape rather than trusting it.

CALL_SITES = [
    # id, label, behaviour class, calls, layer, input tokens, billed output tokens, reasoning share
    ("conversation_orchestrator", "Conversation Orchestrator", BEHAVIOR_ORCHESTRATION, 5, 0, 3_000, 500, 0.22),
    ("intent_classifier", "Intent Classifier", BEHAVIOR_TRANSFORM, 2, 1, 1_400, 300, 0.10),
    ("language_detector", "Language Detector", BEHAVIOR_TRANSFORM, 1, 1, 700, 60, 0.05),
    ("skills_loader", "Skills Loader", BEHAVIOR_TRANSFORM, 1, 1, 2_600, 500, 0.12),
    ("sentiment_reader", "Sentiment Reader", BEHAVIOR_TRANSFORM, 1, 1, 1_500, 150, 0.08),
    ("question_rewriter", "Question Rewriter", BEHAVIOR_TRANSFORM, 2, 2, 1_900, 500, 0.18),
    ("account_database_lookup", "Account Database Lookup", BEHAVIOR_TOOL_DECIDER, 3, 2, 2_200, 650, 0.14),
    ("knowledge_base_retrieval", "Knowledge Base Retrieval", BEHAVIOR_RETRIEVAL, 3, 2, 2_900, 950, 0.16),
    ("refund_calculator_decider", "Refund Calculator Decider", BEHAVIOR_TOOL_DECIDER, 1, 2, 2_400, 700, 0.20),
    ("chunk_summarizer", "Chunk Summarizer", BEHAVIOR_TRANSFORM, 8, 3, 12_000, 2_200, 0.58),
    ("field_extractor", "Field Extractor", BEHAVIOR_TRANSFORM, 7, 3, 6_000, 2_300, 0.41),
    ("policy_engine_check", "Policy Engine Check", BEHAVIOR_TRANSFORM, 2, 4, 3_100, 800, 0.24),
    ("response_drafter", "Response Drafter", BEHAVIOR_TRANSFORM, 3, 4, 9_400, 2_250, 0.33),
    ("customer_record_action", "Customer Record Action Decider", BEHAVIOR_TOOL_DECIDER, 2, 4, 3_300, 700, 0.19),
    ("compliance_checker", "Compliance Checker", BEHAVIOR_TRANSFORM, 2, 5, 5_200, 2_350, 0.29),
    ("redaction_filter", "Personal Data Redaction Filter", BEHAVIOR_TRANSFORM, 1, 5, 7_200, 3_200, 0.15),
    ("ticketing_action", "Ticketing Action Decider", BEHAVIOR_TOOL_DECIDER, 1, 5, 4_100, 800, 0.17),
    ("escalation_note_writer", "Escalation Note Writer", BEHAVIOR_TRANSFORM, 1, 6, 3_600, 1_400, 0.21),
    ("summary_title_writer", "Summary Title Writer", BEHAVIOR_TRANSFORM, 1, 6, 2_800, 90, 0.09),
]

# Delegation and data flow. Direction is producer to consumer: the source's
# output is what the target consumes.
EDGES = [
    ("conversation_orchestrator", "intent_classifier"),
    ("conversation_orchestrator", "language_detector"),
    ("conversation_orchestrator", "skills_loader"),
    ("conversation_orchestrator", "sentiment_reader"),
    ("conversation_orchestrator", "account_database_lookup"),
    ("conversation_orchestrator", "knowledge_base_retrieval"),
    ("conversation_orchestrator", "refund_calculator_decider"),
    ("conversation_orchestrator", "response_drafter"),
    ("conversation_orchestrator", "policy_engine_check"),
    ("language_detector", "intent_classifier"),
    ("intent_classifier", "question_rewriter"),
    ("skills_loader", "conversation_orchestrator"),
    ("question_rewriter", "knowledge_base_retrieval"),
    ("knowledge_base_retrieval", "chunk_summarizer"),
    ("account_database_lookup", "field_extractor"),
    ("chunk_summarizer", "field_extractor"),
    ("chunk_summarizer", "response_drafter"),
    ("field_extractor", "policy_engine_check"),
    ("field_extractor", "response_drafter"),
    ("field_extractor", "customer_record_action"),
    ("refund_calculator_decider", "customer_record_action"),
    ("refund_calculator_decider", "compliance_checker"),
    ("policy_engine_check", "compliance_checker"),
    ("sentiment_reader", "response_drafter"),
    ("response_drafter", "compliance_checker"),
    ("response_drafter", "redaction_filter"),
    ("compliance_checker", "escalation_note_writer"),
    ("compliance_checker", "conversation_orchestrator"),
    ("customer_record_action", "ticketing_action"),
    ("escalation_note_writer", "ticketing_action"),
    ("redaction_filter", "summary_title_writer"),
    ("ticketing_action", "summary_title_writer"),
]

# The opening question, used by beat zero and by the featured trajectory.
OPENING_QUESTION = "Why was my premium charged twice?"

# Short synthetic prompts, one per call site, so system_prompt_sha differs.
SYSTEM_PROMPT_TEMPLATE = (
    "You are the {label} in an enterprise customer support agent. "
    "Behaviour class: {behavior_class}. Respond with the structured object "
    "your caller expects and nothing else."
)

TOOLS_BY_CALL_SITE = {
    "account_database_lookup": ["query_account_records"],
    "customer_record_action": ["update_customer_record", "add_account_note"],
    "ticketing_action": ["create_ticket", "update_ticket", "close_ticket"],
    "refund_calculator_decider": ["compute_refund", "quote_proration"],
    "knowledge_base_retrieval": ["search_knowledge_base"],
}


# --------------------------------------------------------------------------
# Derived world
# --------------------------------------------------------------------------


def build_call_site_table() -> list[dict]:
    """Turn the authored tuples into records."""
    total_calls_per_trajectory = sum(row[3] for row in CALL_SITES)
    if total_calls_per_trajectory != FEATURED_CALL_COUNT:
        raise SystemExit(
            f"call counts sum to {total_calls_per_trajectory}, expected {FEATURED_CALL_COUNT}"
        )

    sites = []
    for site_id, label, behavior, calls, layer, input_tokens, output_tokens, reasoning in CALL_SITES:
        sites.append(
            {
                "id": site_id,
                "label": label,
                "behavior_class": behavior,
                "instrument_readiness": INSTRUMENT_READINESS[behavior],
                "layer": layer,
                "calls_per_trajectory": calls,
                "billed_reasoning_share": reasoning,
                "mean_input_tokens": input_tokens,
                "mean_billed_output_tokens": output_tokens,
                "mean_visible_output_tokens": round(output_tokens * (1 - reasoning), 1),
                "model": MODEL_INCUMBENT,
                "system_prompt_sha": sha256_short(
                    SYSTEM_PROMPT_TEMPLATE.format(label=label, behavior_class=behavior)
                ),
                "tools_offered": TOOLS_BY_CALL_SITE.get(site_id, []),
            }
        )
    return sites


def sha256_short(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------
# Daily aggregates
# --------------------------------------------------------------------------


def day_seasonality(day: date) -> float:
    """Support traffic sags at the weekend and peaks on Monday."""
    weekday = day.weekday()
    return {0: 1.18, 1: 1.10, 2: 1.06, 3: 1.04, 4: 0.98, 5: 0.66, 6: 0.58}[weekday]


TEAM_SKEW = {
    ("refund_calculator_decider", "Billing Support"): 2.1,
    ("refund_calculator_decider", "Technical Support"): 0.2,
    ("account_database_lookup", "Account Management"): 1.7,
    ("knowledge_base_retrieval", "Technical Support"): 1.6,
    ("chunk_summarizer", "Technical Support"): 1.35,
    ("escalation_note_writer", "Account Management"): 1.8,
    ("compliance_checker", "Billing Support"): 1.4,
}


def team_mix(site_id: str) -> dict[str, float]:
    """How one call site's volume splits across teams. Sums to one.

    Teams do not use every call site equally, which is what gives the team
    filter something to bite on. The mix is normalised so a skew changes the
    split without changing the call site's total volume — that keeps the
    aggregator's arithmetic checkable.
    """
    raw = {name: base * TEAM_SKEW.get((site_id, name), 1.0) for name, base in TEAMS}
    total = sum(raw.values())
    return {name: value / total for name, value in raw.items()}


def environment_mix(layer: int) -> dict[str, float]:
    """How volume splits across environments. Sums to one.

    Staging exercises the deep call sites less than production does, because a
    staging run is usually cut short before it reaches them.
    """
    depth = 0.55 if layer >= 4 else 1.0
    raw = {
        name: share * (depth if name == "staging" else 1.0) for name, share in ENVIRONMENTS
    }
    total = sum(raw.values())
    return {name: value / total for name, value in raw.items()}


def generate_daily_aggregates(rng: random.Random, sites: list[dict], trajectories: int) -> list[dict]:
    """Per day, per call site, per environment, per team.

    Computed from distributions. Two million spans are never materialised.
    """
    days = [WINDOW_END - timedelta(days=offset) for offset in range(WINDOW_DAYS - 1, -1, -1)]
    seasonality_total = sum(day_seasonality(day) for day in days)

    rows: list[dict] = []
    for day in days:
        day_trajectories = trajectories * day_seasonality(day) / seasonality_total
        for site in sites:
            environments = environment_mix(site["layer"])
            teams = team_mix(site["id"])
            for env_name, env_share in environments.items():
                for team_name, team_share in teams.items():
                    expected = (
                        day_trajectories
                        * site["calls_per_trajectory"]
                        * env_share
                        * team_share
                    )
                    calls = max(0, int(round(expected * rng.lognormvariate(0.0, 0.06))))
                    if calls == 0:
                        continue
                    input_tokens = int(
                        calls * site["mean_input_tokens"] * rng.lognormvariate(0.0, 0.04)
                    )
                    billed_output_tokens = int(
                        calls * site["mean_billed_output_tokens"] * rng.lognormvariate(0.0, 0.05)
                    )
                    reasoning_tokens = int(billed_output_tokens * site["billed_reasoning_share"])
                    cost = (
                        input_tokens * PRICE_INPUT_PER_MILLION
                        + billed_output_tokens * PRICE_OUTPUT_PER_MILLION
                    ) / 1e6
                    rows.append(
                        {
                            "date": day.isoformat(),
                            "call_site": site["id"],
                            "environment": env_name,
                            "team": team_name,
                            "calls": calls,
                            "input_tokens": input_tokens,
                            "billed_output_tokens": billed_output_tokens,
                            "billed_reasoning_tokens": reasoning_tokens,
                            "cost_usd": round(cost, 6),
                        }
                    )
    return rows


# --------------------------------------------------------------------------
# Trajectories
# --------------------------------------------------------------------------


def incoming_edges() -> dict[str, list[str]]:
    incoming: dict[str, list[str]] = {row[0]: [] for row in CALL_SITES}
    for source, target in EDGES:
        incoming[target].append(source)
    return incoming


def generate_trajectory(
    rng: random.Random,
    sites: list[dict],
    trajectory_index: int,
    featured: bool,
) -> dict:
    """One customer question, expanded into the calls it actually costs.

    Loops and retries are what make a trajectory thirty to fifty calls long:
    the summariser fires once per retrieved chunk, the extractor once per
    field, and a failed structured emission is retried.
    """
    incoming = incoming_edges()
    scale = 1.0 if featured else rng.uniform(0.62, 1.06)

    counts: dict[str, int] = {}
    for site in sites:
        base = site["calls_per_trajectory"]
        if featured:
            counts[site["id"]] = base
            continue
        expected = base * scale
        count = int(math.floor(expected))
        if rng.random() < (expected - count):
            count += 1
        counts[site["id"]] = max(0 if base <= 1 else 1, count)

    if not featured:
        # Keep every trajectory inside the thirty to fifty call band.
        total = sum(counts.values())
        order = [site["id"] for site in sorted(sites, key=lambda s: -s["calls_per_trajectory"])]
        while total > 50:
            for site_id in order:
                if counts[site_id] > 1:
                    counts[site_id] -= 1
                    total -= 1
                    if total <= 50:
                        break
        while total < 30:
            for site_id in order:
                counts[site_id] += 1
                total += 1
                if total >= 30:
                    break

    by_layer: dict[int, list[str]] = {}
    for site in sites:
        by_layer.setdefault(site["layer"], []).append(site["id"])

    calls: list[dict] = []
    emitted: dict[str, list[int]] = {}
    sequence = 0
    for layer in sorted(by_layer):
        layer_calls: list[str] = []
        for site_id in by_layer[layer]:
            layer_calls.extend([site_id] * counts[site_id])
        rng.shuffle(layer_calls)
        for site_id in layer_calls:
            parents = [p for p in incoming[site_id] if emitted.get(p)]
            parent_sequence = rng.choice(emitted[rng.choice(parents)]) if parents else None
            calls.append(
                {
                    "seq": sequence,
                    "call_site": site_id,
                    "parent_seq": parent_sequence,
                    "retry": False,
                }
            )
            emitted.setdefault(site_id, []).append(sequence)
            sequence += 1

    environment = "production" if rng.random() < 0.82 else "staging"
    team = rng.choices([name for name, _ in TEAMS], weights=[w for _, w in TEAMS])[0]

    return {
        "trajectory_id": f"traj-{trajectory_index:06d}",
        "question": OPENING_QUESTION if featured else None,
        "featured": featured,
        "environment": environment,
        "team": team,
        "call_count": len(calls),
        "calls": calls,
    }


def generate_sample_trajectories(rng: random.Random, sites: list[dict]) -> list[dict]:
    trajectories = [generate_trajectory(rng, sites, 0, featured=True)]
    for index in range(1, SAMPLE_TRAJECTORY_COUNT):
        trajectories.append(generate_trajectory(rng, sites, index, featured=False))

    featured = trajectories[0]
    if featured["call_count"] != FEATURED_CALL_COUNT:
        raise SystemExit(
            f"featured trajectory has {featured['call_count']} calls, expected {FEATURED_CALL_COUNT}"
        )
    return trajectories


def count_edges(trajectories: list[dict], trajectory_total: int) -> list[dict]:
    """Co-occurrence measured over the sample, scaled to the full window.

    'Measured over the sample' means counted in this generator's own synthetic
    sample. It is not a measurement of any real system.
    """
    seen: dict[tuple[str, str], int] = {}
    for trajectory in trajectories:
        by_seq = {call["seq"]: call for call in trajectory["calls"]}
        for call in trajectory["calls"]:
            if call["parent_seq"] is None:
                continue
            parent = by_seq[call["parent_seq"]]["call_site"]
            key = (parent, call["call_site"])
            seen[key] = seen.get(key, 0) + 1

    scale = trajectory_total / max(1, len(trajectories))
    edges = []
    for (source, target), count in sorted(seen.items()):
        edges.append(
            {
                "source": source,
                "target": target,
                "sample_count": count,
                "window_count": int(round(count * scale)),
                "per_trajectory": round(count / max(1, len(trajectories)), 3),
            }
        )
    return edges


# --------------------------------------------------------------------------
# Canonical traces and the Langfuse shaped export
# --------------------------------------------------------------------------


def synthetic_output(site: dict, rng: random.Random) -> tuple[str | None, dict | None]:
    if site["behavior_class"] == BEHAVIOR_TOOL_DECIDER:
        return None, {"decision": "call_tool", "confidence": round(rng.uniform(0.71, 0.98), 3)}
    if site["behavior_class"] == BEHAVIOR_ORCHESTRATION:
        return None, {"next_step": "delegate", "remaining_steps": rng.randint(1, 6)}
    if site["behavior_class"] == BEHAVIOR_RETRIEVAL:
        return None, {"chunk_ids": [f"chunk-{rng.randint(1000, 9999)}" for _ in range(rng.randint(2, 5))]}
    return "Synthetic placeholder output for an illustrative demo.", None


def build_call_records(
    rng: random.Random,
    sites: list[dict],
    trajectories: list[dict],
    trace_trajectory_count: int,
) -> list[dict]:
    """One neutral record per call, from which both output shapes are rendered."""
    by_id = {site["id"]: site for site in sites}
    base_time = datetime(2026, 8, 17, 9, 0, 0, tzinfo=timezone.utc)

    records: list[dict] = []
    for trajectory in trajectories[:trace_trajectory_count]:
        start = base_time + timedelta(minutes=7 * int(trajectory["trajectory_id"].split("-")[1]))
        offset_ms = 0
        for call in trajectory["calls"]:
            site = by_id[call["call_site"]]
            visible = max(1, int(rng.gauss(site["mean_visible_output_tokens"], site["mean_visible_output_tokens"] * 0.15)))
            reasoning = int(visible * site["billed_reasoning_share"] / max(1e-6, 1 - site["billed_reasoning_share"]))
            input_tokens = max(1, int(rng.gauss(site["mean_input_tokens"], site["mean_input_tokens"] * 0.12)))
            total_ms = max(120, int(rng.gauss(900 + visible * 1.4, 220)))
            ttft_ms = max(60, int(total_ms * rng.uniform(0.22, 0.45)))
            status = "error" if rng.random() < 0.012 else "ok"
            text, structured = synthetic_output(site, rng)

            records.append(
                {
                    "trajectory_id": trajectory["trajectory_id"],
                    "seq": call["seq"],
                    "parent_seq": call["parent_seq"],
                    "call_site": site["id"],
                    "label": site["label"],
                    "behavior_class": site["behavior_class"],
                    "model": site["model"],
                    "system_prompt_sha": site["system_prompt_sha"],
                    "environment": trajectory["environment"],
                    "team": trajectory["team"],
                    "start": start + timedelta(milliseconds=offset_ms),
                    "input_tokens": input_tokens,
                    "visible_output_tokens": visible,
                    "reasoning_tokens": reasoning,
                    "ttft_ms": ttft_ms,
                    "total_ms": total_ms,
                    "status": status,
                    "text": text,
                    "structured": structured,
                    "tools_offered": site["tools_offered"],
                }
            )
            offset_ms += total_ms + rng.randint(20, 180)
    return records


def record_to_trace(record: dict) -> dict:
    """The canonical trace shape, as exported in schema/trace.schema.json."""
    tool_calls = []
    if record["tools_offered"] and record["behavior_class"] == BEHAVIOR_TOOL_DECIDER:
        tool_calls = [{"name": record["tools_offered"][0], "args": {"account_id": "acct-synthetic-0001"}}]

    return {
        "trace_id": f"{record['trajectory_id']}-{record['seq']:03d}",
        "subagent": record["call_site"],
        "provenance": "synthetic",
        "ts": record["start"].isoformat().replace("+00:00", "Z"),
        "model": record["model"],
        "system_prompt_sha": record["system_prompt_sha"],
        "input": {
            "messages": [OPENING_QUESTION],
            "context_chunks": [],
        },
        "tools_offered": record["tools_offered"],
        "tool_calls": tool_calls,
        "output": {"text": record["text"], "json": record["structured"]},
        "usage": {
            "input_tokens": record["input_tokens"],
            # Billed output is what a bill counts: visible answer plus reasoning.
            "output_tokens": record["visible_output_tokens"] + record["reasoning_tokens"],
            "cached_tokens": 0,
        },
        "latency_ms": {"ttft": record["ttft_ms"], "total": record["total_ms"]},
        "status": record["status"],
        "error": "synthetic transient failure" if record["status"] == "error" else None,
    }


def record_to_langfuse(record: dict) -> dict:
    """The shape a Langfuse observation export has.

    Deliberately not the canonical shape: extra keys, different names, nested
    usage details, metadata carrying what the canonical record puts at the top
    level. This is the converter's input side.
    """
    end = record["start"] + timedelta(milliseconds=record["total_ms"])
    parent = (
        f"{record['trajectory_id']}-{record['parent_seq']:03d}"
        if record["parent_seq"] is not None
        else None
    )
    return {
        "id": f"{record['trajectory_id']}-{record['seq']:03d}",
        "traceId": record["trajectory_id"],
        "parentObservationId": parent,
        "type": "GENERATION",
        "name": record["label"],
        "startTime": record["start"].isoformat().replace("+00:00", "Z"),
        "endTime": end.isoformat().replace("+00:00", "Z"),
        "completionStartTime": (
            record["start"] + timedelta(milliseconds=record["ttft_ms"])
        ).isoformat().replace("+00:00", "Z"),
        "model": record["model"],
        "modelParameters": {"temperature": 0.2, "max_output_tokens": 4096},
        "input": {"messages": [{"role": "user", "content": OPENING_QUESTION}]},
        "output": (
            {"text": record["text"]} if record["text"] is not None else {"json": record["structured"]}
        ),
        "usage": {
            "input": record["input_tokens"],
            "output": record["visible_output_tokens"] + record["reasoning_tokens"],
            "total": record["input_tokens"] + record["visible_output_tokens"] + record["reasoning_tokens"],
            "unit": "TOKENS",
        },
        "usageDetails": {
            "input": record["input_tokens"],
            "output_visible": record["visible_output_tokens"],
            "output_reasoning": record["reasoning_tokens"],
            "cache_read": 0,
        },
        "level": "ERROR" if record["status"] == "error" else "DEFAULT",
        "statusMessage": "synthetic transient failure" if record["status"] == "error" else None,
        "metadata": {
            "call_site": record["call_site"],
            "behavior_class": record["behavior_class"],
            "environment": record["environment"],
            "team": record["team"],
            "system_prompt_sha": record["system_prompt_sha"],
            "tools_offered": record["tools_offered"],
            "provenance": "synthetic",
        },
    }


def langfuse_record_to_trace(observation: dict) -> dict:
    """Convert a Langfuse observation into a canonical trace.

    This is the converter the workbench will need for bring your own traces.
    It lives here because this generator emits a matched pair of files, which
    makes it the fixture that pins the converter's behaviour.
    """
    metadata = observation.get("metadata", {})
    usage = observation.get("usage", {})
    details = observation.get("usageDetails", {})
    output = observation.get("output", {}) or {}

    start = datetime.fromisoformat(observation["startTime"].replace("Z", "+00:00"))
    ttft = None
    if observation.get("completionStartTime"):
        first = datetime.fromisoformat(observation["completionStartTime"].replace("Z", "+00:00"))
        ttft = int((first - start).total_seconds() * 1000)
    total = None
    if observation.get("endTime"):
        end = datetime.fromisoformat(observation["endTime"].replace("Z", "+00:00"))
        total = int((end - start).total_seconds() * 1000)

    is_error = observation.get("level") == "ERROR"
    messages = [
        message["content"] for message in observation.get("input", {}).get("messages", [])
    ]

    tool_calls = []
    tools_offered = metadata.get("tools_offered", [])
    if tools_offered and metadata.get("behavior_class") == BEHAVIOR_TOOL_DECIDER:
        tool_calls = [{"name": tools_offered[0], "args": {"account_id": "acct-synthetic-0001"}}]

    return {
        "trace_id": observation["id"],
        "subagent": metadata.get("call_site", observation.get("name", "unknown")),
        "provenance": metadata.get("provenance", "synthetic"),
        "ts": start.isoformat().replace("+00:00", "Z"),
        "model": observation.get("model", "unknown"),
        "system_prompt_sha": metadata.get("system_prompt_sha", ""),
        "input": {"messages": messages, "context_chunks": []},
        "tools_offered": tools_offered,
        "tool_calls": tool_calls,
        "output": {"text": output.get("text"), "json": output.get("json")},
        "usage": {
            "input_tokens": usage.get("input", details.get("input", 0)) or 0,
            "output_tokens": usage.get("output", 0) or 0,
            "cached_tokens": details.get("cache_read", 0) or 0,
        },
        "latency_ms": {"ttft": ttft, "total": total},
        "status": "error" if is_error else "ok",
        "error": observation.get("statusMessage") if is_error else None,
    }


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--trajectories", type=int, default=DEFAULT_TRAJECTORIES)
    parser.add_argument("--trace-trajectories", type=int, default=20)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    DATA.mkdir(parents=True, exist_ok=True)

    sites = build_call_site_table()
    daily = generate_daily_aggregates(rng, sites, args.trajectories)
    trajectories = generate_sample_trajectories(rng, sites)
    edges = count_edges(trajectories, args.trajectories)
    records = build_call_records(rng, sites, trajectories, args.trace_trajectories)

    window_start = (WINDOW_END - timedelta(days=WINDOW_DAYS - 1)).isoformat()
    meta = {
        "synthetic": True,
        "notice": (
            "ILLUSTRATIVE DEMO — synthetic traces. Every number in this file is "
            "generated, not measured. It describes no real system, model, or vendor."
        ),
        "generator": "scripts/gen_demo_traces.py",
        "seed": args.seed,
        "generated_on": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "window_start": window_start,
        "window_end": WINDOW_END.isoformat(),
        "window_days": WINDOW_DAYS,
        "trajectories_in_window": args.trajectories,
        "featured_call_count": FEATURED_CALL_COUNT,
        "opening_question": OPENING_QUESTION,
        "price_book": {
            "synthetic": True,
            "input_per_million_usd": PRICE_INPUT_PER_MILLION,
            "output_per_million_usd": PRICE_OUTPUT_PER_MILLION,
        },
        "environments": [name for name, _ in ENVIRONMENTS],
        "teams": [name for name, _ in TEAMS],
        "behavior_classes": list(INSTRUMENT_READINESS.keys()),
        "schema": "schema/trace.schema.json",
    }

    write_json(DATA / "traffic.json", {"meta": meta, "call_sites": sites, "edges": edges, "daily": daily})
    write_json(
        DATA / "sample_trajectories.json",
        {"meta": {k: meta[k] for k in ("synthetic", "notice", "seed", "opening_question", "featured_call_count")},
         "trajectories": trajectories},
    )

    write_jsonl(DATA / "traces_sample.jsonl", (record_to_trace(record) for record in records))
    write_jsonl(DATA / "langfuse_export_sample.jsonl", (record_to_langfuse(record) for record in records))

    total_calls = sum(row["calls"] for row in daily)
    total_cost = sum(row["cost_usd"] for row in daily)
    call_counts = [trajectory["call_count"] for trajectory in trajectories]
    print(f"seed {args.seed}")
    print(f"  daily aggregate rows      {len(daily):,}")
    print(f"  window calls              {total_calls:,}")
    print(f"  window spend              ${total_cost:,.2f}")
    print(f"  sample trajectories       {len(trajectories)} "
          f"(calls {min(call_counts)}–{max(call_counts)}, featured {trajectories[0]['call_count']})")
    print(f"  canonical trace records   {len(records):,}")

    by_site: dict[str, float] = {}
    for row in daily:
        by_site[row["call_site"]] = by_site.get(row["call_site"], 0.0) + row["cost_usd"]
    ranked = sorted(by_site.items(), key=lambda item: -item[1])
    top_four = sum(cost for _, cost in ranked[:4]) / total_cost
    print(f"  spend in the top four     {top_four:.1%}")
    for site_id, cost in ranked[:6]:
        print(f"    {site_id:<28} {cost / total_cost:6.1%}  ${cost:>9,.0f}")


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
