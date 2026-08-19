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

The right arrow, the space bar, or a click advances a beat. The left arrow goes
back one. Every beat is a pure function of the beat number, so you can walk it
backwards mid-presentation without anything getting stuck.

| Beat | What happens | The line |
| --- | --- | --- |
| 0 | A question types itself; one node pulses | A customer asks one question. |
| 1 | One trajectory animates call by call, counter to forty seven | One question. Forty-seven model calls. This is why "which model" feels unanswerable. |
| 2 | The trajectory fades; thirty days of traffic overlay it | Stop evaluating runs. Look at the system. |
| 3 | Cost heat ignites — four nodes glow, fifteen fall away | Your fifty-call problem is a four-node problem. |
| 4 | A striped inner band shows billed reasoning share | Part of this heat isn't work — it's default settings. |
| 5 | Behaviour class borders draw on; readiness badges appear | The instrument matches the behavior — and we refuse verdicts where we didn't measure. |
| 6 | The decision card slides in on the hottest call site | Three numbers and a contract. That's what "safe to move" looks like. |
| 7 | The scrubber drags across eight weeks of rollout | One call site at a time. Never big-bang. Watch the bill. |
| 8 | Zoom out to the scoreboard | The biggest prize did not clear. That is the contract working, not the contract failing. |

After beat eight the page enters free explore: pan, zoom, hover any call site
for its volume, cost per day, billed reasoning share, blast radius and rollout
status, click for its decision card. The environment and team filters and the
week scrubber stay live throughout, and they really recompute — filtering to
one team changes which four call sites are the hot four.

## What is on screen

Nineteen call sites in a generic enterprise customer support agent, spanning
the four behaviour classes the workbench distinguishes: **transform**,
**tool decider**, **retrieval**, and **orchestration**. Circle area is call
volume. Warmth and glow are spend. Those two deliberately disagree, because the
biggest circle is not the most expensive one, and that is the first thing a
map is for.

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
schema/trace.schema.json      the canonical trace schema, exported and versioned
scripts/export_schema.py      pulls that schema from the measurement workbench
scripts/gen_demo_traces.py    the synthetic world, seeded
scripts/aggregate.py          traffic in, graph and browser bundle out
data/status_timeline.json     the eight week rollout, authored by hand
data/decision_cards.json      the decision cards, authored by hand
tests/                        data tests, run with pytest
tests/browser/                optional page tests, run with node and jsdom
```

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
