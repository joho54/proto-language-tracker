'use strict';
const $ = s => document.querySelector(s);
const el = (t, c, html) => { const e = document.createElement(t); if (c) e.className = c; if (html != null) e.innerHTML = html; return e; };
const esc = s => String(s).replace(/[&<>]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[m]));
const sleep = ms => new Promise(r => setTimeout(r, ms));

/* ───────── the falsifier, ported to run LIVE in the browser ───────── */
const VOWEL = new Set([...'aeiouæɛəɔ']);
const CLASS = {}; // consonant broad class for partial substitution cost
'pbmfvw'.split('').forEach(c => CLASS[c] = 'lab');
'tdnszrlc'.split('').forEach(c => CLASS[c] = 'cor');
'kgxq'.split('').forEach(c => CLASS[c] = 'dor');
CLASS['h'] = 'glo'; CLASS['j'] = 'gli'; CLASS['y'] = 'gli';
function cost(a, b) {
  if (a === b) return 0;
  const va = VOWEL.has(a), vb = VOWEL.has(b);
  if (va && vb) return 0.5;
  if (va !== vb) return 1;
  return (CLASS[a] && CLASS[a] === CLASS[b]) ? 0.5 : 1;
}
function align(a, b) {                       // Needleman–Wunsch, GAP=0.8
  const ps = [...a], ds = [...b], n = ps.length, m = ds.length, GAP = 0.8;
  const D = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = 1; i <= n; i++) D[i][0] = i * GAP;
  for (let j = 1; j <= m; j++) D[0][j] = j * GAP;
  for (let i = 1; i <= n; i++) for (let j = 1; j <= m; j++)
    D[i][j] = Math.min(D[i-1][j-1] + cost(ps[i-1], ds[j-1]), D[i-1][j] + GAP, D[i][j-1] + GAP);
  let i = n, j = m; const al = [];
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && Math.abs(D[i][j] - (D[i-1][j-1] + cost(ps[i-1], ds[j-1]))) < 1e-9) { al.push([ps[i-1], ds[j-1]]); i--; j--; }
    else if (i > 0 && Math.abs(D[i][j] - (D[i-1][j] + GAP)) < 1e-9) { al.push([ps[i-1], null]); i--; }
    else { al.push([null, ds[j-1]]); j--; }
  }
  return al.reverse();
}
function tally(pairs) {                       // joint + marginal counts over aligned segments
  const joint = new Map(), ma = new Map(), mb = new Map(); let tot = 0;
  const inc = (m, k) => m.set(k, (m.get(k) || 0) + 1);
  for (const [a, b] of pairs) for (const [x, y] of align(a, b)) {
    if (x == null || y == null) continue; inc(joint, x + '\t' + y); inc(ma, x); inc(mb, y); tot++;
  }
  return { joint, ma, mb, tot };
}
function miFrom(t) {
  if (!t.tot) return 0; let I = 0;
  for (const [k, c] of t.joint) { const [x, y] = k.split('\t'); const pxy = c / t.tot, px = t.ma.get(x) / t.tot, py = t.mb.get(y) / t.tot; I += pxy * Math.log(pxy / (px * py)); }
  return I;
}
const mutualInfo = pairs => miFrom(tally(pairs));
function mulberry32(s) { return () => { s |= 0; s = s + 0x6D2B79F5 | 0; let t = Math.imul(s ^ s >>> 15, 1 | s); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function shuffled(arr, rnd) { const a = arr.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1));[a[i], a[j]] = [a[j], a[i]]; } return a; }

/* quick (non-animated) MI + p for the summary cards */
function quickPval(pairs, nperm, seed) {
  const obs = mutualInfo(pairs);
  const A = pairs.map(p => p[0]), B = pairs.map(p => p[1]); const rnd = mulberry32(seed);
  let ge = 0; for (let k = 0; k < nperm; k++) { const Bs = shuffled(B, rnd); if (mutualInfo(A.map((a, i) => [a, Bs[i]])) >= obs) ge++; }
  return { mi: obs, p: (ge + 1) / (nperm + 1) };
}

/* ───────── state ───────── */
let PRESETS = {}, ORDER = [], SUMMARY = {}, runToken = 0;

