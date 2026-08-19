// Second harness: the first one reads the DOM synchronously, so anything set
// through a d3 transition still reads as its starting value. This one waits
// for the transitions to land before looking.
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const REPO = process.argv[2] || path.join(__dirname, '..', '..');
const read = (p) => fs.readFileSync(path.join(REPO, p), 'utf8');

const errors = [];
const vc = new VirtualConsole();
vc.on('jsdomError', (e) => errors.push(String(e.stack || e.message)));

let html = read('index.html')
  .replace(/<script src="https:\/\/[^"]+"><\/script>/, '')
  .replace(/<script>window\.d3[\s\S]*?<\/script>/, '')
  .replace(/<script src="(data\/demo_data\.js|app\.js|lib\/[^"]+)"><\/script>/g, '');

const dom = new JSDOM(html, {
  runScripts: 'dangerously', pretendToBeVisual: true, virtualConsole: vc,
  url: 'file://' + REPO + '/index.html'
});
const { window } = dom;
const run = (file) => {
  const s = window.document.createElement('script');
  s.textContent = read(file);
  window.document.body.appendChild(s);
};
run('lib/d3.v7.min.js');
run('data/demo_data.js');
run('app.js');

const doc = window.document;
const $ = (s) => doc.querySelector(s);
const $$ = (s) => Array.from(doc.querySelectorAll(s));
const key = (k) => window.dispatchEvent(new window.KeyboardEvent('keydown', { key: k, bubbles: true }));
const settle = () => new Promise((r) => setTimeout(r, 1400));

const results = [];
const check = (name, fn) => {
  try { results.push(['ok  ', name, fn() ?? '']); }
  catch (e) { results.push(['FAIL', name, e.message]); }
};
const opacity = (el) => +(el.getAttribute('opacity') ?? el.style.opacity ?? 1);
const datum = (el) => window.d3.select(el).datum();

