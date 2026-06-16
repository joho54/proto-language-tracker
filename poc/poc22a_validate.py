"""POC-22a (validation): 비지도 대응-클러스터링이 OSV vs SV-proper를 분리하나?

★수준3 방법(same-donor 다층 비지도 분해)의 *신뢰성 검증* — 답 아는 데(Non-SV gold)서.
deep-research: 이 방법은 어느 언어쌍서도 전무. 여기선 베트남어 한자차용 OSV/SV-proper 2층을
gold(658 Non-SV doublet) 대조로 비지도 복원 가능한지 = 도구 신뢰 획득(그 위에서 22b discovery).

핵심 설계: feature = *MC↔Viet 대응*(MC성조×Viet성조, MC onset류×Viet onset, MC유성성).
  → 베트남어 형태 단독이 아니라 *시대층=대응규칙 차이*라는 주장을 직접 검증.
구조(POC-17a 따름): (1)지도 NB 상한 F1, (2)비지도 2-mode EM 복원(자연불균형 vs 균형)+MDL.
데이터: vietnamese.jsonl(Non-SV=OSV gold / vi-etym-sino 단음절=SV-proper), Baxter-Sagart MC.
"""
import json, re, csv, math, random, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

random.seed(22)
ROOT = Path(__file__).parent
DATA = ROOT.parent / "data"
BS = DATA / "pjaponic" / "baxtersagart.tsv"
VI = DATA / "kaikki" / "vietnamese.jsonl"
OUT = ROOT / "results" / "poc22a.tsv"
LOG = ROOT / "results" / "poc22a.log"

logf = open(LOG, "w")
def log(*a):
    print(*a, flush=True); print(*a, file=logf, flush=True)

# ── Baxter-Sagart MC ──
bs = {}
for r in csv.DictReader(open(BS), delimiter="\t"):
    z = r["zi"]
    if z and z not in bs and r.get("MC", "").strip():
        bs[z] = r["MC"].split(",")[0].strip()

# ── MC 파싱: 성조 + onset류 ──
def mc_tone(mc):
    if mc.endswith("H"): return "qu"      # 去
    if mc.endswith("X"): return "shang"   # 上
    if mc and mc[-1] in "ptk": return "ru"  # 入
    return "ping"                          # 平
MC_ONSETS = sorted([
    "tsrh","tsyh","dzy","tsy","dzr","tsr","tsh","trh","khw","ngw","sr","zr","sy","zy","ny",
    "ts","dz","ng","ph","th","tr","dr","nr","kh","gj","ph",
    "p","b","m","t","d","n","k","g","x","h","s","z","y","l","r","w","'"], key=len, reverse=True)
VOICED = {"b","d","g","dz","dzy","dzr","z","zy","zr","gj"}
NASAL = {"m","n","ng","ny","nr"}
def mc_onset(mc):
    s = mc.lstrip("'")  # 성문 파열 표기 제거 전 원형 보존? '는 성문음 — 유지 위해 따로
    for o in MC_ONSETS:
        if mc.startswith(o):
            return o
    return mc[:1]
def mc_onset_class(o):
    if o in VOICED: return "voiced_obstr"
    if o in NASAL: return "nasal"
    if o in {"l","r","y","w"}: return "sonorant"
    if o in {"s","sy","sr","tsh","tsrh","tsyh","th","ph","kh","trh"}: return "vless_asp/fric"
    if o in {"'","x","h"}: return "glottal"
    return "vless_stop"

# ── Vietnamese 파싱: 성조 + onset ──
TONE_MARKS = {"̀": "huyen", "́": "sac", "̃": "nga", "̉": "hoi", "̣": "nang"}
def vi_tone(v):
    d = unicodedata.normalize("NFD", v)
    for ch in d:
        if ch in TONE_MARKS: return TONE_MARKS[ch]
    return "ngang"
def strip_tone(v):
    d = unicodedata.normalize("NFD", v)
    return unicodedata.normalize("NFC", "".join(c for c in d if c not in TONE_MARKS))
VI_ONSETS = sorted(["ngh","ng","nh","ch","ph","th","tr","kh","gh","gi","qu",
                    "b","c","d","đ","g","h","k","l","m","n","p","q","r","s","t","v","x"],
                   key=len, reverse=True)