async function boot() {
  const idx = await fetch('data/presets/index.json').then(r => r.json());
  ORDER = idx.presets.map(p => p.id);
  await Promise.all(idx.presets.map(async p => { PRESETS[p.id] = await fetch('data/presets/' + p.file).then(r => r.json()); }));
  // compute live summary for the contrast grid (seeded → stable)
  ORDER.forEach((id, i) => {
    const d = PRESETS[id]; const pairs = d.pairs.map(p => [p.a, p.b]);
    SUMMARY[id] = quickPval(pairs, 300, 1234 + i);
  });
  const bar = $('#preset-buttons');
  idx.presets.forEach(p => {
    const b = el('button', 'pbtn'); b.dataset.kind = p.kind; b.dataset.id = p.id;
    b.innerHTML = `<span class="dot"></span>${esc(p.label)}`;
    b.onclick = () => select(p.id);
    bar.appendChild(b);
  });
  renderContrast();
  select(ORDER[0]);
}

function select(id) {
  document.querySelectorAll('.pbtn').forEach(b => b.classList.toggle('active', b.dataset.id === id));
  const d = PRESETS[id];
  $('#stage').hidden = false;
  $('#now-label').textContent = d.label;
  $('#lang-a').textContent = d.langA; $('#lang-b').textContent = d.langB;
  $('#nperm').textContent = d.nperm.toLocaleString();
  $('#pairs-n').textContent = d.n; $('#pairs-shown').textContent = Math.min(d.pairs.length, 40);
  renderPairs(d);
  run(d);                       // ← actually executes the pipeline, live
}

function renderPairs(d) {
  const box = $('#pairs'); box.innerHTML = '';
  d.pairs.slice(0, 40).forEach(p => {
    const c = el('div', 'pair');
    c.innerHTML = `<div class="cc">${esc(p.concept)}</div>
      <div class="ww"><span class="wa">${esc(p.a_raw)}</span><span class="wb">${esc(p.b_raw)}</span></div>
      <div class="ww"><span class="ph">/${esc(p.a)}/</span><span class="ph">/${esc(p.b)}/</span></div>`;
    box.appendChild(c);
  });
}

/* run the whole pipeline live, with animation */
async function run(d) {
  const my = ++runToken;
  const pairs = d.pairs.map(p => [p.a, p.b]);
  $('#reshuffle').disabled = true;

  // STAGE 2 — align first 10 pairs (computed live)
  const abox = $('#align'); abox.innerHTML = '';
  for (let i = 0; i < Math.min(10, pairs.length); i++) {
    if (my !== runToken) return;
    const [a, b] = pairs[i]; const cells = align(a, b);
    const row = el('div', 'alnrow fade-in');
    row.appendChild(el('span', 'cc', esc(d.pairs[i].concept)));
    const cc = el('div', 'cells');
    cells.forEach(([x, y]) => {
      const match = x !== null && x === y;
      const cell = el('div', 'cell' + (match ? ' match' : ''));
      cell.innerHTML = `<span class="top${x === null ? ' gap' : ''}">${x === null ? '·' : esc(x)}</span><span class="${y === null ? 'gap' : ''}">${y === null ? '·' : esc(y)}</span>`;
      cc.appendChild(cell);
    });
    row.appendChild(cc); abox.appendChild(row);
    await sleep(45);
  }

  // STAGE 3 — tally the correspondence table live, pair by pair
  const acc = { joint: new Map(), ma: new Map(), mb: new Map(), tot: 0 };
  const inc = (m, k) => m.set(k, (m.get(k) || 0) + 1);
  for (let i = 0; i < pairs.length; i++) {
    if (my !== runToken) return;
    for (const [x, y] of align(pairs[i][0], pairs[i][1])) { if (x == null || y == null) continue; inc(acc.joint, x + '\t' + y); inc(acc.ma, x); inc(acc.mb, y); acc.tot++; }
    if (i % 6 === 0 || i === pairs.length - 1) { drawMatrix(acc); await sleep(16); }
  }
  drawMatrix(acc);

  // STAGE 4 — MI (computed live)
  const obs = miFrom(acc);
  $('#mi').innerHTML = `<span class="val">0.000</span><span class="lab">bits of mutual information<br>(0 = independent; higher = systematic correspondence)</span>`;
  await tween(0, obs, 700, v => { $('#mi .val').textContent = v.toFixed(3); }, () => my === runToken);

  // STAGE 5 — permutation null, run LIVE (each shuffle fills the histogram)
  await runPermutation(d, pairs, obs, my);

  if (my !== runToken) return;
  $('#reshuffle').disabled = false;
}

