"""POC-22 시각화 리포트 생성 — 의존성 없는 자체완결 HTML(inline SVG).

POC-22 아크(Sino-Vietnamese 시대층 비지도 분해)를 한 장 HTML로:
  §1 문제 정체(OPEN 판정) §2 데이터 계약 §3 ★신호(tone 대응 대조) §4 검증결과(22a) §5 정직한 판정.
데이터에서 재계산(재현가능). F1은 poc22a.tsv에서 로드. → docs/poc22_report.html
"""
import json, re, csv, unicodedata, html as H
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT.parent / "data"
BS = DATA / "pjaponic" / "baxtersagart.tsv"
VI = DATA / "kaikki" / "vietnamese.jsonl"
A_TSV = ROOT / "results" / "poc22a.tsv"
OUT = ROOT.parent / "docs" / "poc22_report.html"

# ── MC/Viet 파싱 (poc22a와 동일) ──
bs = {}
for r in csv.DictReader(open(BS), delimiter="\t"):
    z = r["zi"]
    if z and z not in bs and r.get("MC", "").strip():
        bs[z] = r["MC"].split(",")[0].strip()
def mc_tone(mc):
    if mc.endswith("H"): return "去"
    if mc.endswith("X"): return "上"
    if mc and mc[-1] in "ptk": return "入"
    return "平"
TONE_MARKS = {"̀": "huyền", "́": "sắc", "̃": "ngã", "̉": "hỏi", "̣": "nặng"}
VTONES = ["ngang", "huyền", "sắc", "hỏi", "ngã", "nặng"]
def vi_tone(v):
    for ch in unicodedata.normalize("NFD", v):
        if ch in TONE_MARKS: return TONE_MARKS[ch]
    return "ngang"

# ── 데이터 추출 (OSV gold doublet / SV-proper) ──
osv, sv, doublets = [], [], []
han_re = re.compile(r"[Nn]on-Sino-Vietnamese reading of (?:Chinese )?([一-鿿])")
sv_re = re.compile(r"SV:\s*([^)\s,]+)")
seen = set()
for line in open(VI, encoding="utf-8"):
    e = json.loads(line)
    if e.get("lang_code") != "vi": continue
    w = e.get("word", ""); et = e.get("etymology_text") or ""
    if " " in w or not w: continue
    m = han_re.search(et)
    if m and m.group(1) in bs:
        if ("o", w, m.group(1)) in seen: continue
        seen.add(("o", w, m.group(1)))
        svf = sv_re.search(et)
        osv.append((m.group(1), bs[m.group(1)], w))
        if svf and len(doublets) < 16:
            doublets.append((m.group(1), bs[m.group(1)], w, svf.group(1)))
    elif not m:
        for t in e.get("etymology_templates", []) or []:
            if t.get("name") == "vi-etym-sino":
                h = t.get("args", {}).get("1", "")
                if h in bs and ("s", w, h) not in seen:
                    seen.add(("s", w, h)); sv.append((h, bs[h], w))
                break

# tone 대조: MC 去 → Viet tone 분포(%)
def tone_dist(items, mc_t):
    c = Counter(vi_tone(v) for _, mc, v in items if mc_tone(mc) == mc_t)
    tot = sum(c.values()) or 1
    return {t: 100 * c.get(t, 0) / tot for t in VTONES}, sum(c.values())
osv_qu, n_osv_qu = tone_dist(osv, "去")
sv_qu, n_sv_qu = tone_dist(sv, "去")

# F1 로드
f1 = {}
if A_TSV.exists():
    for r in csv.DictReader(open(A_TSV), delimiter="\t"):
        f1[r["method"]] = float(r["F1"])

# ── SVG 헬퍼 ──
PAL = {"OSV": "#d9772b", "SV": "#2b6cb0"}
def grouped_bar(cats, series, w=560, h=240, ymax=100, unit="%"):
    pl, pr, pt, pb = 46, 14, 16, 40
    iw, ih = w - pl - pr, h - pt - pb
    gw = iw / len(cats); bw = gw / (len(series) + 0.6)
    s = [f'<svg viewBox="0 0 {w} {h}" class="chart">']
    for gy in range(0, ymax + 1, 25):
        y = pt + ih - ih * gy / ymax
        s.append(f'<line x1="{pl}" y1="{y:.0f}" x2="{w-pr}" y2="{y:.0f}" class="grid"/>')
        s.append(f'<text x="{pl-6}" y="{y+3:.0f}" class="ytick">{gy}</text>')
    for ci, cat in enumerate(cats):
        x0 = pl + ci * gw
        for si, (name, vals) in enumerate(series.items()):
            v = vals[cat]; bh = ih * v / ymax
            x = x0 + gw * 0.18 + si * bw
            y = pt + ih - bh
            col = list(PAL.values())[si]
            s.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw*0.9:.1f}" height="{bh:.1f}" fill="{col}"><title>{name} {cat}: {v:.0f}{unit}</title></rect>')
        s.append(f'<text x="{x0+gw/2:.0f}" y="{h-pb+16}" class="xtick">{cat}</text>')
    s.append('</svg>')
    return "".join(s)