def vi_onset(v):
    s = strip_tone(v).lower()
    for o in VI_ONSETS:
        if s.startswith(o): return o
    return s[:1] if s else "∅"

# ── feature: MC↔Viet 대응 토큰 ──
def featurize(mc, viet):
    mo = mc_onset(mc); mt = mc_tone(mc); vt = vi_tone(viet); vo = vi_onset(viet)
    return [
        f"TONE:{mt}>{vt}",
        f"ONS:{mc_onset_class(mo)}>{vo}",
        f"MCVOICE:{mc_onset_class(mo)}",
        f"VTONE:{vt}",
    ]

# ── 데이터 추출 ──
osv, sv = [], []  # (hanzi, mc, viet)
han_re = re.compile(r"[Nn]on-Sino-Vietnamese reading of (?:Chinese )?([一-鿿])")
seen = set()
for line in open(VI, encoding="utf-8"):
    e = json.loads(line)
    if e.get("lang_code") != "vi": continue
    w = e.get("word", ""); et = e.get("etymology_text") or ""
    if " " in w or not w: continue
    m = han_re.search(et)
    if m and m.group(1) in bs:
        key = ("o", w, m.group(1))
        if key not in seen: seen.add(key); osv.append((m.group(1), bs[m.group(1)], w))
    elif not m:
        for t in e.get("etymology_templates", []) or []:
            if t.get("name") == "vi-etym-sino":
                h = t.get("args", {}).get("1", "")
                if h in bs:
                    key = ("s", w, h)
                    if key not in seen: seen.add(key); sv.append((h, bs[h], w))
                break
log(f"OSV(gold) {len(osv)} / SV-proper {len(sv)}  (불균형 {len(osv)/(len(osv)+len(sv)):.2f})")

# 데이터셋: (tokens, label)  label 1=OSV, 0=SV
def make(items, lab): return [(featurize(mc, v), lab) for _, mc, v in items]
DS = make(osv, 1) + make(sv, 0)
VOCAB = sorted({t for toks, _ in DS for t in toks})
vidx = {t: i for i, t in enumerate(VOCAB)}
def vec(toks):
    x = [0] * len(VOCAB)
    for t in toks:
        x[vidx[t]] += 1
    return x

# ── (1) 지도 NB 상한 (5-fold CV) ──
def nb_train(rows):
    cls = defaultdict(lambda: [1.0] * len(VOCAB)); cnt = Counter(); prior = Counter()
    for toks, y in rows:
        prior[y] += 1
        for t in toks: cls[y][vidx[t]] += 1; cnt[y] += 1
    logp = {}
    for y in (0, 1):
        tot = cnt[y] + len(VOCAB)
        logp[y] = [math.log(c / tot) for c in cls[y]]
    lpri = {y: math.log(prior[y] / len(rows)) for y in (0, 1)}
    return logp, lpri
def nb_pred(toks, logp, lpri):
    best, by = None, None
    for y in (0, 1):
        s = lpri[y] + sum(logp[y][vidx[t]] for t in toks)
        if best is None or s > best: best, by = s, y
    return by
rows = DS[:]; random.shuffle(rows)
folds = [rows[i::5] for i in range(5)]
tp = fp = fn = 0
for k in range(5):
    test = folds[k]; train = [r for j in range(5) if j != k for r in folds[j]]
    logp, lpri = nb_train(train)
    for toks, y in test:
        p = nb_pred(toks, logp, lpri)
        if p == 1 and y == 1: tp += 1
        elif p == 1 and y == 0: fp += 1
        elif p == 0 and y == 1: fn += 1
P = tp / (tp + fp) if tp + fp else 0; R = tp / (tp + fn) if tp + fn else 0
F1 = 2 * P * R / (P + R) if P + R else 0
log(f"\n[1] 지도 NB 상한 (OSV 검출, 5-fold): P={P:.3f} R={R:.3f} F1={F1:.3f}")

