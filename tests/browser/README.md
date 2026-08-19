# Browser tests

Optional. The demo itself has no build step, no framework, and no
`node_modules`, and these two files do not change that — they are run from a
scratch directory outside the repository so nothing installs here.

They exist because the load-bearing part of this repository is a page, and a
page that throws on load is a blank projector at the worst possible moment.
`tests/` covers the data. These cover the page.

## Running them

```
mkdir -p /tmp/decision-layer-tests && cd /tmp/decision-layer-tests
npm init -y && npm install jsdom@24
export NODE_PATH=/tmp/decision-layer-tests/node_modules
node /path/to/agent-topology-decision/tests/browser/beats.js
node /path/to/agent-topology-decision/tests/browser/encodings.js
```

`NODE_PATH` is what lets the scripts find jsdom while living outside the
directory it was installed into. Version twenty four is pinned because later
versions pull in a dependency that this repository's node cannot load.

Both print a line per check and exit non-zero on failure.

## What each one covers

`beats.js` walks the whole presentation the way a presenter does. It loads the
vendored copy of D3 and the generated data bundle, then advances through all
nine beats with the right arrow and reverses all the way back with the left
arrow. It asserts the things a presenter cannot afford to discover live: that
nineteen call sites and their edges draw with finite coordinates, that the
counter reaches forty seven, that beat three lights exactly four nodes and dims
fifteen, that the environment and team filters really recompute the panel and
really reset, that the decision card opens on the right call site with its
gates hash, that the scrubber drives the bill across eight weeks, that the
scoreboard reads one, one, one, sixteen, that the closing caption is verbatim,
and that the honesty badge is still on screen at the end.

`encodings.js` does the same walk but waits for the transitions to land before
looking, because a synchronous read sees a transition's starting value rather
than its destination. It checks the visual encodings themselves: that the
reasoning band appears on exactly the four hot call sites and sweeps fifty
eight percent of the ring on the hottest one, that the four behaviour classes
draw four distinguishable borders, that the orchestrator's "measure last" badge
is legible rather than dimmed away, that the status rings track the rollout
week by week, and that the call site which migrates goes visibly cool while the
one that lands on HOLD stays hot.

Neither test asserts anything about a real system. They check that a synthetic
fixture renders the way the presenter's script says it will.
