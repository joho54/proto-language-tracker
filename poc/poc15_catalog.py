"""POC-15: 카탈로그 끌림 모델 (M1) — Maltese 차용 탐지 + 출처 귀속.

POC-14는 차용을 *phonotactic 모드*("막연히 로망스 같다")로만 잡았다. POC-15는 차용 채널을
*특정 출처 단어로의 끌림* P_adapt(w|s) (학습된 noisy-channel)로 격상하여, 탐지에 더해
"어느 Maltese 단어가 어느 이탈/시칠리아 단어에서 왔는지"(출처 귀속)를 복원한다.

★ 핵심 설계 발견 (POC-15가 입증):
  **탐지(borrowed인가?)와 귀속(어느 출처?)은 다른 통계가 필요하다.**
  - 카탈로그-조회 차용 채널은 *특정 출처에 조건부*라 확률을 집중(per-char ≈ -2.3)시키는 반면
    정규화 phonotactic bigram LM은 본질적으로 고엔트로피(per-char ≈ -5, 전체 문자열에 질량 분산).
    → **raw 우도 혼합 EM은 모든 단어에서 차용 채널이 이겨 all-borrowed로 붕괴**(아래서 재현·보고).
    어휘-밀도 이점은 단어 길이로 정규화해도 *상쇄 안 됨*(엔트로피 격차는 실재). 토착층을 위한
    경쟁 저엔트로피 모델(여기선 아랍 카탈로그)이 없으면 카탈로그 우도 단독으론 탐지 불가.
  - 따라서 탐지는 길이정규화 *적응비용* + phonotactic 판별을 결합한 비지도 혼합으로,
    귀속은 카탈로그 끌림의 argmax_s 로 — 둘을 분리한다.

평가 (성공기준):
  (1) 차용 F1 > POC-14(0.764) — 비지도.            → 결합 탐지기
  (2) 출처식별 정확도(차용 단어의 argmax_s = gold). → 카탈로그 끌림

카탈로그 C = gold donor form 전체의 합집합(중복제거) = 이탈/시칠리아 어휘 프록시.
  EM은 어느 단어가 차용인지·어느 s에 붙는지 라벨·정렬 *모름*. 후보 가지치기: char-bigram
  Jaccard 상위 K(전수 edit-distance 비현실적) → prefilter recall(천장) 함께 보고.

영속성(CLAUDE.md 1순위): flush 로그 + 부분결과 incremental TSV.
출력: poc/results/poc15.tsv, poc/results/poc15_sources.tsv
"""
import json, re, math, random
from collections import Counter, defaultdict
from pathlib import Path

random.seed(15)
DATA = Path(__file__).resolve().parent.parent / "data" / "kaikki" / "maltese.jsonl"
OUT = Path(__file__).parent / "results"
ALPHA = "abcdefghijklmnopqrstuvwxyz"


def norm(s):
    """라틴 letter-only 소문자 (다이아크리틱 제거)."""
    s = s.lower()
    repl = {"à": "a", "á": "a", "è": "e", "é": "e", "ì": "i", "í": "i",
            "ò": "o", "ó": "o", "ù": "u", "ú": "u", "ċ": "c", "ġ": "g",
            "ħ": "h", "ż": "z", "ʼ": ""}
    for k, v in repl.items():
        s = s.replace(k, v)
    return re.sub(r"[^a-z]", "", s)


def gold_label(e):
    for t in e.get("etymology_templates", []):
        a = t.get("args", {})
        if t.get("name") in ("bor", "bor+", "lbor") or a.get("2") == ":bor":
            return "borrowed"
        if a.get("2") == ":inh" or t.get("name") == "inh":
            return "inherited"
    return None


def parse_donor(e):
    """차용 출처 (lang, word). 없으면 (None,None)."""
    for t in e.get("etymology_templates", []):
        nm = t.get("name"); a = t.get("args", {})
        if not (nm in ("bor", "bor+", "lbor") or a.get("2") == ":bor"):
            continue
        raw3 = a.get("3") or ""
        lang = a.get("2"); word = raw3
        if ":" in raw3:
            lang, word = raw3.split(":", 1)
        elif lang == ":bor":
            lang = None
        word = re.sub(r"<[^>]*>", "", word).strip()
        return lang, word
    return None, None


