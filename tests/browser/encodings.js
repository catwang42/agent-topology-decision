// Second harness: the first one reads the DOM synchronously, so anything set
// through a d3 transition still reads as its starting value. This one waits
// for the transitions to land before looking.
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const REPO = process.argv[2] || path.join(__dirname, '..', '..');
const read = (p) => fs.readFileSync(path.join(REPO, p), 'utf8');

// jsdom has no canvas back end; the page copes with a null drawing context and
// carries on. That one message is expected, nothing else is.
const EXPECTED = /Not implemented: HTMLCanvasElement\.prototype\.getContext/;

const errors = [];
const vc = new VirtualConsole();
vc.on('jsdomError', (e) => {
  const text = String(e.stack || e.message);
  if (!EXPECTED.test(text)) errors.push(text);
});

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

  check('beat 4: the thinking-tax core is lit only on the four hot nodes', () => {
    const lit = $$('#layer-nodes > g')
      .filter((g) => opacity(g.querySelector('.core')) > 0.5)
      .map((g) => datum(g).id);
    if (lit.length !== 4) throw new Error(lit.length + ' cores: ' + lit.join(','));
    return lit.join(', ');
  });

  check('beat 4: a bigger thinking tax means a bigger core', () => {
    const cores = $$('#layer-nodes > g')
      .filter((g) => opacity(g.querySelector('.core')) > 0.5)
      .map((g) => {
        const node = window.DEMO_GRAPH.nodes.find((n) => n.id === datum(g).id);
        const share = node.cells.reduce((s, c) => s + c.billed_reasoning_tokens, 0) /
                      node.cells.reduce((s, c) => s + c.billed_output_tokens, 0);
        // The core is a fraction of the node's own radius, so compare the
        // fraction rather than the raw pixels — a big node is not a big tax.
        return { id: datum(g).id, share,
                 fraction: +g.querySelector('.core').getAttribute('r') / datum(g).r };
      })
      .sort((a, b) => b.share - a.share);
    for (let i = 1; i < cores.length; i += 1) {
      if (cores[i].fraction > cores[i - 1].fraction + 1e-6) {
        throw new Error(cores[i].id + ' has a bigger core on a smaller tax');
      }
    }
    return cores.map((c) => c.id + ' ' + (c.share * 100).toFixed(0) + '% → core ' +
      (c.fraction * 100).toFixed(0) + '% of the radius').join(', ');
  });

  check('beat 4: the hottest core is labelled fifty eight percent', () => {
    const g = $$('#layer-nodes > g').find((n) => datum(n).id === 'chunk_summarizer');
    const text = g.querySelector('.core-text');
    if (text.textContent !== '58%') throw new Error('reads ' + text.textContent);
    if (opacity(text) < 0.9) throw new Error('the label is not legible');
    return 'chunk summarizer core reads 58%, core radius ' +
      (+g.querySelector('.core').getAttribute('r')).toFixed(1) + 'px';
  });

  check('beat 4: the spend arc sweeps in proportion to share of the bill', () => {
    const arcs = $$('#layer-nodes > g')
      .filter((g) => opacity(g.querySelector('.spend-arc')) > 0.5)
      .map((g) => {
        const [drawn, whole] = g.querySelector('.spend-arc')
          .getAttribute('stroke-dasharray').split(' ').map(Number);
        return { id: datum(g).id, sweep: drawn / whole };
      })
      .sort((a, b) => b.sweep - a.sweep);
    if (arcs.length !== 4) throw new Error(arcs.length + ' arcs');
    if (arcs[0].id !== 'chunk_summarizer') throw new Error('fullest ring is ' + arcs[0].id);
    if (Math.abs(arcs[0].sweep - 1) > 0.001) throw new Error('the hottest ring is not closed');
    return arcs.map((a) => a.id + ' ' + (a.sweep * 100).toFixed(0) + '%').join(', ');
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
    check('beat 7 week ' + week + ': status dots show the rollout', () => {
      const dotted = $$('#layer-nodes > g')
        .filter((g) => opacity(g.querySelector('.status-dot')) > 0.5)
        .map((g) => datum(g).id + '=' + window.DEMO_TIMELINE.timeline[datum(g).id][week - 1]);
      if (!dotted.length) throw new Error('no status dots at week ' + week);
      if (dotted.some((d) => /=unmeasured$/.test(d))) {
        throw new Error('an unmeasured call site is wearing a status dot');
      }
      return dotted.join(', ');
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
      core: opacity(g.querySelector('.core')),
      dot: g.querySelector('.status-dot').getAttribute('fill'),
      visible: opacity(g)
    };
  };

  check('beat 7 week 8: the migrated call site has visibly cooled', () => {
    const moved = paint('field_extractor');
    const held = paint('chunk_summarizer');
    if (moved.glowRadius !== 0 || moved.glowOpacity !== 0) {
      throw new Error('the migrated node still glows: r=' + moved.glowRadius);
    }
    if (moved.core > 0.01) throw new Error('the thinking-tax core is still lit on a migrated node');
    // Emerald, #10B981 — the one colour on the page that means "moved".
    if (!/16, *185, *129/.test(moved.stroke)) throw new Error('stroke is ' + moved.stroke);
    if (held.glowRadius < 60) throw new Error('the held node stopped glowing: r=' + held.glowRadius);
    if (moved.visible < 0.9) throw new Error('the migrated node became unreadable');
    // Amber, #F59E0B — reserved for hold, so one warning colour on one glyph.
    if (!/^#F59E0B$|245, *158, *11/i.test(held.dot)) throw new Error('the hold dot is ' + held.dot);
    return 'field extractor: fill ' + moved.fill + ', emerald edge, no glow, no core, still legible' +
      '  |  chunk summarizer: fill ' + held.fill + ', glow r=' + held.glowRadius.toFixed(0) +
      ', amber hold dot ' + held.dot;
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

  /* The overflow guarantee. The canvas band is 1440 by 600 in stage pixels and
     the camera is what holds the graph inside it, so take the camera transform
     off the viewport group, apply it to each glyph's own extent — widest halo,
     label, readiness badge and all — and demand the result sits in the
     rectangle. The camera refit is a transition, which is why this lives in
     the harness that waits rather than the one that reads straight away. */
  const BAND = { w: 1440, h: 600 };

  function slackNow() {
    const t = $('#viewport').getAttribute('transform') || '';
    const m = t.match(/translate\(([-\d.e]+),([-\d.e]+)\)\s*scale\(([-\d.e]+)\)/);
    if (!m) throw new Error('no camera transform: ' + t);
    const [cx, cy, k] = [+m[1], +m[2], +m[3]];
    const outside = [];
    let worst = Infinity;
    // Only what the audience can see. Beat zero holds the camera on the top of
    // the stack, and the call sites that have not been revealed yet are at
    // opacity zero — off screen is where they belong.
    const visible = $$('#layer-nodes > g').filter((g) => opacity(g) > 0.02);
    if (visible.length < 1) throw new Error('nothing is visible');
    visible.forEach((g) => {
      const d = datum(g);
      const side = Math.max(d.r + 46, d.labelHalfWidth + 8, 64);
      const x0 = cx + k * (d.x - side);
      const x1 = cx + k * (d.x + side);
      const y0 = cy + k * (d.y - (d.r + 46));
      const y1 = cy + k * (d.y + (d.r + 46));
      const slack = Math.min(x0, y0, BAND.w - x1, BAND.h - y1);
      if (slack < 0) outside.push(d.id + ' by ' + (-slack).toFixed(1) + 'px');
      worst = Math.min(worst, slack);
    });
    if (outside.length) throw new Error(outside.join(', '));
    return { k, slack: worst, shown: visible.length };
  }

  /* ------------------------------------------------------- the floor
     A call site the audience cannot see is a call site that is not in the
     argument. Every glyph carries a ring that clears three to one against the
     background, at every beat and every rollout week — that is the contrast
     ratio the accessibility guidelines ask of a graphical object, and it is
     about what a two pixel ring needs to survive a projector at two metres.
     The check works the ratio out from the attributes the page actually set,
     compositing the stroke over the background at its own opacity. */
  const SPACE = [0x0a, 0x0e, 0x17];
  const MINIMUM_CONTRAST = 3;

  const channel = (v) => {
    const c = v / 255;
    return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  const luminance = (rgb) =>
    0.2126 * channel(rgb[0]) + 0.7152 * channel(rgb[1]) + 0.0722 * channel(rgb[2]);
  const parse = (colour) => {
    const hex = colour.trim().match(/^#([0-9a-f]{6})$/i);
    if (hex) {
      const n = parseInt(hex[1], 16);
      return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
    }
    const rgb = colour.match(/rgba?\(([^)]+)\)/i);
    if (!rgb) throw new Error('cannot read the colour ' + JSON.stringify(colour));
    const parts = rgb[1].split(',').map((v) => parseFloat(v));
    return [parts[0], parts[1], parts[2]];
  };
  const over = (rgb, alpha) => rgb.map((v, i) => alpha * v + (1 - alpha) * SPACE[i]);
  const contrast = (colour, alpha) => {
    const lit = luminance(over(parse(colour), alpha));
    const back = luminance(SPACE);
    return (Math.max(lit, back) + 0.05) / (Math.min(lit, back) + 0.05);
  };

  function faintestGlyph() {
    const glyphs = $$('#layer-nodes > g');
    if (glyphs.length !== 19) throw new Error(glyphs.length + ' glyphs in the layer');
    let worst = { ratio: Infinity };
    glyphs.forEach((g) => {
      const body = g.querySelector('.node-body');
      const label = g.querySelector('.node-label');
      const groupOpacity = opacity(g);
      if (groupOpacity < 1) {
        throw new Error(datum(g).id + ' is faded to ' + groupOpacity.toFixed(2));
      }
      const alpha = +(body.getAttribute('stroke-opacity') ?? 1);
      const width = +(body.getAttribute('stroke-width') ?? 1);
      const ratio = contrast(body.getAttribute('stroke'), alpha);
      if (width < 2) throw new Error(datum(g).id + ' has a ' + width + 'px ring');
      if (+label.getAttribute('opacity') < 0.68) {
        throw new Error(datum(g).id + ' label at ' + label.getAttribute('opacity'));
      }
      if (ratio < worst.ratio) worst = { ratio, id: datum(g).id, width };
    });
    if (worst.ratio < MINIMUM_CONTRAST) {
      throw new Error(worst.id + ' rings at ' + worst.ratio.toFixed(2) +
        ' to 1, under the ' + MINIMUM_CONTRAST + ' to 1 floor');
    }
    return worst;
  }

  const dots = $$('#beat-dots .beat-dot');
  const tightest = [];
  const faintest = [];
  for (let beat = 0; beat < dots.length; beat += 1) {
    dots[beat].dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
    await settle();
    /* eslint-disable no-loop-func */
    check('beat ' + beat + ': every glyph, halo and label sits inside the canvas band', () => {
      const r = slackNow();
      tightest.push(r.slack);
      return r.shown + ' glyphs on screen, camera scale ' + r.k.toFixed(3) +
        ', clearance ' + r.slack.toFixed(1) + 'px';
    });
    check('beat ' + beat + ': all nineteen call sites clear the visibility floor', () => {
      const worst = faintestGlyph();
      faintest.push(worst.ratio);
      return 'nineteen rings on screen, faintest ' + worst.id + ' at ' +
        worst.ratio.toFixed(2) + ' to 1 on a ' + worst.width + 'px stroke';
    });
  }

  // The rollout is eight separate pictures, so it gets checked eight times
  // rather than once. The camera does not move between weeks, but which call
  // sites are lit does, and a week that dropped one into the dark would be a
  // week the audience could not count.
  const weekSegments = $$('#week-pill .week-seg');
  for (let week = 1; week <= 8; week += 1) {
    weekSegments[week - 1].dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
    await settle();
    /* eslint-disable no-loop-func */
    check('rollout week ' + week + ': the whole topology is still on screen', () => {
      const worst = faintestGlyph();
      faintest.push(worst.ratio);
      const r = slackNow();
      if (+$('#scrub-week').textContent !== week) throw new Error('the scrubber says week ' + $('#scrub-week').textContent);
      return 'nineteen rings, faintest at ' + worst.ratio.toFixed(2) +
        ' to 1, clearance ' + r.slack.toFixed(1) + 'px';
    });
  }

  check('nothing anywhere in the story falls under the visibility floor', () => {
    const worst = Math.min(...faintest);
    return 'faintest ring across nine beats and eight rollout weeks: ' +
      worst.toFixed(2) + ' to 1 against the background, floor is ' +
      MINIMUM_CONTRAST + ' to 1';
  });

  // Beat seven is presenter paced. Landing on it must not start anything.
  check('the rollout does not move on its own', async () => {});
  dots[7].dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  const landedOn = $('#scrub-week').textContent;
  await settle();
  await settle();
  await settle();
  results.pop();
  check('the rollout does not move on its own', () => {
    if (landedOn !== '1') throw new Error('landed on week ' + landedOn);
    if ($('#scrub-week').textContent !== '1') {
      throw new Error('drifted to week ' + $('#scrub-week').textContent + ' with no input');
    }
    if (+$('#scrub-range').value !== 1) throw new Error('the slider drifted to ' + $('#scrub-range').value);
    return 'four and a bit seconds on beat seven with no key pressed: still week one';
  });

  check('the graph never touches the caption or the controls', () => {
    if (!tightest.length) throw new Error('no beats were measured');
    const worst = Math.min(...tightest);
    if (worst < 0) throw new Error('overflow of ' + (-worst).toFixed(1) + 'px');
    /* The stage is a fixed 1440 by 900 scaled by one uniform factor, so a
       composition that fits here fits on a thirteen inch 1280 by 800 screen at
       scale 0.889 as well — same rectangle, same ratio, fewer pixels. */
    return 'tightest clearance across all nine beats: ' + worst.toFixed(1) +
      'px at 1440×900, ' + (worst * 0.889).toFixed(1) + 'px at 1280×800';
  });

  // Beat two has the whole system on screen with nothing over it; beat six
  // puts the decision card on top. The camera should have moved the graph out
  // from under the card rather than letting the two share the pixels.
  const cameraAt = () => {
    const m = $('#viewport').getAttribute('transform')
      .match(/translate\(([-\d.e]+),([-\d.e]+)\)\s*scale\(([-\d.e]+)\)/);
    return { x: +m[1], y: +m[2], k: +m[3] };
  };
  const rightEdge = (c) => Math.max(...$$('#layer-nodes > g')
    .filter((g) => opacity(g) > 0.02)
    .map((g) => c.x + c.k * (datum(g).x +
      Math.max(datum(g).r + 46, datum(g).labelHalfWidth + 8, 64))));

  dots[2].dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await settle();
  const uncovered = cameraAt();
  const uncoveredRight = rightEdge(uncovered);

  dots[6].dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  await settle();
  const covered = cameraAt();
  const coveredRight = rightEdge(covered);
  const CARD_LEFT = 1440 - 724;

  check('opening the decision card moves the graph out from under it', () => {
    if (!(covered.x < uncovered.x)) {
      throw new Error('the camera did not pan: x ' + uncovered.x.toFixed(1) +
        ' → ' + covered.x.toFixed(1));
    }
    if (coveredRight > CARD_LEFT) {
      throw new Error('a glyph reaches ' + coveredRight.toFixed(0) +
        'px, past the card edge at ' + CARD_LEFT + 'px');
    }
    return 'rightmost glyph ' + uncoveredRight.toFixed(0) + 'px → ' +
      coveredRight.toFixed(0) + 'px, card edge at ' + CARD_LEFT + 'px';
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