async function runPermutation(d, pairs, obs, my) {
  const A = pairs.map(p => p[0]), B = pairs.map(p => p[1]);
  const nperm = d.nperm; const nulls = []; let ge = 0;
  const t0 = performance.now();
  for (let k = 0; k < nperm; k++) {
    if (my !== runToken) return;
    const Bs = shuffled(B, Math.random);
    const mi = mutualInfo(A.map((a, i) => [a, Bs[i]]));
    nulls.push(mi); if (mi >= obs) ge++;
    if (k % 4 === 0 || k === nperm - 1) {
      drawNull(nulls, obs, (ge + 1) / (k + 2), k + 1, nperm);
      await new Promise(requestAnimationFrame);
    }
  }
  const p = (ge + 1) / (nperm + 1);
  drawNull(nulls, obs, p, nperm, nperm);
  renderVerdict(d, obs, p);
}

$('#reshuffle').onclick = () => { const id = document.querySelector('.pbtn.active')?.dataset.id; if (!id) return; const d = PRESETS[id]; const pairs = d.pairs.map(p => [p.a, p.b]); runPermutation(d, pairs, mutualInfo(pairs), runToken); };

/* ───────── drawing ───────── */
function drawMatrix(acc) {
  const rows = [...acc.ma.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12).map(e => e[0]);
  const cols = [...acc.mb.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12).map(e => e[0]);
  let max = 1; for (const r of rows) for (const c of cols) max = Math.max(max, acc.joint.get(r + '\t' + c) || 0);
  const cw = 30, ch = 26, padL = 34, padT = 26, W = padL + cols.length * cw + 8, H = padT + rows.length * ch + 6;
  let s = `<svg viewBox="0 0 ${W} ${H}">`;
  cols.forEach((c, j) => s += `<text class="axt" x="${padL + j * cw + cw / 2}" y="${padT - 9}" text-anchor="middle">${esc(c)}</text>`);
  rows.forEach((r, i) => {
    s += `<text class="axt" x="${padL - 7}" y="${padT + i * ch + ch / 2 + 4}" text-anchor="end">${esc(r)}</text>`;
    cols.forEach((c, j) => {
      const v = acc.joint.get(r + '\t' + c) || 0, t = v / max;
      const fill = v === 0 ? '#f3f6f9' : `rgba(43,108,176,${0.12 + 0.88 * t})`;
      s += `<rect x="${padL + j * cw}" y="${padT + i * ch}" width="${cw - 2}" height="${ch - 2}" rx="3" fill="${fill}"/>`;
      if (t > 0.18) s += `<text x="${padL + j * cw + cw / 2 - 1}" y="${padT + i * ch + ch / 2 + 4}" text-anchor="middle" font-size="11" fill="${t > 0.55 ? '#fff' : '#2b6cb0'}">${v}</text>`;
    });
  });
  $('#matrix').innerHTML = s + '</svg>';
}

function drawNull(vals, obs, p, done, total) {
  const lo = Math.min(...vals, obs), hi = Math.max(...vals, obs), span = (hi - lo) || 1;
  const nb = 36, W = 560, H = 220, padL = 8, padR = 8, padT = 12, padB = 30, iw = W - padL - padR, ih = H - padT - padB;
  const bins = new Array(nb).fill(0);
  vals.forEach(v => { let k = Math.floor((v - lo) / span * nb); if (k >= nb) k = nb - 1; if (k < 0) k = 0; bins[k]++; });
  const bmax = Math.max(1, ...bins), bw = iw / nb, xObs = padL + (obs - lo) / span * iw;
  let s = `<svg viewBox="0 0 ${W} ${H}">`;
  s += `<text class="axt" x="${padL}" y="${H - 8}">MI under random pairings →</text>`;
  bins.forEach((b, k) => { const h = ih * (b / bmax); s += `<rect x="${padL + k * bw}" y="${padT + ih - h}" width="${bw - 1}" height="${h}" rx="1.5" fill="#cbd5e1"/>`; });
  s += `<line x1="${xObs}" y1="${padT - 4}" x2="${xObs}" y2="${padT + ih}" stroke="#c5384b" stroke-width="2.5"/>`;
  s += `<text x="${Math.min(xObs, W - 92)}" y="${padT + 4}" fill="#c5384b" font-size="12" font-weight="700">real MI ${obs.toFixed(2)}</text>`;
  $('#null').innerHTML = s + '</svg>' +
    `<div class="meta" style="margin-top:6px">shuffle <b>${done}</b>/${total.toLocaleString()} · p ≈ <b style="font-size:16px;color:${p < 0.05 ? '#1c7a4a' : '#475569'}">${p.toFixed(3)}</b></div>`;
}

