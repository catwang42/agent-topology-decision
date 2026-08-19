// Headless smoke test for the decision layer page. Lives outside the repo on
// purpose: the demo itself has no build step and no node_modules.
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const REPO = process.argv[2] || path.join(__dirname, '..', '..');
const read = (p) => fs.readFileSync(path.join(REPO, p), 'utf8');

// jsdom has no canvas back end, so asking for a drawing context is reported as
// an error even though the page handles a null context and carries on. That
// one message is expected here and nowhere else.
const EXPECTED = /Not implemented: HTMLCanvasElement\.prototype\.getContext/;

const errors = [];
const vc = new VirtualConsole();
vc.on('jsdomError', (e) => {
  const text = 'jsdomError: ' + (e.stack || e.message);
  if (!EXPECTED.test(text)) errors.push(text);
});
vc.on('error', (...a) => errors.push('console.error: ' + a.join(' ')));

// Drop the network script tag; the vendored copy is what we exercise.
let html = read('index.html').replace(/<script src="https:\/\/[^"]+"><\/script>/, '');
html = html.replace(/<script>window\.d3[\s\S]*?<\/script>/, '');
html = html.replace(/<script src="(data\/demo_data\.js|app\.js|lib\/[^"]+)"><\/script>/g, '');

const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  pretendToBeVisual: true,
  virtualConsole: vc,
  url: 'file://' + REPO + '/index.html'
});
const { window } = dom;

function run(file) {
  const script = window.document.createElement('script');
  script.textContent = read(file);
  window.document.body.appendChild(script);
}

const results = [];
function check(name, fn) {
  try {
    const detail = fn();
    results.push(['ok  ', name, detail === undefined ? '' : detail]);
  } catch (e) {
    results.push(['FAIL', name, e.message]);
  }
}

run('lib/d3.v7.min.js');
check('d3 loaded', () => 'version ' + window.d3.version);
run('data/demo_data.js');
check('data bundle loaded', () => window.DEMO_GRAPH.nodes.length + ' call sites');
run('app.js');
check('app.js ran with no thrown error', () => {
  if (errors.length) throw new Error(errors.join(' | '));
});

const doc = window.document;
const $ = (sel) => doc.querySelector(sel);
const $$ = (sel) => Array.from(doc.querySelectorAll(sel));
const on = (id) => $('#' + id).classList.contains('on');

check('no data screen is hidden', () => {
  if (on('nodata')) throw new Error('the missing-data screen is showing');
});

check('nineteen nodes drawn', () => {
  const n = $$('#layer-nodes > g').length;
  if (n !== 19) throw new Error('drew ' + n);
  return n + ' node groups';
});

check('edges drawn', () => {
  const n = $$('#layer-edges > path').length;
  if (n < 20) throw new Error('drew ' + n);
  return n + ' edges';
});

/* The camera is what keeps the graph inside the canvas band. This harness
   reads the document the instant a beat changes, and the camera refit is a
   transition, so all it can honestly check here is that the transform is well
   formed and the geometry finite. Whether every glyph actually landed inside
   the band is checked in encodings.js, after the transitions have finished. */
function cameraReport() {
  const t = $('#viewport').getAttribute('transform') || '';
  const m = t.match(/translate\(([-\d.e]+),([-\d.e]+)\)\s*scale\(([-\d.e]+)\)/);
  if (!m) throw new Error('no camera transform: ' + t);
  const [cx, cy, k] = [+m[1], +m[2], +m[3]];
  if (!isFinite(cx) || !isFinite(cy) || !isFinite(k) || k <= 0) {
    throw new Error('camera is ' + t);
  }
  const broken = $$('#layer-nodes > g').filter((g) => {
    const d = window.d3.select(g).datum();
    return !isFinite(d.x) || !isFinite(d.y) || !isFinite(d.r);
  });
  if (broken.length) throw new Error(broken.length + ' nodes have non-finite geometry');
  return { k };
}

check('the camera is well formed and every node has finite geometry', () => {
  return 'camera scale ' + cameraReport().k.toFixed(3) + ', 19 nodes placed';
});

check('edge paths are finite', () => {
  const bad = $$('#layer-edges > path').filter((p) => /NaN|undefined/.test(p.getAttribute('d') || 'x'));
  if (bad.length) throw new Error(bad.length + ' paths contain NaN');
});