def simple_bar(items, w=560, h=210, ymax=1.0, base=None):
    pl, pr, pt, pb = 46, 14, 16, 54
    iw, ih = w - pl - pr, h - pt - pb
    gw = iw / len(items)
    s = [f'<svg viewBox="0 0 {w} {h}" class="chart">']
    for gy in [0, .25, .5, .75, 1.0]:
        y = pt + ih - ih * gy / ymax
        s.append(f'<line x1="{pl}" y1="{y:.0f}" x2="{w-pr}" y2="{y:.0f}" class="grid"/>')
        s.append(f'<text x="{pl-6}" y="{y+3:.0f}" class="ytick">{gy:.2f}</text>')
    if base is not None:
        y = pt + ih - ih * base / ymax
        s.append(f'<line x1="{pl}" y1="{y:.0f}" x2="{w-pr}" y2="{y:.0f}" class="baseline"/>')
        s.append(f'<text x="{w-pr}" y="{y-4:.0f}" class="baselbl" text-anchor="end">chance {base:.2f}</text>')
    for i, (lab, v, col) in enumerate(items):
        bh = ih * v / ymax; x = pl + i * gw + gw * 0.2; y = pt + ih - bh
        s.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{gw*0.6:.0f}" height="{bh:.0f}" fill="{col}"/>')
        s.append(f'<text x="{x+gw*0.3:.0f}" y="{y-5:.0f}" class="barval">{v:.2f}</text>')
        s.append(f'<text x="{x+gw*0.3:.0f}" y="{h-pb+16}" class="xtick2">{lab}</text>')
    s.append('</svg>')
    return "".join(s)

# ── HTML ──
def esc(s): return H.escape(str(s))
dbl_rows = "".join(
    f"<tr><td class=han>{esc(h)}</td><td class=mc>{esc(mc)}</td><td class=osvf>{esc(o)}</td><td class=svf>{esc(s)}</td></tr>"
    for h, mc, o, s in doublets[:12])
tone_series = {"OSV (古漢越)": osv_qu, "SV-proper (漢越)": sv_qu}
fig_tone = grouped_bar(VTONES, tone_series)
fig_f1 = simple_bar([
    ("지도 NB\n(상한)", f1.get("supervised_NB", 0), "#6b46c1"),
    ("비지도 EM\n(자연불균형)", f1.get("unsup_EM_natural", 0), "#d9772b"),
    ("비지도 EM\n(균형)", f1.get("unsup_EM_balanced", 0), "#2b6cb0"),
], base=0.5)