function renderVerdict(d, mi, p) {
  const verdict = d.n < d.horizon ? 'BELOW_HORIZON' : (p < 0.05 ? 'DETECTED' : 'FLOOR');
  const txt = { DETECTED: 'Signal beats chance', FLOOR: 'Lost in the noise', BELOW_HORIZON: 'Too few cognates to tell' }[verdict];
  const flag = d.kind === 'cherry' ? ' cherry-flag' : '';
  let caveat = '';
  if ((d.kind === 'claim' || d.kind === 'control') && Math.abs(p - 0.05) < 0.04)
    caveat = `<div class="note">⚠ p sits right on the 0.05 line — a coin-flip. Hit "re-run the shuffles": the label wobbles. That's why one "p &lt; 0.05" proves nothing here.</div>`;
  SUMMARY[d.id] = { mi, p };
  $('#verdict').innerHTML = `<div class="vcard ${verdict}${flag}">
    <div class="badge">${esc(verdict.replace('_', ' '))}</div>
    <div class="big">${esc(txt)}</div>
    <div class="stats"><span>MI <b>${mi.toFixed(3)}</b></span><span>p <b>${p.toFixed(3)}</b></span>
      <span>cognates <b>${d.n}</b> <small>(horizon ~${d.horizon})</small></span></div>
    <div class="note">${esc(d.note)}</div>${caveat}</div>`;
  renderContrast();
}

function renderContrast() {
  const grid = $('#contrast-grid'); grid.innerHTML = '';
  ORDER.forEach(id => {
    const d = PRESETS[id], su = SUMMARY[id] || {};
    const verdict = (su.p ?? 1) < 0.05 ? 'DETECTED' : 'FLOOR';
    const c = el('div', 'ccard clickable'); c.dataset.kind = d.kind;
    c.innerHTML = `<div class="cl">${esc(d.label)}</div>
      <div class="cv">MI ${(su.mi ?? 0).toFixed(2)} · p ${(su.p ?? 0).toFixed(3)} · N ${d.n}</div>
      <div class="cverd ${verdict}">${verdict}</div>`;
    c.onclick = () => select(id);
    grid.appendChild(c);
  });
  $('#contrast-banner')?.remove();
  const claim = ORDER.map(i => PRESETS[i]).find(p => p.kind === 'claim');
  const ctrl = ORDER.map(i => PRESETS[i]).find(p => p.kind === 'control');
  const conf = ORDER.map(i => PRESETS[i]).find(p => p.kind === 'confirmed');
  if (claim && ctrl && conf && SUMMARY[claim.id] && SUMMARY[ctrl.id] && SUMMARY[conf.id]) {
    const b = el('div', 'note', `<b>Read it honestly:</b> the claim
      (<b>${esc(claim.langA)}–${esc(claim.langB)}, MI ${SUMMARY[claim.id].mi.toFixed(2)}</b>) scores about the same as a family it is
      <b>not</b> related to (<b>${esc(ctrl.langB)}–${esc(ctrl.langA)}, MI ${SUMMARY[ctrl.id].mi.toFixed(2)}</b>) — both far below a
      confirmed pair (<b>MI ${SUMMARY[conf.id].mi.toFixed(2)}</b>). You cannot separate kinship from typological coincidence here. That's the wall.`);
    b.id = 'contrast-banner'; b.style.marginTop = '14px';
    grid.after(b);
  }
}

/* tiny tween for the MI number */
function tween(from, to, ms, step, alive) {
  return new Promise(res => { const t0 = performance.now();
    const f = now => { if (!alive()) return res(); const k = Math.min(1, (now - t0) / ms); step(from + (to - from) * k); k < 1 ? requestAnimationFrame(f) : res(); };
    requestAnimationFrame(f); });
}

boot();