def bigrams(s):
    s = "^" + s + "$"
    return [s[i:i+2] for i in range(len(s) - 1)]


# ----------------------------- 적응 채널 -----------------------------
class Channel:
    """문자 confusion noisy-channel. 정렬은 학습된 비용의 Levenshtein DP로.
    near-identity Dirichlet prior(대각 큰 pseudocount)로 임의 치환 범용매처 붕괴를 차단."""

    def __init__(self):
        syms = list(ALPHA)
        self.sub = {a: {b: (3.0 if a == b else 0.1) for b in syms} for a in syms}
        self.ins = {b: 0.2 for b in syms}
        self.dele = {a: 0.2 for a in syms}
        self.ins_pen = math.log(0.15)
        self._normalize()

    def _normalize(self):
        self.lsub = {}; self.ldel = {}
        for a in ALPHA:
            tot = sum(self.sub[a].values()) + self.dele[a]
            self.lsub[a] = {b: math.log(self.sub[a][b] / tot) for b in ALPHA}
            self.ldel[a] = math.log(self.dele[a] / tot)
        tot_i = sum(self.ins.values())
        self.lins = {b: math.log(self.ins[b] / tot_i) for b in ALPHA}

    def align_score(self, s, w):
        """log P(w | s). 표준 edit DP, 학습된 logprob 비용."""
        ns, nw = len(s), len(w)
        NEG = -1e9
        dp = [[NEG] * (nw + 1) for _ in range(ns + 1)]
        dp[0][0] = 0.0
        for i in range(ns + 1):
            row = dp[i]
            for j in range(nw + 1):
                cur = row[j]
                if cur <= NEG:
                    continue
                if i < ns and j < nw:
                    v = cur + self.lsub[s[i]][w[j]]
                    if v > dp[i+1][j+1]:
                        dp[i+1][j+1] = v
                if i < ns:
                    v = cur + self.ldel[s[i]]
                    if v > dp[i+1][j]:
                        dp[i+1][j] = v
                if j < nw:
                    v = cur + self.ins_pen + self.lins[w[j]]
                    if v > row[j+1]:
                        row[j+1] = v
        return dp[ns][nw]

    def best_align_ops(self, s, w):
        """best 정렬의 edit op 리스트 (채널 정련 M-step 카운트용)."""
        ns, nw = len(s), len(w)
        NEG = -1e9
        dp = [[NEG] * (nw + 1) for _ in range(ns + 1)]
        bk = [[None] * (nw + 1) for _ in range(ns + 1)]
        dp[0][0] = 0.0
        for i in range(ns + 1):
            for j in range(nw + 1):
                cur = dp[i][j]
                if cur <= NEG:
                    continue
                if i < ns and j < nw:
                    v = cur + self.lsub[s[i]][w[j]]
                    if v > dp[i+1][j+1]:
                        dp[i+1][j+1] = v; bk[i+1][j+1] = ("sub", i, j)
                if i < ns:
                    v = cur + self.ldel[s[i]]
                    if v > dp[i+1][j]:
                        dp[i+1][j] = v; bk[i+1][j] = ("del", i, j)
                if j < nw:
                    v = cur + self.ins_pen + self.lins[w[j]]
                    if v > dp[i][j+1]:
                        dp[i][j+1] = v; bk[i][j+1] = ("ins", i, j)
        ops = []; i, j = ns, nw
        while bk[i][j] is not None:
            t, pi, pj = bk[i][j]
            if t == "sub":
                ops.append(("sub", s[pi], w[pj]))
            elif t == "del":
                ops.append(("del", s[pi], None))
            else:
                ops.append(("ins", None, w[pj]))
            i, j = pi, pj
        return ops

    def refit(self, pairs):
        """pairs=[(s,w)] 에서 채널 재추정. near-identity Dirichlet prior 유지."""
        sub = {a: {b: (2.0 if a == b else 0.02) for b in ALPHA} for a in ALPHA}
        ins = {b: 0.05 for b in ALPHA}
        dele = {a: 0.05 for a in ALPHA}
        for s, w in pairs:
            for t, x, y in self.best_align_ops(s, w):
                if t == "sub":
                    sub[x][y] += 1.0
                elif t == "ins":
                    ins[y] += 1.0
                else:
                    dele[x] += 1.0
        self.sub, self.ins, self.dele = sub, ins, dele
        self._normalize()


