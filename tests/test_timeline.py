"""Rollout timeline integrity.

Beat seven drags a scrubber across eight weeks and beat eight totals the
result. Both read this one authored file, so the file has to be internally
consistent: every call site covered, every week present, no status that skips a
step it should not skip, and a final scoreboard that matches the last column.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"

ORDER = ["unmeasured", "measured", "shadow", "canary", "migrated"]


def load(name: str) -> dict:
    path = DATA / name
    if not path.exists():
        pytest.skip(f"{name} is missing. Run the two scripts in scripts/ first.")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def timeline() -> dict:
    return load("status_timeline.json")


@pytest.fixture(scope="module")
def graph() -> dict:
    return load("graph.json")


@pytest.fixture(scope="module")
def cards() -> dict:
    return load("decision_cards.json")


# ------------------------------------------------------------- coverage


def test_the_timeline_covers_exactly_the_call_sites(timeline, graph):
    node_ids = {node["id"] for node in graph["nodes"]}
    assert set(timeline["timeline"]) == node_ids


def test_every_call_site_has_a_status_for_every_week(timeline):
    week_count = len(timeline["weeks"])
    assert week_count == 8
    for site_id, statuses in timeline["timeline"].items():
        assert len(statuses) == week_count, site_id


def test_every_status_is_declared(timeline):
    known = set(timeline["statuses"])
    for site_id, statuses in timeline["timeline"].items():
        assert set(statuses) <= known, site_id


def test_the_weeks_are_contiguous_and_in_order(timeline):
    from datetime import date, timedelta

    previous_end = None
    for index, week in enumerate(timeline["weeks"], start=1):
        assert week["week"] == index
        start = date.fromisoformat(week["start"])
        end = date.fromisoformat(week["end"])
        assert end - start == timedelta(days=6), week
        if previous_end is not None:
            assert start - previous_end == timedelta(days=1), week
        previous_end = end


# --------------------------------------------------------------- shape


def test_no_call_site_moves_backwards_except_into_hold(timeline):
    """A rollout can stall, and it can be rolled back onto HOLD. It cannot
    quietly regress from canary to unmeasured without the hold that explains
    why. HOLD is the only reverse gear, and it is terminal in this fixture."""
    for site_id, statuses in timeline["timeline"].items():
        rank = -1
        for status in statuses:
            if status == "hold":
                rank = 99
                continue
            assert rank != 99, f"{site_id} left HOLD, which this fixture does not model"
            assert ORDER.index(status) >= rank, f"{site_id} went backwards: {statuses}"
            rank = ORDER.index(status)


def test_shadow_does_not_change_the_bill(timeline):
    """Shadow runs beside production. If it lowered spend the demo would be
    claiming a saving nobody banked."""
    statuses = timeline["statuses"]
    assert statuses["unmeasured"]["cost_multiplier"] == 1.0
    assert statuses["measured"]["cost_multiplier"] == 1.0
    assert statuses["shadow"]["cost_multiplier"] == 1.0
    assert statuses["hold"]["cost_multiplier"] == 1.0
    assert statuses["canary"]["cost_multiplier"] < 1.0
    assert statuses["migrated"]["cost_multiplier"] < statuses["canary"]["cost_multiplier"]


def test_the_final_scoreboard_matches_the_last_column(timeline):
    last = [statuses[-1] for statuses in timeline["timeline"].values()]
    declared = timeline["final_scoreboard"]
    assert last.count("migrated") == declared["migrated"] == 1
    assert last.count("shadow") == declared["shadow"] == 1
    assert last.count("hold") == declared["hold"] == 1
    assert last.count("unmeasured") == declared["unmeasured"] == 16
    assert len(last) == 19


def test_the_hottest_call_site_ends_on_hold(timeline, graph):
    """The closing line depends on this: the biggest prize did not clear."""
    hottest = graph["concentration"]["hottest_id"]
    assert timeline["timeline"][hottest][-1] == "hold"


def test_the_second_hottest_call_site_ends_migrated(timeline, graph):
    ranked = sorted(graph["nodes"], key=lambda n: -n["spend_share"])
    assert timeline["timeline"][ranked[1]["id"]][-1] == "migrated"


# ------------------------------------------- the bill the scrubber reports


def weekly_spend(timeline: dict, graph: dict, week: int) -> float:
    statuses = timeline["statuses"]
    return sum(
        node["spend_usd"] * statuses[timeline["timeline"][node["id"]][week - 1]]["cost_multiplier"]
        for node in graph["nodes"]
    )


def test_the_bill_falls_over_the_eight_weeks(timeline, graph):
    first = weekly_spend(timeline, graph, 1)
    last = weekly_spend(timeline, graph, 8)
    assert last < first
    # Moving one call site of roughly a fifth of spend has to be visible.
    assert (first - last) / first > 0.10


def test_the_bill_ticks_back_up_when_the_canary_is_rolled_back(timeline, graph):
    """Week seven to week eight goes the wrong way on purpose. That is the
    chunk summarizer's canary being withdrawn when its gates did not clear.
    If this ever becomes monotonic, the honest detail has been polished away."""
    assert weekly_spend(timeline, graph, 8) > weekly_spend(timeline, graph, 7)


# ----------------------------------------------- cards agree with statuses


def test_each_decision_card_matches_its_final_status(timeline, cards):
    for site_id, card in cards["cards"].items():
        assert card["rollout_status"] == timeline["timeline"][site_id][-1], site_id


def test_only_measured_looking_call_sites_carry_a_card(timeline, cards, graph):
    """Sixteen call sites are unmeasured by design. None of them may carry a
    card, because a card would imply an instrument was pointed at them."""
    for node in graph["nodes"]:
        final = timeline["timeline"][node["id"]][-1]
        has_card = node["id"] in cards["cards"]
        assert has_card == (final != "unmeasured"), node["id"]
        assert node["has_decision_card"] == has_card, node["id"]


def test_the_hold_card_reports_a_failing_gate(cards):
    card = cards["cards"]["chunk_summarizer"]
    assert card["verdict"] == "UNDETERMINED"
    assert any(gate["result"] == "FAIL" for gate in card["gates"])


def test_the_migrate_card_has_no_failing_gate(cards):
    card = cards["cards"]["field_extractor"]
    assert card["verdict"] == "MIGRATE"
    assert all(gate["result"] == "PASS" for gate in card["gates"])


def test_the_shadow_card_has_no_verdict_at_all(cards):
    card = cards["cards"]["response_drafter"]
    assert all(gate["result"] == "PENDING" for gate in card["gates"])
    assert card["gates_evaluated"].startswith("0")


def test_the_gates_contract_is_pinned(cards):
    contract = cards["gates_contract"]
    assert contract["version"] == 1
    assert contract["hash"]
    assert contract["hash_is_synthetic"] is True
    for card in cards["cards"].values():
        declared = {gate["name"] for gate in card["gates"]}
        assert declared == set(contract["bounds"]), card["call_site"]
