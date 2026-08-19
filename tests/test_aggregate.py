"""Aggregator arithmetic.

The page is only as honest as its arithmetic. These tests pin the figures the
audience actually reads: the concentration headline, the reasoning share on the
hottest call site, blast radius, and the environment and team grid the browser
re-sums every time a filter is clicked.

None of these are measurements. They are checks that a synthetic fixture adds
up to what the page claims it adds up to.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"


def load(name: str) -> dict:
    path = DATA / name
    if not path.exists():
        pytest.skip(f"{name} is missing. Run the two scripts in scripts/ first.")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def graph() -> dict:
    return load("graph.json")


@pytest.fixture(scope="module")
def nodes(graph) -> dict:
    return {node["id"]: node for node in graph["nodes"]}


# ----------------------------------------------------------------- shares


def test_spend_shares_sum_to_one(graph):
    total = sum(node["spend_share"] for node in graph["nodes"])
    assert total == pytest.approx(1.0, abs=1e-9)


def test_call_shares_sum_to_one(graph):
    total = sum(node["call_share"] for node in graph["nodes"])
    assert total == pytest.approx(1.0, abs=1e-9)


def test_spend_share_matches_spend_over_total(graph, nodes):
    # The share is derived before rounding and the dollar figure is rounded to
    # the cent, so compare in dollars: the share must reprice to the same bill
    # to within half a cent.
    total_spend = graph["meta"]["total_spend_usd"]
    for node in graph["nodes"]:
        repriced = node["spend_share"] * total_spend
        assert repriced == pytest.approx(node["spend_usd"], abs=0.005), node["id"]


def test_four_call_sites_carry_about_seventy_percent(graph):
    """Beat three's whole claim: a fifty call problem is a four node problem."""
    concentration = graph["concentration"]
    assert len(concentration["top_four_ids"]) == 4
    assert 0.65 <= concentration["top_four_spend_share"] <= 0.75

    ranked = sorted(graph["nodes"], key=lambda n: -n["spend_share"])
    recomputed = sum(node["spend_share"] for node in ranked[:4])
    assert concentration["top_four_spend_share"] == pytest.approx(recomputed, abs=1e-12)
    assert concentration["top_four_ids"] == [node["id"] for node in ranked[:4]]


def test_the_hottest_call_site_is_the_chunk_summarizer(graph):
    concentration = graph["concentration"]
    assert concentration["hottest_id"] == "chunk_summarizer"
    # Beat four says fifty eight percent of its billed output is reasoning.
    assert concentration["hottest_reasoning_share"] == pytest.approx(0.58, abs=0.015)


def test_the_second_hottest_carries_about_a_fifth_of_spend(nodes):
    """Beat seven needs the migrating call site to be visible on the bill.

    The ruling asked for roughly twenty two percent so that moving one call
    site drops the running total by an amount a person can see.
    """
    assert nodes["field_extractor"]["spend_share"] == pytest.approx(0.22, abs=0.02)


def test_the_biggest_circle_is_not_the_most_expensive(nodes):
    """The encoding earns its keep only if volume and spend disagree somewhere."""
    by_calls = max(nodes.values(), key=lambda n: n["calls"])
    by_spend = max(nodes.values(), key=lambda n: n["spend_usd"])
    assert by_calls["id"] != by_spend["id"] or by_calls["spend_share"] < 0.5


# ----------------------------------------------------------- blast radius


def test_blast_radius_is_a_share(graph):
    for node in graph["nodes"]:
        assert 0.0 <= node["blast_radius"] < 1.0, node["id"]


def test_the_orchestrator_has_the_widest_blast_radius(graph):
    widest = max(graph["nodes"], key=lambda n: n["blast_radius"])
    assert widest["id"] == "conversation_orchestrator"
    assert widest["blast_radius"] > 0.8


