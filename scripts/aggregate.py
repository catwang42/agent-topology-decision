#!/usr/bin/env python3
"""Aggregate the synthetic traffic into the graph the page renders.

Reads
    data/traffic.json            call sites, edges, thirty days of aggregates
    data/status_timeline.json    the authored eight week rollout
    data/decision_cards.json     the authored decision cards
    data/sample_trajectories.json

Writes
    data/graph.json              nodes and edges, with everything derived
    data/demo_data.js            the same payloads as browser globals

Why two output files. The page has to open from a file path with no server and
no network. A browser will not let a page at a file path fetch a sibling file,
so the data is also written as a script that assigns globals. ``graph.json`` is
the artefact; ``demo_data.js`` is how it gets into the page.

EVERY NUMBER HERE IS SYNTHETIC. This script derives figures from a generated
fixture. It measures nothing.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"


def load(name: str) -> dict:
    path = DATA / name
    if not path.exists():
        raise SystemExit(f"missing {path}. Run scripts/gen_demo_traces.py first.")
    return json.loads(path.read_text(encoding="utf-8"))


def blast_radius(node_ids: list[str], edges: list[dict], volume: dict[str, int]) -> dict[str, float]:
    """Share of total call volume that sits downstream of each call site.

    Downstream means reachable by following the direction of data flow, so it
    is the volume that consumes this call site's output, directly or through
    other call sites. A call site is not counted in its own blast radius.

    The graph has cycles — the orchestrator is called back into — so this is a
    reachable set computed with a breadth first walk, not a depth sum.
    """
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        outgoing[edge["source"]].append(edge["target"])

    total_volume = sum(volume.values())
    radius: dict[str, float] = {}
    for start in node_ids:
        seen: set[str] = set()
        queue = deque(outgoing[start])
        while queue:
            current = queue.popleft()
            if current in seen or current == start:
                continue
            seen.add(current)
            queue.extend(outgoing[current])
        radius[start] = sum(volume[node] for node in seen) / total_volume if total_volume else 0.0
    return radius


def build_graph() -> dict:
    traffic = load("traffic.json")
    timeline = load("status_timeline.json")
    cards = load("decision_cards.json")

    sites = traffic["call_sites"]
    daily = traffic["daily"]
    edges = traffic["edges"]

    # Collapse the daily rows onto the environment and team grid. The date
    # dimension is dropped here on purpose: the page's scrubber moves through
    # rollout weeks, not through days, and the traffic profile it modulates is
    # the whole thirty day window. Keeping the grid is what lets the
    # environment and team filters recompute every share in the browser.
    cells: dict[str, dict[tuple[str, str], dict]] = defaultdict(
        lambda: defaultdict(lambda: {"calls": 0, "input_tokens": 0, "billed_output_tokens": 0,
                                     "billed_reasoning_tokens": 0, "cost_usd": 0.0})
    )
    series: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in daily:
        cell = cells[row["call_site"]][(row["environment"], row["team"])]
        cell["calls"] += row["calls"]
        cell["input_tokens"] += row["input_tokens"]
        cell["billed_output_tokens"] += row["billed_output_tokens"]
        cell["billed_reasoning_tokens"] += row["billed_reasoning_tokens"]
        cell["cost_usd"] += row["cost_usd"]
        series[row["call_site"]][row["date"]] += row["cost_usd"]

    volume = {site["id"]: sum(c["calls"] for c in cells[site["id"]].values()) for site in sites}
    spend = {site["id"]: sum(c["cost_usd"] for c in cells[site["id"]].values()) for site in sites}
    total_spend = sum(spend.values())
    total_volume = sum(volume.values())
    radius = blast_radius([site["id"] for site in sites], edges, volume)

    window_days = traffic["meta"]["window_days"]
    dates = sorted({row["date"] for row in daily})

    nodes = []
    for site in sites:
        site_id = site["id"]
        reasoning_tokens = sum(c["billed_reasoning_tokens"] for c in cells[site_id].values())
        billed_output = sum(c["billed_output_tokens"] for c in cells[site_id].values())
        nodes.append(
            {
                "id": site_id,
                "label": site["label"],
                "behavior_class": site["behavior_class"],
                "instrument_readiness": site["instrument_readiness"],
                "layer": site["layer"],
                "calls_per_trajectory": site["calls_per_trajectory"],
                "calls": volume[site_id],
                "call_share": volume[site_id] / total_volume if total_volume else 0.0,
                "spend_usd": round(spend[site_id], 2),
                "spend_share": spend[site_id] / total_spend if total_spend else 0.0,
                "spend_usd_per_day": round(spend[site_id] / window_days, 2),
                "billed_reasoning_share": (
                    reasoning_tokens / billed_output if billed_output else 0.0
                ),
                "billed_reasoning_tokens": reasoning_tokens,
                "billed_output_tokens": billed_output,
                "blast_radius": radius[site_id],
                "has_decision_card": site_id in cards["cards"],
                "cells": [
                    {
                        "environment": environment,
                        "team": team,
                        "calls": cell["calls"],
                        "cost_usd": round(cell["cost_usd"], 4),
                        "billed_output_tokens": cell["billed_output_tokens"],
                        "billed_reasoning_tokens": cell["billed_reasoning_tokens"],
                    }
                    for (environment, team), cell in sorted(cells[site_id].items())
                ],
                "daily_cost_usd": [round(series[site_id][day], 4) for day in dates],
            }
        )

    max_edge = max((edge["window_count"] for edge in edges), default=1)
    graph_edges = [
        {
            "source": edge["source"],
            "target": edge["target"],
            "window_count": edge["window_count"],
            "per_trajectory": edge["per_trajectory"],
            "frequency": edge["window_count"] / max_edge,
        }
        for edge in edges
    ]

    ranked = sorted(nodes, key=lambda node: -node["spend_share"])
    concentration = {
        "top_four_ids": [node["id"] for node in ranked[:4]],
        "top_four_spend_share": sum(node["spend_share"] for node in ranked[:4]),
        "hottest_id": ranked[0]["id"],
        "hottest_spend_share": ranked[0]["spend_share"],
        "hottest_reasoning_share": ranked[0]["billed_reasoning_share"],
        "call_site_count": len(nodes),
    }

    return {
        "meta": {
            **traffic["meta"],
            "aggregator": "scripts/aggregate.py",
            "window_dates": dates,
            "total_calls": total_volume,
            "total_spend_usd": round(total_spend, 2),
            "total_spend_usd_per_day": round(total_spend / window_days, 2),
        },
        "concentration": concentration,
        "nodes": nodes,
        "edges": graph_edges,
    }


def check(graph: dict, timeline: dict, cards: dict) -> None:
    """Fail loudly rather than render a graph that does not add up."""
    node_ids = {node["id"] for node in graph["nodes"]}

    share_sum = sum(node["spend_share"] for node in graph["nodes"])
    if abs(share_sum - 1.0) > 1e-9:
        raise SystemExit(f"spend shares sum to {share_sum}, expected 1.0")

    for edge in graph["edges"]:
        if edge["source"] not in node_ids or edge["target"] not in node_ids:
            raise SystemExit(f"edge {edge['source']} -> {edge['target']} names an unknown call site")

    missing = node_ids - set(timeline["timeline"])
    if missing:
        raise SystemExit(f"status timeline is missing call sites: {sorted(missing)}")
    extra = set(timeline["timeline"]) - node_ids
    if extra:
        raise SystemExit(f"status timeline names call sites that do not exist: {sorted(extra)}")

    week_count = len(timeline["weeks"])
    known = set(timeline["statuses"])
    for site_id, statuses in timeline["timeline"].items():
        if len(statuses) != week_count:
            raise SystemExit(f"{site_id} has {len(statuses)} weeks, expected {week_count}")
        unknown = set(statuses) - known
        if unknown:
            raise SystemExit(f"{site_id} uses unknown statuses {sorted(unknown)}")

    for site_id in cards["cards"]:
        if site_id not in node_ids:
            raise SystemExit(f"decision card names an unknown call site: {site_id}")


def main() -> None:
    graph = build_graph()
    timeline = load("status_timeline.json")
    cards = load("decision_cards.json")
    trajectories = load("sample_trajectories.json")
    check(graph, timeline, cards)

    (DATA / "graph.json").write_text(json.dumps(graph, indent=1) + "\n", encoding="utf-8")

    # The page animates one trajectory and offers a few alternates. Shipping
    # all two hundred would quadruple the bundle for no visible gain, so the
    # browser payload carries the featured one plus a sample. The full set
    # stays in data/sample_trajectories.json.
    featured = [t for t in trajectories["trajectories"] if t["featured"]]
    others = [t for t in trajectories["trajectories"] if not t["featured"]][:11]
    browser_trajectories = {**trajectories, "trajectories": featured + others}
    browser_trajectories["meta"] = {
        **trajectories["meta"],
        "in_bundle": len(featured + others),
        "in_full_file": len(trajectories["trajectories"]),
        "full_file": "data/sample_trajectories.json",
    }

    bundle = (
        "/* GENERATED by scripts/aggregate.py — do not edit.\n"
        "   ILLUSTRATIVE DEMO — synthetic traces. Every number below is generated,\n"
        "   not measured. Loaded as a script rather than fetched so the page opens\n"
        "   from a file path with no server and no network. */\n"
        f"window.DEMO_GRAPH = {json.dumps(graph, separators=(',', ':'))};\n"
        f"window.DEMO_TIMELINE = {json.dumps(timeline, separators=(',', ':'))};\n"
        f"window.DEMO_CARDS = {json.dumps(cards, separators=(',', ':'))};\n"
        f"window.DEMO_TRAJECTORIES = {json.dumps(browser_trajectories, separators=(',', ':'))};\n"
    )
    (DATA / "demo_data.js").write_text(bundle, encoding="utf-8")

    concentration = graph["concentration"]
    print("wrote data/graph.json and data/demo_data.js")
    print(f"  call sites            {concentration['call_site_count']}")
    print(f"  window spend          ${graph['meta']['total_spend_usd']:,.2f}")
    print(f"  spend in top four     {concentration['top_four_spend_share']:.1%}")
    print(f"  hottest               {concentration['hottest_id']} "
          f"({concentration['hottest_spend_share']:.1%} of spend, "
          f"{concentration['hottest_reasoning_share']:.0%} billed reasoning)")
    print(f"  bundle size           {len(bundle) / 1024:,.0f} kilobytes")
    for node in sorted(graph["nodes"], key=lambda n: -n["blast_radius"])[:4]:
        print(f"  blast radius          {node['id']:<28} {node['blast_radius']:.1%}")


if __name__ == "__main__":
    main()
