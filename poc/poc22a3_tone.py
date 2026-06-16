"""POC-22a'' (A안): 성조-우선 카탈로그-이탈 + 판정보류(abstention).

22a' 진단: 시대층 신호는 *성조*에 강·청정(doublet 성조 0.917, 去聲 0.81)하나 ~절반은 성조 동일(미진단)
+ 결합점수가 희석. → 성조-이탈만 쓰고, 성조로 안 보이는 건 *기권*(§4.1② calibrated abstention).

규칙(비지도): 각 MC류의 *규칙(최빈) 성조*를 비라벨 전체셋서 학습 → 단어 성조가 규칙서 벗어나면 OSV,
따르면 SV. 기권 = MC류가 평평(성조 비진단)한 단어. 산출: 전체 F1 + *확신부분* 정밀도·커버리지.
"""
import json, re, csv, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT.parent / "data"
OUT = ROOT / "results" / "poc22a3.tsv"
LOG = ROOT / "results" / "poc22a3.log"
logf = open(LOG, "w")
def log(*a):
    print(*a, flush=True); print(*a, file=logf, flush=True)

bs = {}
for r in csv.DictReader(open(DATA / "pjaponic" / "baxtersagart.tsv"), delimiter="\t"):
    z = r["zi"]
    if z and z not in bs and r.get("MC", "").strip():
        bs[z] = r["MC"].split(",")[0].strip()
def mct(mc):
    if mc.endswith("H"): return "qu"
    if mc.endswith("X"): return "shang"
    if mc and mc[-1] in "ptk": return "ru"
    return "ping"
def voiced(mc):
    return mc[:2] in ("dz", "zy", "dr", "gj") or (mc[:1] in "bdgz" and mc[:2] != "dz")
TM = {"̀": "huyen", "́": "sac", "̃": "nga", "̉": "hoi", "̣": "nang"}
def vt(v):
    for ch in unicodedata.normalize("NFD", v):
        if ch in TM: return TM[ch]
    return "ngang"

# 데이터
osv, sv = [], []
han = re.compile(r"[Nn]on-Sino-Vietnamese reading of (?:Chinese )?([一-鿿])")
seen = set()
for line in open(DATA / "kaikki" / "vietnamese.jsonl", encoding="utf-8"):
    e = json.loads(line)
    if e.get("lang_code") != "vi": continue
    w = e.get("word", ""); et = e.get("etymology_text") or ""
    if " " in w or not w: continue
    m = han.search(et)
    if m and m.group(1) in bs:
        if ("o", w, m.group(1)) in seen: continue
        seen.add(("o", w, m.group(1))); osv.append((bs[m.group(1)], w))
    elif not m:
        for t in e.get("etymology_templates", []) or []:
            if t.get("name") == "vi-etym-sino":
                h = t.get("args", {}).get("1", "")
                if h in bs and ("s", w, h) not in seen:
                    seen.add(("s", w, h)); sv.append((bs[h], w))
                break
ALL = [(mc, v, 1) for mc, v in osv] + [(mc, v, 0) for mc, v in sv]
log(f"OSV {len(osv)} / SV {len(sv)}")

# ── 비라벨 전체셋서 MC류별 성조 분포 → 규칙(최빈) 성조 + 첨예도 ──
dist = defaultdict(Counter)
for mc, v, _ in ALL:
    dist[(mct(mc), voiced(mc))][vt(v)] += 1
modal = {}; peak = {}
for k, c in dist.items():
    tot = sum(c.values()); top = c.most_common(1)[0]
    modal[k] = top[0]; peak[k] = top[1] / tot
log("\nMC류별 규칙(최빈)성조 + 첨예도:")
for k in sorted(dist, key=lambda k: -sum(dist[k].values())):
    log(f"  {k[0]:6s} voiced={k[1]!s:5s} → {modal[k]:6s} ({peak[k]:.2f})  n={sum(dist[k].values())}")

# ── 규칙: 성조가 최빈서 벗어나면 OSV(1), 따르면 SV(0) ──
def predict(mc, v):
    return 0 if vt(v) == modal[(mct(mc), voiced(mc))] else 1
def prf(items, mask=None):
    tp = fp = fn = tn = 0
    for i, (mc, v, y) in enumerate(items):
        if mask and not mask(mc): continue
        p = predict(mc, v)
        tp += p == 1 and y == 1; fp += p == 1 and y == 0
        fn += p == 0 and y == 1; tn += p == 0 and y == 0
    P = tp / (tp + fp) if tp + fp else 0; R = tp / (tp + fn) if tp + fn else 0
    F = 2 * P * R / (P + R) if P + R else 0
    return F, P, R, (tp + fp + fn + tn)

F, P, R, N = prf(ALL)
log(f"\n[전체] 성조-이탈 규칙: F1={F:.3f} P={P:.3f} R={R:.3f}  (22a naive EM 0.51, 22a' 0.45 대비)")

# ── abstention: 첨예(τ) MC류만 = 성조 진단가능 → 확신셋 ──
log("\n[판정보류] τ=MC류 첨예도 하한 (그 미만은 기권):")
OUT.write_text("setting\tF1\tP\tR\tcoverage\tnote\n")
with open(OUT, "a") as f:
    f.write(f"all\t{F:.4f}\t{P:.4f}\t{R:.4f}\t1.000\t성조이탈 전체\n")
    for tau in [0.5, 0.6, 0.7, 0.8]:
        peaked = lambda mc: peak[(mct(mc), voiced(mc))] >= tau
        Ff, Pf, Rf, Nf = prf(ALL, peaked)
        cov = Nf / len(ALL)
        log(f"  τ={tau}: F1={Ff:.3f} P={Pf:.3f} R={Rf:.3f}  커버리지={cov:.2f} ({Nf}/{len(ALL)})")
        f.write(f"abstain_tau{tau}\t{Ff:.4f}\t{Pf:.4f}\t{Rf:.4f}\t{cov:.4f}\t첨예MC류만\n")

log("\n" + "=" * 60)
log("판정: 성조-이탈 규칙이 22a/22a' 비지도(0.45~0.51) 넘으면 = 성조-우선이 옳음.")
log("  abstention으로 확신셋 정밀도↑하면 = '성조진단 가능 부분층은 비지도 분리, 나머지 기권'")
log("  = 정직한 부분-성공(§4.1② calibrated abstention). OSV층 이질성의 정량 초상.")
logf.close()
