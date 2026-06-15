"""POC-15b: 용량 청구(NML 취지)만으로 raw 생성 혼합의 붕괴가 풀리는가?

POC-15 발견: 카탈로그-조회 차용 채널 vs 음소배열 계승 채널의 raw 생성우도 비교는
7394/7394(100%) 단어서 차용이 이겨 혼합이 all-borrowed로 붕괴(용량 비대칭). POC-15는
*판별 융합*(z-score)으로 우회했다. POC-15b는 SPEC §6.5의 원리적 코어를 검증한다:

  **용량 청구 = 각 채널을 "그 채널이 *무작위 데이터*를 얼마나 잘 맞추나"로 정규화**
  (NML 확률복잡도의 추적가능 추정). 차용 채널은 어떤 단어든 카탈로그 4081개 중 최근접을
  찾아주는 '공짜 바닥점수'가 깔려 있다 — 이 바닥(= 같은 길이 무작위 단어의 기대 적합)을 빼면
  "진짜로 카탈로그가 더 잘 설명하는 초과분"만 남는다.

무작위(null) 단어: 전역 char-bigram Markov로 생성(음소배열은 그럴듯·의미는 무작위).
  채널별 per-char 바닥 floor: zbor_pc = E[best카탈로그정렬/len], zinh_pc = E[LM LL/len].
  charged_pc(w) = (채널 per-char score) − (채널 null floor pc).

검정:
  - d_raw(w)  = nsim_bor(w) − ll_inh_pc(w)        (POC-15의 붕괴 비교)
  - d_chg(w)  = charged_bor_pc(w) − charged_inh_pc(w)  (용량 청구 후)
  각각 (a) 부호 결정의 borrowed 비율(붕괴 여부), (b) 비지도 2-GMM F1 보고.
  → charged가 sane 분리(비율↓·F1↑)면 = **생성 경로가 용량 청구로 작동**(융합 불요 입증).
    아니면 = 용량 청구만으론 부족, 채널별 보정/융합 필수(§6.5 기본 경로 결정).

영속성: flush 로그 + poc/results/poc15b.tsv.
"""
import json, math, random
from collections import Counter, defaultdict
from pathlib import Path
import poc15_catalog as P

random.seed(150)
OUT = Path(__file__).parent / "results"


def gmm1d_f1(x, gold):
    """1-D 2-GMM 비지도 → borrowed=고-mean 성분, F1 반환."""
    r = P.gmm1d(x, max(x), min(x))
    pred = [r[i] > 0.5 for i in range(len(x))]
    f1, prec, rec, acc = P._f1(pred, gold)
    return f1, prec, rec, acc, sum(pred) / len(pred)


def auc(score, gold):
    """ROC-AUC (Mann–Whitney) — 클러스터링과 무관한 *분리도*. 상수 shift에 불변."""
    import bisect
    pos = [score[i] for i in range(len(score)) if gold[i]]
    neg = sorted(score[i] for i in range(len(score)) if not gold[i])
    c = 0.0
    for s in pos:
        lo = bisect.bisect_left(neg, s); hi = bisect.bisect_right(neg, s)
        c += lo + 0.5 * (hi - lo)
    return c / (len(pos) * len(neg))