check('the particle canvas sits under the graph, not over it', () => {
  const canvas = $('#particles');
  const svg = $('#graph');
  if (!canvas) throw new Error('no particle canvas');
  if (canvas.compareDocumentPosition(svg) !== window.Node.DOCUMENT_POSITION_FOLLOWING) {
    throw new Error('the canvas is not before the graph in the document');
  }
  return 'canvas ' + canvas.width + '×' + canvas.height + ' device pixels, drawn beneath the nodes';
});

check('filter chips rendered', () => {
  const env = $$('#filter-environment .chip').length;
  const team = $$('#filter-team .chip').length;
  if (env !== 3 || team !== 4) throw new Error(env + ' environment, ' + team + ' team');
  return env + ' environment chips, ' + team + ' team chips';
});

// ------------------------------------------------------------------ beats
const key = (k) => window.dispatchEvent(new window.KeyboardEvent('keydown', { key: k, bubbles: true }));
const forward = () => key('ArrowRight');
const back = () => key('ArrowLeft');

check('beat 0 shows the cold open with the typed question', () => {
  if (!on('coldopen')) throw new Error('cold open not on');
  if ($('#caption-line').textContent.length < 10) throw new Error('no caption');
  return JSON.stringify($('#caption-beat').textContent);
});

forward();
check('beat 1 shows the counter', () => {
  if (!on('counter')) throw new Error('counter not on');
  return 'caption: ' + $('#caption-line').textContent.slice(0, 46) + '…';
});

forward();
check('beat 2 reveals every call site and the counter reads forty seven', () => {
  const v = $('#counter-value').textContent;
  if (v !== '47') throw new Error('counter reads ' + v);
  const hidden = $$('#layer-nodes > g').filter((g) => +(g.getAttribute('opacity') || 1) < 0.9);
  if (hidden.length) throw new Error(hidden.length + ' nodes still dim');
  return 'counter ' + v + ', all 19 visible';
});

forward();
check('beat 3 dims the cold nodes and lights four', () => {
  const ops = $$('#layer-nodes > g').map((g) => +(g.getAttribute('opacity') || 1));
  const hot = ops.filter((o) => o > 0.9).length;
  const cold = ops.filter((o) => o <= 0.2).length;
  if (hot !== 4) throw new Error(hot + ' hot nodes, expected 4');
  if (cold !== 15) throw new Error(cold + ' dimmed, expected 15');
  return hot + ' hot at full, ' + cold + ' dimmed to 0.12';
});

check('beat 3 panel reports the concentration', () => {
  if (!on('panel')) throw new Error('panel not on');
  const big = $('.conc-big').textContent;
  const rows = $$('#spend-bars .spend-row').length;
  if (!/^\d+%$/.test(big)) throw new Error('headline reads ' + big);
  return big + ' headline, ' + rows + ' rows';
});

check('beat 3 filters are live', () => {
  if (!on('filters')) throw new Error('filters not on');
  const before = $('.conc-big').textContent + ' ' + $$('#spend-bars .spend-name')[0].textContent;
  $$('#filter-team .chip')[3].dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  const after = $('.conc-big').textContent + ' ' + $$('#spend-bars .spend-name')[0].textContent;
  const sub = $('#panel-sub').textContent;
  if (!/team:/.test(sub)) throw new Error('panel does not name the filter: ' + sub);
  $$('#filter-team .chip')[0].dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  const restored = $('.conc-big').textContent + ' ' + $$('#spend-bars .spend-name')[0].textContent;
  if (restored !== before) throw new Error('filter did not restore: ' + before + ' -> ' + restored);
  return 'all → Account Management changed the panel to "' + after + '", and reset cleanly';
});

forward();
check('beat 4 puts the thinking tax in the core of the glyph', () => {
  // The core radius rides a transition, so this harness reads the label, which
  // is set outright. The radius itself is checked in encodings.js after the
  // transitions have landed.
  const texts = $$('#layer-nodes .core-text').map((t) => t.textContent).filter(Boolean);
  if (!texts.includes('58%')) throw new Error('no 58% core; saw ' + texts.join(','));
  return texts.length + ' cores labelled, hottest reads 58%';
});

check('beat 4 keeps the camera well formed', () => {
  return 'camera scale ' + cameraReport().k.toFixed(3);
});

