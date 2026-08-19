"""The labelling rules, enforced.

Rule two of CLAUDE.md: every number in this repository is synthetic and
labelled as such; no number may imply measurement, period. That rule is easy to
agree with and easy to erode one commit at a time, so it is checked here.

Note the rule is about numbers, not about the word. The page says "measurable
now" and "measure last" as statements of method, and the rollout has a status
called Measured. Those are claims about what an instrument could do, not
reports of what one found. What is banned is a value presented as an
observation of a real system.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"

BADGE = "ILLUSTRATIVE DEMO — synthetic traces"


def data_files() -> list[Path]:
    return sorted(path for path in DATA.glob("*.json"))


def test_the_cancelled_reference_file_is_gone():
    """C2 was cancelled. Nothing in this repository copies a real scorecard."""
    stray = list(REPO_ROOT.rglob("measured_reference*"))
    assert not stray, f"the cancelled reference fixture came back: {stray}"


def test_no_source_file_mentions_the_cancelled_fixture():
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "lib" in path.parts:
            continue
        if path.suffix not in {".py", ".js", ".json", ".html", ".css", ".md"}:
            continue
        if path.name == "test_honesty.py":
            continue
        assert "measured_reference" not in path.read_text(encoding="utf-8"), path


def test_every_data_file_declares_itself_synthetic():
    files = data_files()
    assert files, "there is no data to check"
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        head = payload.get("meta", payload)
        assert head.get("synthetic") is True, f"{path.name} does not declare itself synthetic"
        assert "synthetic" in head.get("notice", "").lower(), f"{path.name} has no notice"


def test_the_browser_bundle_is_labelled_at_the_top():
    bundle = DATA / "demo_data.js"
    if not bundle.exists():
        pytest.skip("run scripts/aggregate.py first")
    head = bundle.read_text(encoding="utf-8")[:400]
    assert "synthetic" in head.lower()
    assert "not measured" in head.lower()


def test_the_badge_is_on_the_page():
    page = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    assert BADGE in page


def test_the_page_never_fetches_anything():
    """The demo has to open from a file path with no network."""
    app = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    for banned in ("fetch(", "XMLHttpRequest", "d3.json(", "d3.csv("):
        assert banned not in app, f"app.js uses {banned}, which fails from a file path"


def test_the_vendored_library_loads_before_the_network_copy():
    """Opening the file from a disk path must make no network request at all,
    so the local copy is the primary and the pinned remote copy is the
    fallback, not the other way round."""
    page = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    vendored = (REPO_ROOT / "lib" / "d3.v7.min.js")
    assert vendored.exists(), "the vendored library is missing"
    assert vendored.stat().st_size > 100_000, "the vendored library looks truncated"

    local_at = page.index("lib/d3.v7.min.js")
    remote_at = page.index("cdn.jsdelivr.net")
    assert local_at < remote_at, "the network copy is loaded before the vendored one"


def test_the_page_loads_nothing_else_off_the_network():
    for name in ("index.html", "style.css", "app.js"):
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        for line in text.splitlines():
            if "http://" not in line and "https://" not in line:
                continue
            allowed = (
                "cdn.jsdelivr.net" in line          # the D3 fallback
                or "github.com" in line             # links the presenter clicks
                or line.lstrip().startswith(("*", "//", "/*"))
            )
            assert allowed, f"{name} reaches the network: {line.strip()}"


def test_the_footer_names_the_generator_and_the_seed():
    """Rule three of the honesty chrome: say where the numbers came from."""
    page = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    app = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
    assert "scripts/gen_demo_traces.py" in page
    assert "seed" in app


def test_no_trace_claims_customer_provenance():
    """The workbench schema allows `customer`. This repository may not use it."""
    path = DATA / "traces_sample.jsonl"
    if not path.exists():
        pytest.skip("run scripts/gen_demo_traces.py first")
    for line in path.read_text(encoding="utf-8").splitlines():
        if line:
            assert json.loads(line)["provenance"] == "synthetic"


def test_the_model_names_are_vendor_neutral():
    """No number here may be read as evidence about a named vendor's model."""
    cards = json.loads((DATA / "decision_cards.json").read_text(encoding="utf-8"))
    names = {cards["incumbent"]["id"], cards["candidate"]["id"]}
    forbidden = ("gpt", "claude", "gemini", "llama", "mistral", "grok", "sonnet", "haiku", "opus")
    for name in names:
        assert not any(brand in name.lower() for brand in forbidden), name