def test_blast_radius_matches_a_walk_of_the_edges(graph, nodes):
    """Recomputed here independently, so a bug in the aggregator shows up."""
    outgoing: dict[str, list[str]] = {node["id"]: [] for node in graph["nodes"]}
    for edge in graph["edges"]:
        outgoing[edge["source"]].append(edge["target"])
    total_calls = sum(node["calls"] for node in graph["nodes"])

    for node in graph["nodes"]:
        seen: set[str] = set()
        stack = list(outgoing[node["id"]])
        while stack:
            current = stack.pop()
            if current in seen or current == node["id"]:
                continue
            seen.add(current)
            stack.extend(outgoing[current])
        expected = sum(nodes[other]["calls"] for other in seen) / total_calls
        assert node["blast_radius"] == pytest.approx(expected, rel=1e-9), node["id"]


def test_a_leaf_call_site_has_no_downstream(graph, nodes):
    targets = {edge["source"] for edge in graph["edges"]}
    leaves = [node for node in graph["nodes"] if node["id"] not in targets]
    assert leaves, "the graph has no leaf call sites, which makes blast radius meaningless"
    for leaf in leaves:
        assert leaf["blast_radius"] == 0.0


# ------------------------------------------------- the filter grid the page re-sums


def test_cells_reconstruct_each_call_site(graph):
    """The browser sums these cells on every filter click. They must be whole."""
    for node in graph["nodes"]:
        assert sum(cell["calls"] for cell in node["cells"]) == node["calls"]
        assert sum(cell["cost_usd"] for cell in node["cells"]) == pytest.approx(
            node["spend_usd"], abs=0.05
        ), node["id"]


def test_every_call_site_appears_in_every_environment_and_team(graph):
    environments = set(graph["meta"]["environments"])
    teams = set(graph["meta"]["teams"])
    expected = {(environment, team) for environment in environments for team in teams}
    for node in graph["nodes"]:
        present = {(cell["environment"], cell["team"]) for cell in node["cells"]}
        assert present == expected, node["id"]
        for cell in node["cells"]:
            assert cell["calls"] > 0, f"{node['id']} {cell}"


def test_filtering_never_produces_a_larger_total_than_no_filter(graph):
    total = sum(node["spend_usd"] for node in graph["nodes"])
    for environment in graph["meta"]["environments"]:
        subtotal = sum(
            cell["cost_usd"]
            for node in graph["nodes"]
            for cell in node["cells"]
            if cell["environment"] == environment
        )
        assert 0 < subtotal < total


def test_the_environments_partition_the_spend(graph):
    total = sum(node["spend_usd"] for node in graph["nodes"])
    parts = sum(
        cell["cost_usd"]
        for node in graph["nodes"]
        for cell in node["cells"]
    )
    assert parts == pytest.approx(total, abs=0.05)


def test_reasoning_share_is_a_share(graph):
    for node in graph["nodes"]:
        assert 0.0 <= node["billed_reasoning_share"] <= 1.0, node["id"]
        assert node["billed_reasoning_tokens"] <= node["billed_output_tokens"], node["id"]


# ---------------------------------------------------------------- the graph


def test_edges_name_known_call_sites(graph, nodes):
    for edge in graph["edges"]:
        assert edge["source"] in nodes, edge
        assert edge["target"] in nodes, edge
        assert edge["source"] != edge["target"], edge
        assert 0 < edge["frequency"] <= 1.0, edge


def test_the_graph_has_the_loops_that_make_it_a_topology(graph, nodes):
    """A tree would be a lie. Retries and re-entry are the whole point."""
    back_edges = [
        edge for edge in graph["edges"]
        if nodes[edge["target"]]["layer"] <= nodes[edge["source"]]["layer"]
    ]
    assert back_edges, "no call site ever hands control back up the stack"


def test_all_four_behavior_classes_are_present(graph):
    classes = {node["behavior_class"] for node in graph["nodes"]}
    assert classes == {"transform", "tool decider", "retrieval", "orchestration"}


def test_the_daily_series_reconstructs_the_window(graph):
    for node in graph["nodes"]:
        assert len(node["daily_cost_usd"]) == graph["meta"]["window_days"]
        assert sum(node["daily_cost_usd"]) == pytest.approx(node["spend_usd"], abs=0.05)