forward();
check('beat 5 draws class rings and readiness badges', () => {
  const rings = $$('#layer-nodes .class-ring').length;
  const badges = $$('#layer-nodes .node-badge').map((b) => b.textContent);
  if (!badges.includes('measure last')) throw new Error('no measure-last badge');
  if (!badges.includes('measurable now')) throw new Error('no measurable-now badge');
  // The name wraps onto two lines in the glyph, so match the whole one.
  const orch = $$('#layer-nodes > g').find((g) => g.getAttribute('aria-label') === 'Conversation Orchestrator');
  if (!orch) throw new Error('no orchestrator glyph');
  const op = +(orch.getAttribute('opacity') || 1);
  if (op < 0.5) throw new Error('orchestrator invisible at ' + op);
  return rings + ' rings; orchestrator legible at opacity ' + op;
});

forward();
check('beat 6 opens the decision card on the hottest call site', () => {
  if (!on('card')) throw new Error('card not on');
  const title = $('.card-title').textContent;
  const verdict = $('.verdict-word').textContent;
  const metrics = $$('.headline-metric').length;
  const hash = $('.gates-hash code').textContent;
  const tag = $('#card .tag-synthetic').textContent.trim();
  if (title !== 'Chunk Summarizer') throw new Error('card is for ' + title);
  if (metrics !== 3) throw new Error(metrics + ' headline metrics');
  if (!/a7f3c1d90e42/.test(hash)) throw new Error('no gates hash: ' + hash);
  if (!/synthetic/i.test(tag)) throw new Error('card is not tagged synthetic');
  if (on('panel')) throw new Error('the spend panel is still under the card');
  return title + ' — ' + verdict + ' — ' + metrics + ' metrics — ' + hash;
});

check('beat 6 card does not contradict itself with a rollout row', () => {
  // The scrubber does not exist yet, so there is no week to attach a status
  // to. Showing "week one: unmeasured" beside six evaluated gates would read
  // as a contradiction.
  const body = $('#card-body').textContent;
  if (/Rollout status/.test(body)) throw new Error('the rollout row leaked into beat six');
});

check('beat 6 card shows both a failing and a passing gate', () => {
  const rows = $$('.gate-table tr').map((r) => r.lastElementChild.textContent);
  const fails = rows.filter((r) => r === 'FAIL').length;
  const passes = rows.filter((r) => r === 'PASS').length;
  if (fails !== 2 || passes !== 4) throw new Error(fails + ' fail, ' + passes + ' pass');
  return rows.length + ' gates: ' + passes + ' pass, ' + fails + ' fail';
});

forward();
check('beat 7 shows the scrubber at week one', () => {
  if (!on('scrubber')) throw new Error('scrubber not on');
  if ($('#scrub-week').textContent !== '1') throw new Error('starts at week ' + $('#scrub-week').textContent);
  return $('#scrub-dates').textContent + ' · ' + $('#scrub-spend').textContent.replace(/<[^>]+>/g, '');
});

const spendByWeek = [];
check('beat 7 scrubber drives the whole page', () => {
  const range = $('#scrub-range');
  const seen = [];
  for (let week = 1; week <= 8; week += 1) {
    range.value = String(week);
    range.dispatchEvent(new window.Event('input', { bubbles: true }));
    const spend = $('#scrub-spend').textContent.match(/\$[\d,]+/)[0];
    spendByWeek.push(+spend.replace(/[$,]/g, ''));
    const flagged = $$('#layer-nodes > g').filter((g) =>
      window.DEMO_TIMELINE.timeline[window.d3.select(g).datum().id][week - 1] !== 'unmeasured').length;
    seen.push('W' + week + ' ' + spend + ' (' + flagged + ' with a status dot)');
  }
  return seen.join('  ');
});

check('beat 7 bill falls as the second hottest call site migrates', () => {
  if (!(spendByWeek[7] < spendByWeek[0])) throw new Error(spendByWeek.join(','));
  const drop = (spendByWeek[0] - spendByWeek[7]) / spendByWeek[0];
  if (drop < 0.10) throw new Error('only ' + (drop * 100).toFixed(1) + '% off the bill');
  return (drop * 100).toFixed(1) + '% off the daily bill by week eight';
});

check('beat 7 bill ticks back up when the canary is rolled back', () => {
  if (!(spendByWeek[7] > spendByWeek[6])) {
    throw new Error('week 7 ' + spendByWeek[6] + ' -> week 8 ' + spendByWeek[7]);
  }
  return 'week seven $' + spendByWeek[6] + ' → week eight $' + spendByWeek[7];
});