def test_the_decision_cards_say_where_real_values_would_attach():
    """The ruling: keep the structure so real values can attach via one file."""
    cards = json.loads((DATA / "decision_cards.json").read_text(encoding="utf-8"))
    assert cards["attach_real_values_here"]
    for card in cards["cards"].values():
        assert {"verdict", "headline", "gates", "why", "next"} <= set(card)
        for metric in card["headline"]:
            assert {"name", "value", "range", "result"} <= set(metric)


def test_claude_md_carries_the_three_rules():
    path = REPO_ROOT / "CLAUDE.md"
    if not path.exists():
        pytest.fail("CLAUDE.md is missing")
    text = " ".join(path.read_text(encoding="utf-8").split())
    assert BADGE in text
    assert "Every number in this repository is synthetic and labelled as such." in text
    assert "No number may imply measurement, period." in text
    assert "abbreviation" in text.lower()


def test_no_card_prose_describes_a_number_as_measured():
    """The rule bites hardest on the decision cards, because they carry figures.

    "Latency, ninety fifth percentile — 7,400 ms, incumbent measured at 6,900 ms"
    reads as a report of what somebody ran. Nobody ran anything. The prose that
    sits beside a figure has to say where the figure came from, and the only
    honest answer in this repository is: it was invented.

    Statements of method are still welcome, and the exclusion below is what
    keeps them welcome — "the page renders measured values" describes what
    would happen on the day real values attach, and reports no finding.
    """
    payload = json.loads((DATA / "decision_cards.json").read_text(encoding="utf-8"))

    # Whole words only, which is what lets "unmeasured by design" and "pay for
    # the measurement" through. Those say a thing was not measured, or that
    # measuring costs money. Neither hands the reader a figure.
    banned = re.compile(r"\b(measured|observed|recorded|benchmarked|reported)\b", re.I)

    def prose_beside_a_figure(card: dict):
        for metric in card.get("headline", []):
            yield metric.get("basis", "")
        yield card.get("verdict_line", "")
        yield card.get("why", "")
        yield card.get("next", "")

    offenders = []
    everything = dict(payload["cards"])
    everything["unmeasured_card"] = payload["unmeasured_card"]
    for call_site, card in everything.items():
        for line in prose_beside_a_figure(card):
            hit = banned.search(line or "")
            if hit:
                offenders.append(f"{call_site}: {line!r} says {hit.group(0)!r}")

    assert not offenders, "a figure is presented as an observation:\n  " + "\n  ".join(offenders)


def test_the_browser_bundle_carries_the_same_card_prose_as_the_source():
    """The page reads the bundle, not the source, so the two must agree.

    Editing a card and forgetting to run scripts/aggregate.py leaves the fixed
    wording in the repository and the old wording on the screen, which is the
    worst of both: the rule looks kept and is not.
    """
    bundle = DATA / "demo_data.js"
    if not bundle.exists():
        pytest.skip("run scripts/aggregate.py first")
    source = json.loads((DATA / "decision_cards.json").read_text(encoding="utf-8"))
    text = bundle.read_text(encoding="utf-8")
    line = next(l for l in text.splitlines() if l.startswith("window.DEMO_CARDS ="))
    baked = json.loads(line[len("window.DEMO_CARDS = "):].rstrip(";"))
    assert baked == source, "data/demo_data.js is stale: run scripts/aggregate.py"
