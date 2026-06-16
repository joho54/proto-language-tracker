"""POC-22a' (보강): 카탈로그-이탈 + 전체 대응 조건모델 + doublet 쌍대조.

22a 실패 3원인 정조준: (1)거친 feature → 전체 대응셀 조건모델, (2)불균형 붕괴 → 빈도 아닌
*규칙대응 이탈도*로 가름(M1, POC-17a-fix 기제), (3)어휘·의미 노이즈 → doublet 쌍대조(통제).

방법: 비라벨 전체셋에서 P(Viet feature | MC feature) 추정(SV가 다수라 ≈규칙 SV 대응).
  score(단어) = 그 단어의 MC→Viet 대응이 규칙패턴에 얼마나 맞나(로그우도). OSV=소수·불규칙=저score.
  - doublet 쌍대조: 같은 한자 OSV형 vs SV형 score 비교(의미·출처 통제된 순수 신호).
  - 비지도 분리: score 1D에 2-mode GMM-EM → gold 복원 F1. + 지도 최적임계 F1(상한).
"""
import json, re, csv, math, unicodedata, random
from collections import Counter, defaultdict
from pathlib import Path

random.seed(22)
ROOT = Path(__file__).parent
DATA = ROOT.parent / "data"
BS = DATA / "pjaponic" / "baxtersagart.tsv"
VI = DATA / "kaikki" / "vietnamese.jsonl"
OUT = ROOT / "results" / "poc22a2.tsv"
LOG = ROOT / "results" / "poc22a2.log"
logf = open(LOG, "w")
def log(*a):
    print(*a, flush=True); print(*a, file=logf, flush=True)

bs = {}
for r in csv.DictReader(open(BS), delimiter="\t"):
    z = r["zi"]
    if z and z not in bs and r.get("MC", "").strip():
        bs[z] = r["MC"].split(",")[0].strip()

# ── MC features ──
def mc_tone(mc):
    if mc.endswith("H"): return "qu"
    if mc.endswith("X"): return "shang"
    if mc and mc[-1] in "ptk": return "ru"
    return "ping"
MC_ONSETS = sorted(["tsrh","tsyh","dzy","tsy","dzr","tsr","tsh","trh","khw","ngw","sr","zr","sy","zy","ny",
    "ts","dz","ng","ph","th","tr","dr","nr","kh","gj","p","b","m","t","d","n","k","g","x","h","s","z","y","l","r","w","'"], key=len, reverse=True)
VOICED = {"b","d","g","dz","dzy","dzr","z","zy","zr","gj"}
NASAL = {"m","n","ng","ny","nr"}
def mc_onset(mc):
    for o in MC_ONSETS:
        if mc.startswith(o): return o
    return mc[:1]
def mc_oclass(o):
    if o in VOICED: return "vd"
    if o in NASAL: return "nas"
    if o in {"l","r","y","w","'"}: return "son"
    if o in {"s","sy","sr","z","zy","zr"}: return "fric"
    if o and o[-1] == "h": return "asp"
    return "vls"
def mc_coda(mc):
    m = mc.rstrip("HX")
    if m and m[-1] in "ptk": return "stop"
    if m.endswith("ng"): return "ng"
    if m and m[-1] in "mn": return "nas"
    return "open"

# ── Viet features ──
TM = {"̀": "huyen", "́": "sac", "̃": "nga", "̉": "hoi", "̣": "nang"}
def vi_tone(v):
    for ch in unicodedata.normalize("NFD", v):
        if ch in TM: return TM[ch]
    return "ngang"
def vi_strip(v):
    return unicodedata.normalize("NFC", "".join(c for c in unicodedata.normalize("NFD", v) if c not in TM)).lower()
VI_ON = sorted(["ngh","ng","nh","ch","ph","th","tr","kh","gh","gi","qu","b","c","d","đ","g","h","k","l","m","n","p","q","r","s","t","v","x"], key=len, reverse=True)
def vi_onset(v):
    s = vi_strip(v)
    for o in VI_ON:
        if s.startswith(o): return o
    return s[:1] if s else "0"
def vi_coda(v):
    s = vi_strip(v)
    for c in ["ch","nh","ng","p","t","c","m","n"]:
        if s.endswith(c): return "stop" if c in ("p","t","c","ch") else ("ng" if c in ("ng","nh") else "nas")
    return "open"

def feats(mc, v):
    o = mc_onset(mc)
    return dict(mt=mc_tone(mc), mv=mc_oclass(o), mo=mc_oclass(o), mc=mc_coda(mc),
               vt=vi_tone(v), vo=vi_onset(v), vc=vi_coda(v))

# ── 데이터 ──
osv, sv, dbl = [], [], []
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
        osv.append((m.group(1), bs[m.group(1)], w))
        sm = sv_re.search(et)
        if sm: dbl.append((m.group(1), bs[m.group(1)], w, sm.group(1)))
    elif not m:
        for t in e.get("etymology_templates", []) or []:
            if t.get("name") == "vi-etym-sino":
                h = t.get("args", {}).get("1", "")
                if h in bs and ("s", w, h) not in seen:
                    seen.add(("s", w, h)); sv.append((h, bs[h], w))
                break