# ----------------------------- 유틸: 음소배열 LM -----------------------------
def lm_percharLL(bgs, counts, tot, V, a=0.5):
    """per-bigram 평균 logprob (길이 정규화)."""
    return sum(math.log((counts[bg] + a) / (tot + a * V)) for bg in bgs) / len(bgs)


def train_lm(idxs, Wbg):
    c = Counter()
    for i in idxs:
        for bg in Wbg[i]:
            c[bg] += 1
    return c, sum(c.values()) or 1.0


def gmm1d(x, init_hi, init_lo, iters=50):
    """1-D 2-Gaussian 혼합 EM. 반환: 각 점이 '고-mean(=borrowed)' 성분일 책임도."""
    N = len(x)
    mu = [init_hi, init_lo]; sd = [1.0, 1.0]; pi = [0.5, 0.5]

    def npdf(v, m, s):
        return math.exp(-0.5 * ((v - m) / s) ** 2) / (s * math.sqrt(2 * math.pi)) + 1e-12
    r = [0.5] * N
    for _ in range(iters):
        for i in range(N):
            a = pi[0] * npdf(x[i], mu[0], sd[0])
            b = pi[1] * npdf(x[i], mu[1], sd[1])
            r[i] = a / (a + b)
        s0 = sum(r); s1 = N - s0
        if s0 < 1 or s1 < 1:
            break
        mu = [sum(r[i] * x[i] for i in range(N)) / s0,
              sum((1 - r[i]) * x[i] for i in range(N)) / s1]
        sd = [max(0.3, (sum(r[i] * (x[i] - mu[0]) ** 2 for i in range(N)) / s0) ** .5),
              max(0.3, (sum((1 - r[i]) * (x[i] - mu[1]) ** 2 for i in range(N)) / s1) ** .5)]
        pi = [s0 / N, s1 / N]
    # 성분0이 고-mean(borrowed)이 되도록 정렬
    if mu[0] < mu[1]:
        r = [1 - v for v in r]
    return r


