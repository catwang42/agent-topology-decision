# The Decision Layer

**ILLUSTRATIVE DEMO — synthetic traces.** Every number in this repository is
synthetic and labelled as such. No number here implies a measurement of any
real system, model, or vendor. See [CLAUDE.md](CLAUDE.md) for the rules that
keep it that way.

A four minute, presenter driven visual that makes one argument legible:

> Migrating an agent to a different model is not one decision. It is a decision
> per call site, and most of the call sites should never be decided at all.

This is the **Map** layer of a Map → Measure → Decide story. It shows you where
the money is and which call sites are decidable today. It does not tell you the
answer, because it has not measured anything — the answers come from the
[measurement workbench](https://github.com/catwang42/agent-migration-workbench),
which is where the instruments live.

## Open it

```
open index.html
```

That is the whole thing. No server, no build, no network. Open the file.

## Present it

Three ways to advance, all of them visible. The control bar across the bottom
carries an arrow either side and a dot for every beat, so you can jump straight
to one; the right arrow key, the space bar, or a click anywhere on the canvas
steps forward; the left arrow steps back. On load a pulsing affordance says
*click anywhere to begin* and leaves once you have. Nothing on this page is
clickable without looking clickable.

Every beat is a pure function of the beat number, so you can walk it backwards
mid-presentation without anything getting stuck.

Beat seven is the exception, and only in that it takes eight presses instead of
one. It is the eight week rollout, and it steps one week per press so the
presenter can talk over each one. Nothing in it moves on its own. The beat's
dot in the control bar unrolls into a segmented pill, one segment per week,
that fills as you go — so you always know how many presses are left before the
story moves on.

| Beat | What happens | The line |
| --- | --- | --- |
| 0 | A question types itself; one node pulses | A customer asks one question. |
| 1 | One trajectory animates call by call, counter to forty seven | One question. Forty-seven model calls. This is why "which model" feels unanswerable. |
| 2 | The trajectory fades and thirty days of traffic flood the edges | Stop evaluating runs. Look at the system. |
| 3 | Spend ignites — four glyphs run hot, fifteen fall to near black | Your fifty-call problem is a four-node problem. |
| 4 | A glowing core opens inside each glyph: billed reasoning share | Part of this heat isn't work — it's default settings. |
| 5 | Behaviour class borders draw on; readiness badges appear | The instrument matches the behavior — and we refuse verdicts where we didn't measure. |
| 6 | The decision card slides in on the hottest call site | Three numbers and a contract. That's what "safe to move" looks like. |
| 7 | Eight presses, one rollout week each; a line per week says what moved | One call site at a time. Never big-bang. Watch the bill. |
| 8 | Zoom out to the scoreboard | The biggest prize did not clear. That is the contract working, not the contract failing. |

After beat eight the page enters free explore: pan, zoom, hover any call site
for its volume, cost per day, billed reasoning share, blast radius and rollout
status, click for its decision card. The environment and team filters and the
week scrubber stay live throughout, and they really recompute — filtering to
one team changes which four call sites are the hot four.

## What is on screen

Nineteen call sites in a generic enterprise customer support agent, spanning
the four behaviour classes the workbench distinguishes: **transform**,
**tool decider**, **retrieval**, and **orchestration**.

Each call site is a set of concentric rings rather than a flat disc, and every
ring carries one thing:

| Ring | What it encodes |
| --- | --- |
| Outer ring, stroke pattern | Behaviour class — one pattern per class |
| Swept ring | Share of total spend, drawn as an arc around the glyph |
| Body, radius | Call volume over the thirty day window |
| Body, colour | Spend intensity, on the cyan to violet to magenta ramp |
| Inner core | Share of billed output that is reasoning the caller never sees |
| Orbit dot | Rollout status — migrated, in shadow, canary, or hold |

Radius and colour deliberately disagree, because the biggest circle is not the
most expensive one, and that is the first thing a map is for.

Traffic runs as particles along the edges: speed follows call frequency,
density follows volume, and colour follows the edge. When a call site migrates,
its stream turns emerald and visibly thins — the picture of a bill going down.
When one is held back, its stream stays dense and picks up the warning amber.

The rollout ends with one call site migrated, one in shadow, one on HOLD, and
sixteen unmeasured by design. The sixteen are the point as much as the one: a
call site that does not carry enough spend to pay for its own measurement
should not be measured, and a map is what tells you which those are.

## Regenerate the data

```
python3 scripts/export_schema.py        # vendor the trace schema (needs the workbench nearby)
python3 scripts/gen_demo_traces.py      # generate the synthetic world
python3 scripts/aggregate.py            # build data/graph.json and data/demo_data.js
python3 -m pytest tests/                # schema, arithmetic, timeline, labelling
```

The generator is seeded (`20260818`), so the same command produces the same
world every time. The seed and the generation date are printed in the page
footer.

## Layout

```
index.html app.js style.css   the page
lib/d3.v7.min.js              D3 version seven, vendored for offline use
lib/inter-variable-latin.woff2 the typeface, vendored for offline use
schema/trace.schema.json      the canonical trace schema, exported and versioned
scripts/export_schema.py      pulls that schema from the measurement workbench
scripts/gen_demo_traces.py    the synthetic world, seeded
scripts/aggregate.py          traffic in, graph and browser bundle out
data/status_timeline.json     the eight week rollout, authored by hand
data/decision_cards.json      the decision cards, authored by hand
tests/                        data tests, run with pytest
tests/browser/                optional page tests, run with node and jsdom
```

## The visual language

**The grid.** The stage is a fixed 1440 by 900 rectangle scaled by one uniform
factor to fit the screen it lands on, divided into five bands that never
overlap: header, canvas, caption, controls, footer. Every band's position and
height is a custom property in `style.css`, and `tests/test_layout.py` checks
by arithmetic that they tile and fit. The graph is clamped to the canvas band —
the camera refits with six percent of padding on every beat change, and the
band clips anything the camera gets wrong. Overlays slide over the canvas as
glass cards and the camera pans out from under them rather than fighting for
the pixels.

**The floor.** Every one of the nineteen call sites is drawn in every frame of
the story, and none of them is ever allowed to disappear. A dormant call site
still carries a two pixel ring in cool slate, a faint interior, and its name at
seventy percent — enough to clear three to one against the background, which is
the contrast an object needs to be seen rather than guessed at. Heat and
dimming work as a range above that floor rather than a fade towards nothing:
beat three drops the fifteen cold call sites *to* the floor, which is what lets
the room count them and see that four of nineteen hold the money. Before spend
ignites, beats zero to two hold every glyph a step above the floor, so the
topology reads as a real system from the first frame. `tests/browser/` checks
the contrast ratio of every ring in every beat and every rollout week, and the
minimum glyph diameter, at both screen sizes.

**The palette.** Deep space: background `#0A0E17`, a cyan accent for flow and
activity, dormant call sites at `#1E293B` and near invisible. Spend reads as
colour temperature along a single ramp — `#22D3EE` cyan to `#8B5CF6` violet to
`#EC4899` magenta. There is no orange anywhere on the page except one amber,
`#F59E0B`, reserved for a call site whose gates did not clear. One amber ring
on one glyph reads as a warning without needing a legend, which only works if
nothing else on the page is amber. `tests/test_layout.py` enforces that too.

## The schema contract

`schema/trace.schema.json` is exported from `amw/traces/schema.py` in the
measurement workbench and pinned to the commit it came from. Every trace this
repository generates validates against it, and the Langfuse shaped export
converts back into a canonical trace that also validates. That round trip is
tested, which makes this generator usable as a converter fixture rather than
just a demo prop.

Re-export it whenever the workbench schema moves:

```
python3 scripts/export_schema.py --workbench ../agent-migration-workbench
```

## Where real values would attach

One file: `data/decision_cards.json`. Replace the card bodies, keep the keys,
and the page renders measured values with no other change. Nothing else in the
codebase needs to know. On the day that happens, the badge and CLAUDE.md
rule two change with it — in that order, in the same commit.