ALL = [(mc, v, 1) for _, mc, v in osv] + [(mc, v, 0) for _, mc, v in sv]
log(f"OSV {len(osv)} / SV {len(sv)} / doublet쌍 {len(dbl)}")

# ── 규칙 대응 조건모델 (비라벨 전체셋) ──
def build_model(items):
    T = defaultdict(Counter); O = defaultdict(Counter); C = defaultdict(Counter)
    for mc, v, _ in items:
        f = feats(mc, v)
        T[(f["mt"], f["mv"])][f["vt"]] += 1
        O[f["mo"]][f["vo"]] += 1
        C[f["mc"]][f["vc"]] += 1
    return T, O, C
def logp(dist, key, val, V):
    c = dist[key]; tot = sum(c.values())
    return math.log((c.get(val, 0) + 0.5) / (tot + 0.5 * V))
def score(mc, v, M):
    T, O, C = M; f = feats(mc, v)
    return (logp(T, (f["mt"], f["mv"]), f["vt"], 6)
            + logp(O, f["mo"], f["vo"], 30)
            + logp(C, f["mc"], f["vc"], 4))
M = build_model(ALL)
scores = [(score(mc, v, M), y) for (mc, v, y) in ALL]

# ── ③ doublet 쌍대조 (의미·출처 통제 순수 신호) ──
ok = 0; tot = 0
for h, mc, osvf, svf in dbl:
    so = score(mc, osvf, M); ss = score(mc, svf, M)
    tot += 1; ok += (so < ss)
log(f"\n[③ doublet 쌍대조] OSV score < SV score: {ok}/{tot} = {ok/tot:.3f}  (0.5=무신호, 1.0=완전분리)")

# ── 지도 최적임계 F1 (상한) ──
ss = sorted(scores)
best = (0, None)
for i in range(len(ss)):
    thr = ss[i][0]
    tp = sum(1 for s, y in scores if s <= thr and y == 1)
    fp = sum(1 for s, y in scores if s <= thr and y == 0)
    fn = sum(1 for s, y in scores if s > thr and y == 1)
    P = tp / (tp + fp) if tp + fp else 0; R = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * P * R / (P + R) if P + R else 0
    if f1 > best[0]: best = (f1, thr)
log(f"[지도 최적임계 상한] F1={best[0]:.3f} (score≤{best[1]:.2f}=OSV)")

# ── 비지도 1D 2-mode GMM-EM ──
def gmm1d(xs, iters=80):
    xs = list(xs); n = len(xs)
    mu = [min(xs), max(xs)]; var = [1.0, 1.0]; pi = [0.5, 0.5]
    def N(x, m, v): return math.exp(-(x - m) ** 2 / (2 * v)) / math.sqrt(2 * math.pi * v) + 1e-300
    for _ in range(iters):
        r = []
        for x in xs:
            a = pi[0] * N(x, mu[0], var[0]); b = pi[1] * N(x, mu[1], var[1])
            r.append((a / (a + b), b / (a + b)))
        for k in range(2):
            w = sum(rr[k] for rr in r)
            mu[k] = sum(rr[k] * x for rr, x in zip(r, xs)) / w
            var[k] = max(1e-3, sum(rr[k] * (x - mu[k]) ** 2 for rr, x in zip(r, xs)) / w)
            pi[k] = w / n
    low = 0 if mu[0] < mu[1] else 1   # 저score 모드 = OSV 가설
    asg = [(0 if (pi[0]*N(x,mu[0],var[0])) > (pi[1]*N(x,mu[1],var[1])) else 1) for x in xs]
    return [1 if a == low else 0 for a in asg]  # 1=OSV pred
def gN(x, m, v): return math.exp(-(x - m) ** 2 / (2 * v)) / math.sqrt(2 * math.pi * v)
pred = gmm1d([s for s, _ in scores])
tp = sum(1 for (s, y), p in zip(scores, pred) if p == 1 and y == 1)
fp = sum(1 for (s, y), p in zip(scores, pred) if p == 1 and y == 0)
fn = sum(1 for (s, y), p in zip(scores, pred) if p == 0 and y == 1)
P = tp / (tp + fp) if tp + fp else 0; R = tp / (tp + fn) if tp + fn else 0
f1u = 2 * P * R / (P + R) if P + R else 0
log(f"[비지도 2-mode GMM] F1={f1u:.3f} (P={P:.3f} R={R:.3f})")

OUT.write_text("test\tvalue\tnote\n")
with open(OUT, "a") as f:
    f.write(f"doublet_pair\t{ok/tot:.4f}\tOSV<SV score 비율(0.5=무신호)\n")
    f.write(f"supervised_thr_F1\t{best[0]:.4f}\t최적임계 상한\n")
    f.write(f"unsup_gmm_F1\t{f1u:.4f}\t1D 2-mode 카탈로그이탈\n")

log("\n" + "=" * 60)
log("판정: ③ doublet 쌍대조가 핵심 — 0.5면 신호 자체 없음(층위 분리 원리적 불가),")
log("  0.8+면 신호 실재(어휘통제). 비지도 GMM이 gold 따라가면 카탈로그-이탈로 복원 성공.")
log("  22a(naive EM F1 0.51) 대비 개선 여부 = 보강 효과.")
logf.close()
