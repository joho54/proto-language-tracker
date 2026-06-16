'use strict';
const $ = s => document.querySelector(s);
const el = (t, c, html) => { const e = document.createElement(t); if (c) e.className = c; if (html != null) e.innerHTML = html; return e; };
const esc = s => String(s).replace(/[&<>]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[m]));

const VERDICT_TXT = { DETECTED: 'Signal beats chance', FLOOR: 'Lost in the noise', BELOW_HORIZON: 'Too few cognates to tell' };
let PRESETS = {};   // id -> data
let ORDER = [];

async function boot() {
  const idx = await fetch('data/presets/index.json').then(r => r.json());
  ORDER = idx.presets.map(p => p.id);
  await Promise.all(idx.presets.map(async p => { PRESETS[p.id] = await fetch('data/presets/' + p.file).then(r => r.json()); }));
  const bar = $('#preset-buttons');
  idx.presets.forEach((p, i) => {
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
  $('#pairs-n').textContent = d.n; $('#pairs-shown').textContent = d.pairs.length;
  renderPairs(d); renderAlign(d); renderMatrix(d); renderMI(d); renderNull(d); renderVerdict(d);
  $('#stage').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderPairs(d) {
  const box = $('#pairs'); box.innerHTML = '';
  d.pairs.forEach(p => {
    const c = el('div', 'pair fade-in');
    c.innerHTML = `<div class="cc">${esc(p.concept)}</div>
      <div class="ww"><span class="wa">${esc(p.a_raw)}</span><span class="wb">${esc(p.b_raw)}</span></div>
      <div class="ww"><span class="ph">/${esc(p.a)}/</span><span class="ph">/${esc(p.b)}/</span></div>`;
    box.appendChild(c);
  });
}

function renderAlign(d) {
  const box = $('#align'); box.innerHTML = '';
  d.alignments.slice(0, 10).forEach(al => {
    const row = el('div', 'alnrow fade-in');
    const p = d.pairs[al.i];
    row.appendChild(el('span', 'cc', p ? esc(p.concept) : ''));
    const cells = el('div', 'cells');
    al.cells.forEach(([x, y]) => {
      const match = x !== null && x === y;
      const cell = el('div', 'cell' + (match ? ' match' : ''));
      cell.innerHTML = `<span class="top${x === null ? ' gap' : ''}">${x === null ? '·' : esc(x)}</span>` +
        `<span class="${y === null ? 'gap' : ''}">${y === null ? '·' : esc(y)}</span>`;
      cells.appendChild(cell);
    });
    row.appendChild(cells);
    box.appendChild(row);
  });
}

function renderMatrix(d) {
  const { rows, cols, counts } = d.matrix;
  const max = Math.max(1, ...counts.flat());
  const cw = 30, ch = 26, padL = 34, padT = 26;
  const W = padL + cols.length * cw + 8, H = padT + rows.length * ch + 6;
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="correspondence heatmap">`;
  cols.forEach((c, j) => s += `<text class="axt" x="${padL + j * cw + cw / 2}" y="${padT - 9}" text-anchor="middle">${esc(c)}</text>`);
  rows.forEach((r, i) => {
    s += `<text class="axt" x="${padL - 7}" y="${padT + i * ch + ch / 2 + 4}" text-anchor="end">${esc(r)}</text>`;
    cols.forEach((c, j) => {
      const v = counts[i][j], t = v / max;
      const fill = v === 0 ? '#f3f6f9' : `rgba(43,108,176,${0.12 + 0.88 * t})`;
      s += `<rect x="${padL + j * cw}" y="${padT + i * ch}" width="${cw - 2}" height="${ch - 2}" rx="3" fill="${fill}"><title>${esc(r)}→${esc(c)}: ${v}</title></rect>`;
      if (t > 0.18) s += `<text x="${padL + j * cw + cw / 2 - 1}" y="${padT + i * ch + ch / 2 + 4}" text-anchor="middle" font-size="11" fill="${t > 0.55 ? '#fff' : '#2b6cb0'}">${v}</text>`;
    });
  });
  $('#matrix').innerHTML = s + '</svg>';
}

function renderMI(d) {
  $('#mi').innerHTML = `<span class="val">${d.mi.toFixed(3)}</span>
    <span class="lab">bits of mutual information<br>(0 = sounds are independent; higher = systematic correspondence)</span>`;
}

let nullTimer = null;
function renderNull(d) {
  const vals = d.null.values, obs = d.mi;
  const lo = Math.min(...vals, obs), hi = Math.max(...vals, obs);
  const nb = 36, W = 560, H = 220, padL = 8, padR = 8, padT = 12, padB = 30;
  const iw = W - padL - padR, ih = H - padT - padB;
  const bins = new Array(nb).fill(0);
  const span = (hi - lo) || 1;
  vals.forEach(v => { let k = Math.floor((v - lo) / span * nb); if (k >= nb) k = nb - 1; if (k < 0) k = 0; bins[k]++; });
  const bmax = Math.max(...bins);
  const xObs = padL + (obs - lo) / span * iw;
  const bw = iw / nb;
  const draw = (reveal) => {
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="permutation null distribution">`;
    s += `<text class="axt" x="${padL}" y="${H - 8}" text-anchor="start">MI under random pairings →</text>`;
    bins.forEach((b, k) => {
      const h = ih * (b / bmax) * (k / nb <= reveal ? 1 : 0);
      s += `<rect x="${padL + k * bw}" y="${padT + ih - h}" width="${bw - 1}" height="${h}" rx="1.5" fill="#cbd5e1"/>`;
    });
    // observed line
    s += `<line x1="${xObs}" y1="${padT - 4}" x2="${xObs}" y2="${padT + ih}" stroke="#c5384b" stroke-width="2.5"/>`;
    s += `<text x="${Math.min(xObs, W - 90)}" y="${padT + 4}" fill="#c5384b" font-size="12" font-weight="700">real MI ${obs.toFixed(2)}</text>`;
    $('#null').innerHTML = s + '</svg>' +
      `<div class="meta" style="margin-top:6px">p = <b style="font-size:16px;color:${d.p < 0.05 ? '#1c7a4a' : '#475569'}">${d.p.toFixed(3)}</b>` +
      ` — ${Math.round(d.p * d.nperm)} of ${d.nperm.toLocaleString()} shuffles matched or beat the real value.</div>`;
  };
  if (nullTimer) clearInterval(nullTimer);
  let rev = 0; draw(0);
  nullTimer = setInterval(() => { rev += 0.06; draw(rev); if (rev >= 1) { clearInterval(nullTimer); } }, 28);
}

function renderVerdict(d) {
  const flag = d.kind === 'cherry' ? ' cherry-flag' : '';
  let caveat = '';
  if ((d.kind === 'claim' || d.kind === 'control') && Math.abs(d.p - 0.05) < 0.04)
    caveat = `<div class="note">⚠ p sits right on the 0.05 line — a coin-flip. Re-sample or shuffle more and the label can flip. This is exactly why a single "p &lt; 0.05" proves nothing here.</div>`;
  $('#verdict').innerHTML = `<div class="vcard ${d.verdict}${flag}">
    <div class="badge">${esc(d.verdict.replace('_', ' '))}</div>
    <div class="big">${esc(VERDICT_TXT[d.verdict] || '')}</div>
    <div class="stats"><span>MI <b>${d.mi.toFixed(3)}</b></span><span>p <b>${d.p.toFixed(3)}</b></span>
      <span>cognates <b>${d.n}</b> <small>(horizon ~${d.horizon})</small></span></div>
    <div class="note">${esc(d.note)}</div>${caveat}</div>`;
}

function renderContrast() {
  const grid = $('#contrast-grid'); grid.innerHTML = '';
  ORDER.forEach(id => {
    const d = PRESETS[id];
    const c = el('div', 'ccard clickable'); c.dataset.kind = d.kind;
    c.innerHTML = `<div class="cl">${esc(d.label)}</div>
      <div class="cv">MI ${d.mi.toFixed(2)} · p ${d.p.toFixed(3)} · N ${d.n}</div>
      <div class="cverd ${d.verdict}">${esc(d.verdict.replace('_', ' '))}</div>`;
    c.onclick = () => select(id);
    grid.appendChild(c);
  });
  // honest banner comparing claim vs control
  const claim = Object.values(PRESETS).find(p => p.kind === 'claim');
  const ctrl = Object.values(PRESETS).find(p => p.kind === 'control');
  const conf = Object.values(PRESETS).find(p => p.kind === 'confirmed');
  if (claim && ctrl && conf) {
    const banner = el('div', 'note', `<b>Read it honestly:</b> the claim
      (<b>${esc(claim.langA)}–${esc(claim.langB)}, MI ${claim.mi.toFixed(2)}</b>) scores essentially the same as a language it is
      <b>not</b> related to (<b>${esc(ctrl.langB)}–${esc(ctrl.langA)}, MI ${ctrl.mi.toFixed(2)}</b>) — both a world away from a
      confirmed pair (<b>MI ${conf.mi.toFixed(2)}</b>). Whatever the boundary p-values say, you cannot separate kinship from
      typological coincidence here. That's the wall.`);
    banner.style.marginTop = '14px';
    grid.after(banner);
  }
}

boot();