check('beat 7 names the rise in plain money, not just as a smaller fall', () => {
  // Against week one, week eight still reads as a fall. The audience should
  // not have to remember 18.4 percent to notice the bill got worse.
  const text = $('#scrub-spend').textContent;
  const rise = text.match(/▲ \$\d+ on last week/);
  if (!rise) throw new Error('week eight does not say it rose: ' + text);
  return text.replace(/\s+/g, ' ').trim();
});

check('beat 7 card follows the scrubber onto hold', () => {
  const text = $('#card-body').textContent;
  if (!/Rollout status, week 8: Hold/.test(text)) {
    throw new Error('card says: ' + (text.match(/Rollout status[^.]*\./) || ['nothing'])[0]);
  }
  return 'card reads "Rollout status, week 8: Hold"';
});

forward();
check('beat 8 shows the scoreboard', () => {
  if (!on('scoreboard')) throw new Error('scoreboard not on');
  const tiles = $$('#scoreboard .tile').map((t) =>
    t.querySelector('.tile-count').textContent + ' ' + t.querySelector('.tile-name').textContent);
  const want = ['1 Migrated', '1 In shadow', '1 Hold', '16 Unmeasured'];
  if (JSON.stringify(tiles) !== JSON.stringify(want)) throw new Error(tiles.join(' · '));
  const links = $$('#scoreboard-links a').length;
  if (links < 3) throw new Error(links + ' links');
  return tiles.join(' · ') + ' — ' + links + ' links';
});

check('beat 8 closing caption is the ruling verbatim', () => {
  const want = 'The biggest prize did not clear. That is the contract working, not the contract failing.';
  const got = $('#caption-line').textContent.trim();
  if (got !== want) throw new Error(JSON.stringify(got));
  return 'verbatim';
});

check('beat 8 scoreboard keeps the closing headline', () => {
  const line = $('#scoreboard-line').textContent.replace(/\s+/g, ' ').trim();
  if (!/The map finds the money/.test(line)) throw new Error(line);
  return line;
});

forward();
check('beat 9 is free explore', () => {
  if (on('scoreboard')) throw new Error('scoreboard still up');
  if (!on('filters')) throw new Error('filters gone');
  return $('#caption-beat').textContent + ' — ' + $('#caption-line').textContent;
});

check('advancing past the last beat is a no-op', () => {
  forward(); forward();
  const beat = $('#caption-beat').textContent;
  if (!/Free explore/.test(beat)) throw new Error(beat);
});

// -------------------------------------------------------------- reversing
check('every beat reverses', () => {
  const seen = [];
  for (let i = 0; i < 9; i += 1) {
    back();
    seen.push($('#caption-beat').textContent.replace('Beat ', 'B').replace(/ —.*/, ''));
  }
  if (seen[8] !== 'B0') throw new Error(seen.join(' '));
  if (errors.length) throw new Error(errors.join(' | '));
  return seen.join(' → ');
});

check('reversing to beat 0 resets the cold open and hides everything else', () => {
  if (!on('coldopen')) throw new Error('cold open not restored');
  for (const id of ['panel', 'filters', 'scrubber', 'scoreboard', 'card']) {
    if (on(id)) throw new Error(id + ' still showing at beat 0');
  }
});

check('forward again from zero reaches beat 8 with the same scoreboard', () => {
  for (let i = 0; i < 8; i += 1) forward();
  const tiles = $$('#scoreboard .tile .tile-count').map((t) => t.textContent).join(',');
  if (tiles !== '1,1,1,16') throw new Error(tiles);
  return 'tiles ' + tiles;
});

// ------------------------------------------------------------- navigation
// Three ways in, and all three have to reach the same nine beats: the control
// bar, the keyboard, and a click anywhere on the canvas.
const click = (el) => el.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
const beatNow = () => $('#caption-beat').textContent;

check('the control bar shows a dot for every beat plus the explore pill', () => {
  const dots = $$('#beat-dots .beat-dot').length;
  const pill = $('#beat-explore');
  if (dots !== 9) throw new Error(dots + ' dots');
  if (!pill) throw new Error('no explore pill');
  return dots + ' beat dots and an "' + pill.textContent + '" pill, all visible at all times';
});

check('every beat is reachable by clicking its dot', () => {
  const seen = [];
  $$('#beat-dots .beat-dot').forEach((dot, i) => {
    click(dot);
    const lit = $$('#beat-dots .beat-dot').filter((d) => d.classList.contains('on'));
    if (lit.length !== 1 || lit[0] !== dot) throw new Error('dot ' + i + ' did not light alone');
    seen.push(beatNow().replace('Beat ', 'B').replace(/ —.*/, ''));
    cameraReport();
  });
  return seen.join(' ');
});