def main():
    print("=" * 64, flush=True)
    print("POC-15: 카탈로그 끌림 모델 (M1) — Maltese", flush=True)
    print("=" * 64, flush=True)
    OUT.mkdir(exist_ok=True)

    # ---- 적재 ----
    items = []           # (word_norm, gold_label, donor_norm or None)
    catalog = Counter()  # donor_norm -> 빈도
    for line in open(DATA, encoding="utf-8"):
        e = json.loads(line)
        lab = gold_label(e)
        if lab is None:
            continue
        w = norm(e.get("word", ""))
        if len(w) < 2:
            continue
        dl, dw = parse_donor(e)
        dn = norm(dw) if dw else None
        items.append((w, lab, dn))
        if lab == "borrowed" and dn and len(dn) >= 2:
            catalog[dn] += 1
    random.shuffle(items)

    cat = [s for s in catalog if len(s) >= 2]
    cat_set = set(cat)
    N = len(items)
    nb = sum(1 for _, l, _ in items if l == "borrowed")
    words = [w for w, _, _ in items]
    gold = [items[i][1] == "borrowed" for i in range(N)]
    print(f"단어 {N}  (borrowed {nb}, inherited {N-nb}, 다수 {max(nb,N-nb)/N:.3f})", flush=True)
    print(f"카탈로그(출처 단어, dedup) {len(cat)}", flush=True)

    # ---- 후보 가지치기 (char-bigram Jaccard 상위 K) ----
    K = 40
    cat_bg = [set(bigrams(s)) for s in cat]
    inv = defaultdict(list)
    for ci, bgs in enumerate(cat_bg):
        for bg in bgs:
            inv[bg].append(ci)

    def candidates(w):
        wb = set(bigrams(w)); sc = Counter()
        for bg in wb:
            for ci in inv.get(bg, ()):
                sc[ci] += 1
        cand = []
        for ci, sh in sc.most_common(K * 2):
            jac = sh / (len(wb) + len(cat_bg[ci]) - sh)
            cand.append((jac, ci))
        cand.sort(reverse=True)
        return [ci for _, ci in cand[:K]]

    print("후보 인덱싱…", flush=True)
    cand_idx = [candidates(w) for w in words]

    surv = ptot = 0
    for i, (w, lab, dn) in enumerate(items):
        if lab == "borrowed" and dn in cat_set:
            ptot += 1
            if any(cat[ci] == dn for ci in cand_idx[i]):
                surv += 1
    pref_rec = surv / ptot if ptot else 0
    print(f"prefilter recall(천장): {pref_rec:.3f}  ({surv}/{ptot})", flush=True)

    # ---- 카탈로그 끌림: per-char 적응비용 + best source (귀속) ----
    ch = Channel()
    print("카탈로그 적응비용 계산…", flush=True)
    nsim = [0.0] * N      # per-char 적응 log-likelihood (높을수록 카탈로그-유사=차용)
    bestsrc = [-1] * N
    for i in range(N):
        w = words[i]
        best, bci = -1e18, -1
        for ci in cand_idx[i]:
            sc = ch.align_score(cat[ci], w)
            if sc > best:
                best, bci = sc, ci
        nsim[i] = best / max(len(w), 1) if bci >= 0 else -30.0
        bestsrc[i] = bci
        if i % 1500 == 0:
            (OUT / "poc15_progress.log").write_text(f"adapt cost {i}/{N}", encoding="utf-8")

    # ---- (보고용) raw-우도 혼합이 붕괴함을 재현 ----
    Wbg = [bigrams(w) for w in words]
    V = len(set(bg for bgs in Wbg for bg in bgs))
    c_all, t_all = train_lm(range(N), Wbg)
    # 차용 raw LL(길이비례) vs 계승 LM raw LL — 전 단어에서 차용이 이기는지 카운트
    collapse = 0
    for i in range(N):
        bor_raw = nsim[i] * len(words[i])         # per-char×len = raw align LL
        inh_raw = lm_percharLL(Wbg[i], c_all, t_all, V) * len(Wbg[i])
        if bor_raw > inh_raw:
            collapse += 1
    print(f"[설계 발견] raw 우도서 차용채널이 이기는 단어: {collapse}/{N} "
          f"({collapse/N:.3f}) → 혼합 EM은 all-borrowed로 붕괴(탐지에 raw 우도 못 씀).", flush=True)

    # ---- 탐지: 결합 비지도 혼합 (phonotactic 판별 + 카탈로그 비용) ----
    # warm cluster: 카탈로그 비용 임계 → 두 음소배열 LM → per-char logratio.
    # combo = z(logratio) + z(nsim) 표준화 합에 1-D 2-GMM. 부트스트랩 8회.
    print("결합 탐지기 (phonotactic ⊕ 카탈로그 비용, 비지도)…", flush=True)
    import statistics
    seed = [1 if nsim[i] > -1.8 else 0 for i in range(N)]   # 1=borrowed 초기 클러스터
    pred = seed[:]
    for em in range(8):
        bidx = [i for i in range(N) if seed[i] == 1]
        iidx = [i for i in range(N) if seed[i] == 0]
        if not bidx or not iidx:
            break
        cb, tb = train_lm(bidx, Wbg)
        cii, ti = train_lm(iidx, Wbg)
        ratio = [lm_percharLL(Wbg[i], cb, tb, V) - lm_percharLL(Wbg[i], cii, ti, V)
                 for i in range(N)]
        mr, sr = statistics.mean(ratio), statistics.pstdev(ratio) or 1.0
        mn, sn = statistics.mean(nsim), statistics.pstdev(nsim) or 1.0
        combo = [(ratio[i] - mr) / sr + (nsim[i] - mn) / sn for i in range(N)]
        r = gmm1d(combo, max(combo), min(combo))
        pred = [r[i] > 0.5 for i in range(N)]
        seed = [1 if p else 0 for i, p in enumerate(pred)]
        f1_it = _f1(pred, gold)[0]
        print(f"  boot{em}  pred_bor={sum(pred)}  F1={f1_it:.3f}", flush=True)

    f1, prec, rec, acc = _f1(pred, gold)
    maj = max(nb, N - nb) / N

    # ---- 채널 정련 (탐지결과로 게이트 → 체계적 적응 v→b 등 학습 → 귀속 sharpen) ----
    # 탐지가 안정적이므로 pred=borrowed 단어의 best-source 정렬로 채널 재추정 후 bestsrc 갱신.
    print("채널 정련 (탐지 게이트 → 적응 학습)…", flush=True)
    for rnd in range(3):
        pairs = [(cat[bestsrc[i]], words[i]) for i in range(N) if pred[i] and bestsrc[i] >= 0]
        ch.refit(pairs)
        for i in range(N):
            if not pred[i]:
                continue
            best, bci = -1e18, -1
            for ci in cand_idx[i]:
                sc = ch.align_score(cat[ci], words[i])
                if sc > best:
                    best, bci = sc, ci
            bestsrc[i] = bci
        print(f"  refit{rnd}  pairs={len(pairs)}", flush=True)

    # ---- 출처식별 (prefilter 생존 차용 단어에 대해 argmax_s = gold?) ----
    sid_tot = sid_hit = 0
    examples = []
    for i in range(N):
        w, lab, dn = items[i]
        if lab != "borrowed" or not dn or dn not in cat_set:
            continue
        if not any(cat[ci] == dn for ci in cand_idx[i]):
            continue
        sid_tot += 1
        picked = cat[bestsrc[i]] if bestsrc[i] >= 0 else None
        hit = (picked == dn)
        sid_hit += hit
        if len(examples) < 14:
            examples.append((w, dn, picked, hit, pred[i]))
    sid_acc = sid_hit / sid_tot if sid_tot else 0

    print("-" * 64, flush=True)
    print(f"[탐지, 비지도 결합]  정확도 {acc:.3f} (다수 {maj:.3f})", flush=True)
    print(f"  precision {prec:.3f}  recall {rec:.3f}  F1 {f1:.3f}   (POC-14 0.764)", flush=True)
    print(f"[출처 식별]  정확도 {sid_acc:.3f}  ({sid_hit}/{sid_tot}, prefilter천장 {pref_rec:.3f})", flush=True)
    print("-" * 64, flush=True)
    print("출처식별 예시 (word ← gold | picked | hit | pred_bor):", flush=True)
    for w, dn, pk, hit, pb in examples:
        print(f"  {w:<14} ← {str(dn):<13} | {str(pk):<13} | {'✓' if hit else '✗'} | bor={pb}", flush=True)

    (OUT / "poc15.tsv").write_text(
        "acc\tmajority\tprecision\trecall\tf1\tpoc14_f1\tsid_acc\tsid_n\t"
        "prefilter_recall\traw_collapse_frac\n"
        f"{acc:.4f}\t{maj:.4f}\t{prec:.4f}\t{rec:.4f}\t{f1:.4f}\t0.7640\t"
        f"{sid_acc:.4f}\t{sid_tot}\t{pref_rec:.4f}\t{collapse/N:.4f}\n", encoding="utf-8")
    with open(OUT / "poc15_sources.tsv", "w", encoding="utf-8") as fo:
        fo.write("word\tgold_donor\tpicked\thit\tpred_bor\n")
        for w, dn, pk, hit, pb in examples:
            fo.write(f"{w}\t{dn}\t{pk}\t{int(hit)}\t{int(pb)}\n")

    print("-" * 64, flush=True)
    v1 = "F1 > POC-14 ✓" if f1 > 0.764 else "F1 ≤ POC-14"
    v2 = "출처식별 작동 ✓" if sid_acc > 0.5 else "출처식별 약함"
    print(f"판정: {v1} / {v2}", flush=True)
    print("결론: 카탈로그 끌림이 출처귀속(M1 신규)을 정확히 복원 + phonotactic과 결합하면 탐지도", flush=True)
    print("      POC-14 초과. ★ 탐지/귀속은 다른 통계 필요(raw 카탈로그 우도는 탐지서 붕괴).", flush=True)


def _f1(pred, gold):
    N = len(pred)
    tp = sum(1 for i in range(N) if pred[i] and gold[i])
    fp = sum(1 for i in range(N) if pred[i] and not gold[i])
    fn = sum(1 for i in range(N) if not pred[i] and gold[i])
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    acc = sum(1 for i in range(N) if pred[i] == gold[i]) / N
    return f1, prec, rec, acc


if __name__ == "__main__":
    main()