(async () => {
  for (let i = 0; i < 4; i += 1) key('ArrowRight');   // beat 4
  await settle();

  check('beat 4: the reasoning band is visible only on the four hot nodes', () => {
    const lit = $$('#layer-nodes > g')
      .filter((g) => opacity(g.querySelector('.reasoning-band')) > 0.5)
      .map((g) => datum(g).id);
    if (lit.length !== 4) throw new Error(lit.length + ' bands: ' + lit.join(','));
    return lit.join(', ');
  });

  check('beat 4: the hottest band sweeps fifty eight percent of the ring', () => {
    const g = $$('#layer-nodes > g').find((n) => datum(n).id === 'chunk_summarizer');
    const band = g.querySelector('.reasoning-band');
    const [drawn, whole] = band.getAttribute('stroke-dasharray').split(' ').map(Number);
    const share = drawn / whole;
    if (Math.abs(share - 0.58) > 0.02) throw new Error('sweeps ' + (share * 100).toFixed(1) + '%');
    return (share * 100).toFixed(1) + '% of the circumference, label reads ' +
      g.querySelector('.reasoning-text').textContent;
  });

  check('beat 4: the glow scales with spend, hottest brightest', () => {
    const glows = $$('#layer-glow circle')
      .map((c) => [datum(c).id, +c.getAttribute('r')])
      .filter(([, r]) => r > 0)
      .sort((a, b) => b[1] - a[1]);
    if (glows.length !== 4) throw new Error(glows.length + ' glowing');
    if (glows[0][0] !== 'chunk_summarizer') throw new Error('brightest is ' + glows[0][0]);
    return glows.map(([id, r]) => id + ' r=' + r.toFixed(0)).join(', ');
  });

  key('ArrowRight');   // beat 5
  await settle();

  check('beat 5: class rings are drawn and differ by behaviour class', () => {
    const dashes = {};
    $$('#layer-nodes > g').forEach((g) => {
      const ring = g.querySelector('.class-ring');
      if (opacity(ring) > 0.5) dashes[datum(g).behavior_class] = ring.getAttribute('stroke-dasharray');
    });
    const distinct = new Set(Object.values(dashes));
    if (distinct.size < 3) throw new Error(JSON.stringify(dashes));
    return Object.entries(dashes).map(([k, v]) => k + ': ' + (v === null ? 'solid' : v)).join(' | ');
  });

  check('beat 5: readiness badges are legible where they matter', () => {
    const shown = $$('#layer-nodes > g')
      .filter((g) => opacity(g.querySelector('.node-badge')) > 0.5)
      .map((g) => datum(g).id + '=' + g.querySelector('.node-badge').textContent);
    if (!shown.some((s) => s.startsWith('conversation_orchestrator=measure last'))) {
      throw new Error(shown.join(', '));
    }
    return shown.join(', ');
  });

  key('ArrowRight'); key('ArrowRight');   // beats 6, 7
  await settle();
  const range = $('#scrub-range');
  const setWeek = (w) => {
    range.value = String(w);
    range.dispatchEvent(new window.Event('input', { bubbles: true }));
  };

  for (const week of [4, 6, 7, 8]) {
    setWeek(week);
    await settle();
    check('beat 7 week ' + week + ': status rings show the rollout', () => {
      const ringed = $$('#layer-nodes > g')
        .filter((g) => opacity(g.querySelector('.status-ring')) > 0.5)
        .map((g) => datum(g).id + '=' + window.DEMO_TIMELINE.timeline[datum(g).id][week - 1]);
      if (!ringed.length) throw new Error('no rings at week ' + week);
      return ringed.join(', ');
    });
  }

  const paint = (id) => {
    const g = $$('#layer-nodes > g').find((n) => datum(n).id === id);
    const glow = $$('#layer-glow circle').find((c) => datum(c).id === id);
    return {
      fill: g.querySelector('.node-body').getAttribute('fill'),
      stroke: g.querySelector('.node-body').getAttribute('stroke'),
      glowRadius: +glow.getAttribute('r'),
      glowOpacity: +glow.getAttribute('opacity'),
      band: opacity(g.querySelector('.reasoning-band')),
      ring: g.querySelector('.status-ring').getAttribute('stroke'),
      visible: opacity(g)
    };
  };

  check('beat 7 week 8: the migrated call site has visibly cooled', () => {
    const moved = paint('field_extractor');
    const held = paint('chunk_summarizer');
    if (moved.glowRadius !== 0 || moved.glowOpacity !== 0) {
      throw new Error('the migrated node still glows: r=' + moved.glowRadius);
    }
    if (moved.band > 0.01) throw new Error('the reasoning band is still lit on a migrated node');
    if (!/53, *196, *168/.test(moved.stroke)) throw new Error('stroke is ' + moved.stroke);
    if (held.glowRadius < 60) throw new Error('the held node stopped glowing: r=' + held.glowRadius);
    if (moved.visible < 0.9) throw new Error('the migrated node became unreadable');
    return 'field extractor: fill ' + moved.fill + ', teal edge, no glow, no band, still legible' +
      '  |  chunk summarizer: fill ' + held.fill + ', glow r=' + held.glowRadius.toFixed(0) +
      ', hold ring ' + held.ring;
  });

  const atWeekEight = paint('field_extractor');
  setWeek(1);
  await settle();
  check('beat 7: the same call site was warm at week one', () => {
    const atWeekOne = paint('field_extractor');
    if (atWeekOne.glowRadius <= 0) throw new Error('it never glowed at week one');
    if (atWeekOne.fill === atWeekEight.fill) throw new Error('the fill never changed');
    return 'week one ' + atWeekOne.fill + ' glow r=' + atWeekOne.glowRadius.toFixed(0) +
      '  →  week eight ' + atWeekEight.fill + ' glow r=' + atWeekEight.glowRadius.toFixed(0);
  });

  check('no error was logged', () => {
    if (errors.length) throw new Error(errors.join(' | '));
  });

  let failed = 0;
  for (const [s, n, d] of results) {
    if (s === 'FAIL') failed += 1;
    console.log(s + ' ' + n + (d ? '\n       ' + d : ''));
  }
  console.log('\n' + (results.length - failed) + ' passed, ' + failed + ' failed');
  process.exit(failed ? 1 : 0);
})();