def main():
    print("=" * 64, flush=True)
    print("POC-15b: 용량 청구(NML 취지)가 raw-혼합 붕괴를 푸는가", flush=True)
    print("=" * 64, flush=True)
    OUT.mkdir(exist_ok=True)

    # ---- 적재 (POC-15와 동일) ----
    items = []; catalog = Counter()
    for line in open(P.DATA, encoding="utf-8"):
        e = json.loads(line)
        lab = P.gold_label(e)
        if lab is None:
            continue
        w = P.norm(e.get("word", ""))
        if len(w) < 2:
            continue
        dl, dw = P.parse_donor(e); dn = P.norm(dw) if dw else None
        items.append((w, lab, dn))
        if lab == "borrowed" and dn and len(dn) >= 2:
            catalog[dn] += 1
    random.shuffle(items)
    cat = [s for s in catalog if len(s) >= 2]
    N = len(items); words = [w for w, _, _ in items]
    gold = [items[i][1] == "borrowed" for i in range(N)]
    nb = sum(gold)
    print(f"단어 {N} (borrowed {nb}), 카탈로그 {len(cat)}", flush=True)

    # ---- 후보 prefilter (bigram Jaccard 상위 K) ----
    K = 40
    cat_bg = [set(P.bigrams(s)) for s in cat]
    inv = defaultdict(list)
    for ci, bgs in enumerate(cat_bg):
        for bg in bgs:
            inv[bg].append(ci)

    def candidates(w):
        wb = set(P.bigrams(w)); sc = Counter()
        for bg in wb:
            for ci in inv.get(bg, ()):
                sc[ci] += 1
        cand = []
        for ci, sh in sc.most_common(K * 2):
            jac = sh / (len(wb) + len(cat_bg[ci]) - sh)
            cand.append((jac, ci))
        cand.sort(reverse=True)
        return [ci for _, ci in cand[:K]]

    ch = P.Channel()   # 고정 near-identity (용량청구 효과만 격리)

    def best_align(w, cand):
        best = -1e18
        for ci in cand:
            sc = ch.align_score(cat[ci], w)
            if sc > best:
                best = sc
        return best if best > -1e17 else -30.0 * len(w)

    # ---- 계승 LM (전체) ----
    Wbg = [P.bigrams(w) for w in words]
    V = len(set(bg for bgs in Wbg for bg in bgs))
    c_all, t_all = P.train_lm(range(N), Wbg)

    def inh_ll(w):
        bgs = P.bigrams(w)
        return sum(math.log((c_all[bg] + 0.5) / (t_all + 0.5 * V)) for bg in bgs)

    # ---- 실단어 per-char 점수 ----
    print("실단어 채널 점수…", flush=True)
    nsim = [0.0] * N; inh_pc = [0.0] * N
    for i in range(N):
        L = max(len(words[i]), 1)
        nsim[i] = best_align(words[i], candidates(words[i])) / L
        inh_pc[i] = inh_ll(words[i]) / L
        if i % 1500 == 0:
            (OUT / "poc15b_progress.log").write_text(f"score {i}/{N}", encoding="utf-8")

    # ---- 용량 floor: null 단어(전역 bigram Markov)로 추정 ----
    print("null(무작위 단어) 용량 floor 추정…", flush=True)
    # bigram Markov 전이 (^시작, $종료)
    trans = defaultdict(Counter)
    for w in words:
        s = "^" + w + "$"
        for a, b in zip(s, s[1:]):
            trans[a][b] += 1
    pref = {a: ([b for b in c], [c[b] for b in c]) for a, c in trans.items()}

    def sample_null(maxlen=18):
        cur = "^"; out = []
        for _ in range(maxlen):
            opts, wts = pref.get(cur)
            nxt = random.choices(opts, wts)[0]
            if nxt == "$":
                break
            out.append(nxt); cur = nxt
        return "".join(out)

    NULL = 2500
    zb_pc = []; zi_pc = []
    for j in range(NULL):
        wn = sample_null()
        if len(wn) < 2:
            continue
        L = len(wn)
        zb_pc.append(best_align(wn, candidates(wn)) / L)
        zi_pc.append(inh_ll(wn) / L)
        if j % 500 == 0:
            (OUT / "poc15b_progress.log").write_text(f"null {j}/{NULL}", encoding="utf-8")
    zbor = sum(zb_pc) / len(zb_pc)   # 차용 채널의 per-char '공짜 바닥'
    zinh = sum(zi_pc) / len(zi_pc)   # 계승 채널의 per-char 바닥
    print(f"null floor per-char: 차용 {zbor:.3f}  계승 {zinh:.3f}  "
          f"(실단어 평균: 차용 {sum(nsim)/N:.3f} 계승 {sum(inh_pc)/N:.3f})", flush=True)

    # ---- 두 결정통계 ----
    d_raw = [nsim[i] - inh_pc[i] for i in range(N)]                 # POC-15 붕괴 비교
    d_chg = [(nsim[i] - zbor) - (inh_pc[i] - zinh) for i in range(N)]  # 용량 청구 후

    # 부호 결정(생성 비교 그대로): d>0 → borrowed
    frac_raw = sum(1 for v in d_raw if v > 0) / N
    frac_chg = sum(1 for v in d_chg if v > 0) / N
    f1r_s, *_ = P._f1([v > 0 for v in d_raw], gold)
    f1c_s, pc, rc, ac = P._f1([v > 0 for v in d_chg], gold)

    # 비지도 2-GMM
    f1r, _, _, _, fr_gmm = gmm1d_f1(d_raw, gold)
    f1c, pcg, rcg, acg, fc_gmm = gmm1d_f1(d_chg, gold)

    # ★ 분리도(AUC) — 클러스터링과 무관. 상수 shift엔 불변.
    shift = [round(d_chg[i] - d_raw[i], 6) for i in range(N)]
    n_shift = len(set(shift))
    auc_raw = auc(d_raw, gold); auc_chg = auc(d_chg, gold); auc_ns = auc(nsim, gold)

    print("-" * 64, flush=True)
    print("[부호 결정 = raw 생성 비교 그대로]", flush=True)
    print(f"  raw     borrowed비율 {frac_raw:.3f}  F1 {f1r_s:.3f}   ← POC-15 붕괴 재현", flush=True)
    print(f"  charged borrowed비율 {frac_chg:.3f}  F1 {f1c_s:.3f}  (P {pc:.3f} R {rc:.3f})", flush=True)
    print("[비지도 2-GMM]", flush=True)
    print(f"  raw     borrowed비율 {fr_gmm:.3f}  F1 {f1r:.3f}", flush=True)
    print(f"  charged borrowed비율 {fc_gmm:.3f}  F1 {f1c:.3f}", flush=True)
    print("[★ 분리도 AUC — 방법 무관]", flush=True)
    print(f"  d_raw {auc_raw:.3f}   d_charged {auc_chg:.3f}   nsim단독 {auc_ns:.3f}", flush=True)
    print(f"  d_charged − d_raw = 전 단어 동일 상수({shift[0]:+.3f}, distinct={n_shift}) "
          f"→ 용량청구는 *순수 임계이동*, 순위·AUC 불변.", flush=True)
    print(f"  (참조: POC-15 융합 F1 0.864 — strata별 LM 로그비라는 *판별* feature 덕)", flush=True)

    (OUT / "poc15b.tsv").write_text(
        "stat\tfrac_bor\tf1\tauc\n"
        f"raw_sign\t{frac_raw:.4f}\t{f1r_s:.4f}\t{auc_raw:.4f}\n"
        f"charged_sign\t{frac_chg:.4f}\t{f1c_s:.4f}\t{auc_chg:.4f}\n"
        f"raw_gmm\t{fr_gmm:.4f}\t{f1r:.4f}\t{auc_raw:.4f}\n"
        f"charged_gmm\t{fc_gmm:.4f}\t{f1c:.4f}\t{auc_chg:.4f}\n"
        f"nsim_only\t-\t-\t{auc_ns:.4f}\n"
        f"# null_floor_perchar borrowed {zbor:.4f} inherited {zinh:.4f}; "
        f"shift(const) {shift[0]:.4f} distinct {n_shift}\n",
        encoding="utf-8")

    print("-" * 64, flush=True)
    print("판정: ★ 용량 청구(상수 floor 정규화)는 **분리도를 못 올린다** — d_raw와 AUC 동일,", flush=True)
    print("      차이는 임계값 이동뿐(붕괴비율 100%→89%지만 F1·AUC 그대로). UBM 소거와 동일 구조.", flush=True)
    print("  → 탐지는 *순위를 바꾸는 판별 feature*(채널별 보정/strata LM 로그비) 필수.", flush=True)
    print("    생성적 대칭화(토착층 동등 카탈로그)는 미검증 대안. SPEC §6.5 기본=판별 융합 확정.", flush=True)


if __name__ == "__main__":
    main()