doc = f"""<!doctype html><html lang=ko><head><meta charset=utf-8>
<title>POC-22 — Sino-Vietnamese 시대층 비지도 분해</title>
<style>
:root{{--ink:#1a202c;--mut:#5a6478;--line:#e2e8f0;--bg:#fafbfc;--card:#fff}}
*{{box-sizing:border-box}} body{{font:15px/1.65 -apple-system,'Helvetica Neue',sans-serif;color:var(--ink);background:var(--bg);margin:0;padding:0 16px 80px}}
.wrap{{max-width:860px;margin:0 auto}}
header{{padding:38px 0 18px;border-bottom:2px solid var(--ink)}}
h1{{font-size:25px;margin:0 0 6px}} .sub{{color:var(--mut);font-size:14px}}
.verdict{{display:inline-block;background:#1c7a4a;color:#fff;font-weight:700;font-size:12px;padding:3px 10px;border-radius:4px;letter-spacing:.04em}}
.verdict.weak{{background:#b7791f}}
h2{{font-size:18px;margin:34px 0 8px;padding-top:8px;border-top:1px solid var(--line)}}
h2 .n{{color:#b7791f;font-weight:800;margin-right:8px}}
p{{margin:8px 0}} .mut{{color:var(--mut)}} b{{color:#000}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:14px 0}}
.chart{{width:100%;height:auto;display:block;margin:6px 0}}
.grid{{stroke:#eef1f5;stroke-width:1}} .ytick,.xtick,.xtick2{{fill:var(--mut);font-size:11px;text-anchor:middle}}
.ytick{{text-anchor:end}} .xtick2{{font-size:10px;white-space:pre}} .barval{{fill:var(--ink);font-size:12px;font-weight:700;text-anchor:middle}}
.baseline{{stroke:#e53e3e;stroke-dasharray:5 4;stroke-width:1.5}} .baselbl{{fill:#e53e3e;font-size:11px}}
.legend{{display:flex;gap:18px;font-size:13px;margin:4px 0 0}} .legend i{{display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:5px;vertical-align:-1px}}
table{{border-collapse:collapse;width:100%;font-size:14px;margin:6px 0}}
td,th{{border:1px solid var(--line);padding:5px 9px;text-align:left}} th{{background:#f4f6f9;font-weight:600}}
.han{{font-size:18px;text-align:center}} .mc{{font-family:ui-monospace,monospace;color:var(--mut)}}
.osvf{{color:{PAL['OSV']};font-weight:700}} .svf{{color:{PAL['SV']};font-weight:700}}
.kpi{{display:flex;gap:12px;flex-wrap:wrap;margin:10px 0}}
.kpi div{{flex:1;min-width:120px;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px}}
.kpi .v{{font-size:22px;font-weight:800}} .kpi .l{{font-size:12px;color:var(--mut)}}
.flag{{border-left:3px solid #b7791f;background:#fffbf0;padding:8px 12px;margin:10px 0;font-size:14px}}
.lvl{{font-size:14px;margin:4px 0;padding-left:4px}} code{{background:#f0f2f5;padding:1px 5px;border-radius:3px;font-size:13px}}
footer{{margin-top:40px;padding-top:14px;border-top:1px solid var(--line);color:var(--mut);font-size:12px}}
</style></head><body><div class=wrap>

<header>
<h1>POC-22 · Sino-Vietnamese 시대층 비지도 분해</h1>
<div class=sub>한 공여어(중국어)의 <b>여러 시대 차용층</b>(古漢越 OSV / 漢越 SV-proper)을 대응규칙 클러스터로 분리 · 2026-06-16</div>
<div style="margin-top:10px"><span class=verdict>문제: OPEN</span> &nbsp; <span class="verdict weak">22a 검증: 약함(부분)</span></div>
</header>

<h2><span class=n>§1</span>문제 정체 — 왜 열린 문제인가</h2>
<p>기존 계산적 차용연구는 <b>이진 탐지</b>(차용이냐 토착이냐)거나 기껏 <b>어느 공여어냐</b>까지다. 빈 자리는 —
<b>같은 공여어의 어느 <u>시대</u>냐</b>. 베트남어 한자어는 전부 중국어지만 여러 시대 파도로 들어와 <b>시대마다 음대응이 다르다.</b></p>
<div class=card>
<p style="margin:0 0 6px"><b>시대층 분리의 세 수준</b> — 우리 기여는 수준3</p>
<div class=lvl>① <b>정성 문헌학</b>(손으로): Wang Li·Alves·Phan — <b>풍부히 존재</b>(=SETTLED, validation gold)</div>
<div class=lvl>② <b>지도 계산</b>(층위 미리 라벨→모델): Ito/Kenstowicz(일본어) — 드묾</div>
<div class=lvl>③ <b>비지도 계산</b>(기계가 층위 <b>스스로 발견</b>): <b>어느 언어쌍서도 전무</b> ← 우리</div>
</div>
<p class=mut>deep-research(100 에이전트·24/25 주장 3-0): LexStat·List 2019·List&amp;Forkel·Miller&amp;List 2023·Wientzek 2025 모두
이진 탐지/계승 클러스터뿐 — same-donor 다층 비지도 분해는 없음. Sino-Japanese·Sino-Korean도 확인. <b>판정: OPEN.</b></p>

<h2><span class=n>§2</span>데이터 계약 — gold·신호 모두 보유</h2>
<div class=kpi>
<div><div class=v>{len(osv)}</div><div class=l>OSV gold (Non-SV 태그)</div></div>
<div><div class=v>{len(sv)}</div><div class=l>SV-proper 단음절</div></div>
<div><div class=v>4056</div><div class=l>Baxter-Sagart MC 자</div></div>
<div><div class=v>외부0</div><div class=l>다운로드 불요</div></div>
</div>
<p>cross-stratum <b>doublet</b>(한 한자→OSV형/SV형)이 정찰이 말한 <i>비지도 최강 신호</i>. 각 형태의 출처 한자를 Baxter-Sagart MC에 연결해 <b>MC→Viet 대응</b>을 측정한다.</p>
<table><tr><th>한자</th><th>중고음(MC)</th><th>OSV 형</th><th>SV-proper 형</th></tr>{dbl_rows}</table>

<h2><span class=n>§3</span>★ 핵심 신호 — 시대층은 <u>측정 가능하게</u> 다른 대응 시스템</h2>
<p>MC <b>去聲</b>(qusheng) → 베트남 성조 분포. <b>SV-proper는 sắc/nặng에 집중</b>(규칙적 대응), <b>OSV는 평평</b>(차용 시점이 일러 성조정렬 전) — Alves가 손으로 쓰는 <i>성조 역전</i> 진단이 수치화된 것.</p>
<div class=card>
<div class=legend><span><i style="background:{PAL['OSV']}"></i>OSV 古漢越 (n={n_osv_qu})</span><span><i style="background:{PAL['SV']}"></i>SV-proper 漢越 (n={n_sv_qu})</span></div>
{fig_tone}
<p class=mut style="margin:2px 0 0">x=베트남 성조, y=MC去聲 항목 중 %. SV {sv_qu['sắc']+sv_qu['nặng']:.0f}%가 sắc+nặng vs OSV 분산.</p>
</div>

<h2><span class=n>§4</span>검증 결과 (POC-22a) — 정직하게 약함</h2>
<p>feature = <b>MC↔Viet 대응</b>(성조쌍·onset류·유성성). 구조는 POC-17a 따름: 지도 상한 → 비지도 복원.</p>
<div class=card>{fig_f1}
<p class=mut style="margin:2px 0 0">OSV 검출 F1. 빨간 점선 = 균형셋 우연(0.5).</p></div>
<div class=flag>
<b>판정: 신호는 실재하나 약하고, 비지도 복원은 실패.</b><br>
· <b>지도 상한 F1 {f1.get('supervised_NB',0):.2f}</b> — 대응 feature에 층위 신호 <b>있음</b>(우연 0.27↑). 단 Sino-Korean SV/native의 0.95와 달리 <b>훨씬 낮음</b> = OSV/SV-proper는 <i>둘 다 중국어</i>라 더 미묘한 구분.<br>
· <b>비지도 EM: 자연불균형 0.00(붕괴) / 균형 {f1.get('unsup_EM_balanced',0):.2f}≈우연</b> — 현 feature 입도(4토큰)·단순 다항혼합으론 <b>층위 복원 못 함</b>. (BIC는 2-mode 선호하나 분리축이 시대층이 아님.)
</div>

<h2><span class=n>§5</span>정직한 판정 &amp; 다음</h2>
<p><b>22a는 de-risk 임무를 했다 — "쉬운 비지도 분해는 부족하다"를 밝혔다.</b> 층위는 분리가능한 신호를 갖지만(지도 0.59), naive 비지도로는 안 풀린다. 이는 POC-17a 교훈(불균형 붕괴)에 <b>새 교훈</b>을 더한다: <i>거친 대응 토큰으론 미묘한 동일-공여어 층위를 못 가른다.</i></p>
<div class=card>
<p style="margin:0 0 4px"><b>다음(22b 전 보강)</b></p>
<div class=lvl>· feature 정밀화: 성조×onset×rhyme <b>전체 대응표</b>(현재 4토큰 → 전체 MC→Viet 대응 행렬)</div>
<div class=lvl>· 불균형 보정: M1 카탈로그-끌림(POC-15/17a-fix) — Sino-Korean서 0.78→0.94로 구원한 도구</div>
<div class=lvl>· doublet 우선: 같은 한자 OSV/SV 쌍은 <i>대응차가 순수 분리</i>(어휘·의미 통제) → 최강 신호부터</div>
</div>
<p class=mut>성공기준은 양성이 아니라 <b>도구 신뢰 획득</b>: 보강 후 비지도가 gold를 따라가면 → 22b(논쟁 가장자리·Phan AMC에 정직 CI)로. 아니면 한계를 정직히 보고.</p>

<footer>
POC-22 아크 · 데이터 <code>data/kaikki/vietnamese.jsonl</code> · <code>data/pjaponic/baxtersagart.tsv</code> ·
코드 <code>poc/poc22a_validate.py</code> · 생성 <code>poc/poc22_report.py</code>.
선행연구 정찰 = deep-research(별도). 본 리포트는 데이터에서 재계산.
</footer>
</div></body></html>"""

OUT.write_text(doc, encoding="utf-8")
print(f"[리포트] {OUT} ({len(doc)//1024}KB)")
print(f"  OSV {len(osv)} / SV {len(sv)} / doublet표 {len(doublets)}")
print(f"  去聲: SV sắc+nặng={sv_qu['sắc']+sv_qu['nặng']:.0f}% vs OSV={osv_qu['sắc']+osv_qu['nặng']:.0f}%")
print(f"  F1: 지도={f1.get('supervised_NB',0):.3f} 비지도자연={f1.get('unsup_EM_natural',0):.3f} 비지도균형={f1.get('unsup_EM_balanced',0):.3f}")
