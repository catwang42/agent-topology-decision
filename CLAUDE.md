# Working rules for this repository

This repository is a presentation. It exists to make one argument legible in
about four minutes: that migrating an agent to a different model is not one
decision, it is a decision per call site. Everything here serves that argument,
and the argument only works if the audience can trust what is on screen.

Three rules. They are not style preferences. Breaking any of them breaks the
thing the demo is for.

## Rule one — every view carries the badge

Every view carries the badge:

> ILLUSTRATIVE DEMO — synthetic traces

It sits in the top right corner of the stage and it never leaves, at any beat,
in any mode. There is no exception, no overlay that covers it, and no beat
where it fades out because the composition looks cleaner without it.

If you add a new screen, a new panel, or a new export, the badge comes with it.

## Rule two — every number is synthetic and labelled as such

Every number in this repository is synthetic and labelled as such. No number
may imply measurement, period.

What this rules out, concretely:

- No value copied from a real scorecard, benchmark, price list, or dashboard.
- No number described as observed, recorded, benchmarked, or reported.
- No "measured" tag on a decision card, or anywhere else. The tag does not
  exist in the stylesheet and it should stay that way.
- No named vendor or product attached to any figure, so that no reader can take
  a synthetic number as evidence about a real model.

What it does not rule out: statements about method. The page says "measurable
now" and "measure last", and the rollout timeline has a status called Measured.
Those describe what an instrument could do and where it should be pointed
first. They report no finding. The distinction is the whole point of the demo,
so keep it sharp: a claim about method is welcome, a claim about a result is
not.

Real values may attach later, and there is exactly one place for them to
attach: `data/decision_cards.json`. Replace the card bodies, keep the keys, and
the page renders them with no other change. On the day that happens, rule two
changes with it, in this file first.

Tests enforce what can be enforced: see `tests/test_honesty.py`.

## Rule three — plain language, no abbreviations

Write everything out. In captions, labels, tooltips, comments, commit messages,
and file names.

Write "ninety fifth percentile", not "p95" in prose. Write "confidence range",
not "CI". Write "percentage points", not "pp", outside a table cell where space
genuinely forbids it. Write "Conversation Orchestrator", not "orch".

The audience for this page is a vice president who has thirty seconds of
patience for jargon and none for decoding. An abbreviation saves the author
four characters and costs the reader the sentence.

Field names in data files are the one exception, because they are contracts
rather than prose. Even there, prefer `billed_reasoning_share` over `brs`.

---

## How the pieces fit

```
scripts/export_schema.py     pulls the canonical trace schema from the
                             measurement workbench into schema/
scripts/gen_demo_traces.py   generates the synthetic world: call sites, edges,
                             thirty days of traffic, sample trajectories
scripts/aggregate.py         turns traffic into data/graph.json and the browser
                             bundle data/demo_data.js
index.html app.js style.css  the page: nine beats, then free explore
data/status_timeline.json    the eight week rollout, authored by hand
data/decision_cards.json     the decision cards, authored by hand
```

Regenerate everything with:

```
python3 scripts/gen_demo_traces.py
python3 scripts/aggregate.py
python3 -m pytest tests/
```

## Constraints that are not negotiable

- No build step, no framework, no bundler. Plain HTML, CSS, and JavaScript,
  with D3 version seven.
- The page must open from a file path with no server and no network. That is
  why the data arrives as a script that assigns globals rather than as a fetch,
  and why D3 is vendored into `lib/`.
- The stage is a fixed 1440 by 900 canvas, scaled to fit the screen it lands
  on. Design for the projector, degrade to the laptop.