check('the arrow buttons step the beat and disable at the ends', () => {
  click($('#beat-dots .beat-dot'));          // back to beat zero
  if (!$('#nav-prev').disabled) throw new Error('back arrow live at beat zero');
  click($('#nav-next'));
  if (!/Beat 1/.test(beatNow())) throw new Error(beatNow());
  click($('#nav-prev'));
  if (!/Beat 0/.test(beatNow())) throw new Error(beatNow());
  click($('#beat-explore'));
  if (!/Free explore/.test(beatNow())) throw new Error(beatNow());
  if (!$('#nav-next').disabled) throw new Error('forward arrow live at the last beat');
  return 'back disabled at beat zero, forward disabled at free explore';
});

check('clicking the canvas advances, and clicking a control does not', () => {
  click($('#beat-dots .beat-dot'));          // beat zero
  click($('#band-canvas'));
  if (!/Beat 1/.test(beatNow())) throw new Error('a canvas click did not advance: ' + beatNow());
  click($('#band-caption'));
  if (!/Beat 2/.test(beatNow())) throw new Error('a caption click did not advance: ' + beatNow());
  const before = beatNow();
  click($('#scrub-range'));
  click($('#filter-team .chip'));
  if (beatNow() !== before) throw new Error('a control click advanced the beat');
  return 'canvas and caption advance; the scrubber and the filter chips do not';
});

check('the begin affordance appears on load and leaves once used', () => {
  if (on('begin-hint')) throw new Error('the hint came back after the deck had moved');
  const text = $('#begin-hint').textContent.trim();
  if (!/click/i.test(text)) throw new Error(text);
  return '"' + text + '", shown until the first advance';
});

check('beat 8 clears the decision card so the scoreboard stands alone', () => {
  if (on('card')) throw new Error('the card is still over the scoreboard');
  if (on('panel')) throw new Error('the spend panel is still over the scoreboard');
});

// --------------------------------------------------------------- tooltips
check('hovering a call site shows a tooltip with the numbers', () => {
  forward(); // into free explore
  const hits = $$('#layer-nodes .node-hit');
  hits[9].dispatchEvent(new window.MouseEvent('mousemove', { bubbles: true, clientX: 300, clientY: 300 }));
  const tip = $('#tooltip');
  if (!tip.classList.contains('on')) throw new Error('tooltip not shown');
  const labels = $$('#tooltip dt').map((d) => d.textContent);
  const want = ['Calls, thirty days', 'Cost per day', 'Share of spend', 'Billed reasoning', 'Blast radius'];
  if (JSON.stringify(labels) !== JSON.stringify(want)) throw new Error(labels.join(', '));
  return $('.tip-name').textContent + ': ' + $$('#tooltip dd').map((d) => d.textContent).join(' / ');
});

check('clicking an unmeasured call site refuses a verdict', () => {
  const unmeasured = $$('#layer-nodes .node-hit').find((h) => {
    const d = window.d3.select(h).datum();
    return !d.has_decision_card;
  });
  unmeasured.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  const verdict = $('.verdict-word').textContent;
  if (verdict !== 'NOT MEASURED') throw new Error(verdict);
  const body = $('#card-body').textContent;
  if (!/unmeasured by design/.test(body)) throw new Error('no by-design explanation');
  return verdict + ' — and the gates contract is shown but not evaluated';
});

check('the honesty badge survived every beat', () => {
  const badge = $('#badge').textContent.trim();
  if (!/ILLUSTRATIVE DEMO — synthetic traces/.test(badge)) throw new Error(badge);
  return badge;
});

check('the footer names the seed and the generator', () => {
  const foot = $('#footer').textContent.replace(/\s+/g, ' ').trim();
  if (!/seed 20260818/.test(foot)) throw new Error(foot);
  return foot;
});

check('no error was logged at any point', () => {
  if (errors.length) throw new Error(errors.join(' | '));
});

// ------------------------------------------------------------------ report
let failed = 0;
for (const [status, name, detail] of results) {
  if (status === 'FAIL') failed += 1;
  console.log(status + ' ' + name + (detail ? '\n       ' + detail : ''));
}
console.log('\n' + (results.length - failed) + ' passed, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