# ── (2) 비지도 2-mode 다항혼합 EM ──
def em(rows, K=2, iters=40):
    X = [vec(t) for t, _ in rows]; N = len(X); V = len(VOCAB)
    rng = random.Random(22)
    # 초기화: 랜덤 responsibility
    resp = [[rng.random() for _ in range(K)] for _ in range(N)]
    for r in resp:
        s = sum(r);
        for k in range(K): r[k] /= s
    ll_old = None
    for _ in range(iters):
        # M: pi, phi
        pi = [sum(resp[n][k] for n in range(N)) / N for k in range(K)]
        phi = [[1.0] * V for _ in range(K)]
        for n in range(N):
            for k in range(K):
                rk = resp[n][k]
                if rk < 1e-9: continue
                for i, c in enumerate(X[n]):
                    if c: phi[k][i] += rk * c
        for k in range(K):
            tot = sum(phi[k])
            phi[k] = [math.log(p / tot) for p in phi[k]]
        # E
        ll = 0.0
        for n in range(N):
            lps = []
            for k in range(K):
                lp = math.log(pi[k] + 1e-12) + sum(c * phi[k][i] for i, c in enumerate(X[n]) if c)
                lps.append(lp)
            m = max(lps); den = m + math.log(sum(math.exp(l - m) for l in lps))
            resp[n] = [math.exp(l - den) for l in lps]; ll += den
        if ll_old is not None and abs(ll - ll_old) < 1e-4: break
        ll_old = ll
    assign = [max(range(K), key=lambda k: resp[n][k]) for n in range(N)]
    return assign, ll, pi

def score_clusters(rows, assign):
    # 클러스터→라벨 매핑(다수결), F1(OSV)
    K = max(assign) + 1
    cl2lab = {}
    for k in range(K):
        labs = [rows[n][1] for n in range(len(rows)) if assign[n] == k]
        cl2lab[k] = 1 if labs.count(1) > labs.count(0) else 0
    tp = fp = fn = 0
    for n, (_, y) in enumerate(rows):
        p = cl2lab[assign[n]]
        if p == 1 and y == 1: tp += 1
        elif p == 1 and y == 0: fp += 1
        elif p == 0 and y == 1: fn += 1
    P = tp / (tp + fp) if tp + fp else 0; R = tp / (tp + fn) if tp + fn else 0
    return (2 * P * R / (P + R) if P + R else 0), P, R

# 자연 불균형
asg, ll2, pi = em(DS)
f1n, Pn, Rn = score_clusters(DS, asg)
# 1-mode loglik (MDL)
_, ll1, _ = em(DS, K=1)
def bic(ll, k_params, N): return -2 * ll + k_params * math.log(N)
V = len(VOCAB); N = len(DS)
bic1 = bic(ll1, V, N); bic2 = bic(ll2, 2 * V + 1, N)
log(f"\n[2a] 비지도 2-mode EM (자연 불균형): F1={f1n:.3f} (P={Pn:.3f} R={Rn:.3f}), pi={[round(p,2) for p in pi]}")
log(f"     MDL/BIC: 1-mode={bic1:.0f}  2-mode={bic2:.0f}  → {'2-mode 채택✓' if bic2<bic1 else '1-mode(분리 미채택)'}")

# 균형 subsample (POC-17a 교훈: 불균형서 붕괴 가능)
random.shuffle(sv)
DSB = make(osv, 1) + make(sv[:len(osv)], 0); random.shuffle(DSB)
asgb, _, pib = em(DSB)
f1b, Pb, Rb = score_clusters(DSB, asgb)
log(f"[2b] 비지도 2-mode EM (균형 subsample): F1={f1b:.3f} (P={Pb:.3f} R={Rb:.3f})")

# ── 산출 ──
OUT.write_text("method\tF1\tP\tR\tnote\n")
with open(OUT, "a") as f:
    f.write(f"supervised_NB\t{F1:.4f}\t{P:.4f}\t{R:.4f}\t상한(대응feature)\n")
    f.write(f"unsup_EM_natural\t{f1n:.4f}\t{Pn:.4f}\t{Rn:.4f}\t불균형{len(osv)}/{len(sv)}\n")
    f.write(f"unsup_EM_balanced\t{f1b:.4f}\t{Pb:.4f}\t{Rb:.4f}\t균형\n")

log("\n" + "=" * 60)
log("판정 기준: 지도 高F1=대응신호로 층위 분리가능✓. 비지도 복원이 gold 따라가면")
log("  = 수준3 방법(비지도 다층분해)이 *작동* → 22b discovery 신뢰 획득.")
log("  (POC-17a처럼 자연불균형서 EM 약하고 균형서 살아나면 = 불균형보정 필요 교훈 재확인.)")
logf.close()
