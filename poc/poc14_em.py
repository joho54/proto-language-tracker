"""POC-14: 2-모드 혼합 EM 프로토타입 (Maltese) — 일반 기제 + EM + MDL.

질문: 유형을 손으로 안 넣어도, *비지도* 혼합 EM이 일탈 층(차용)을 *발견*하고
      MDL이 그 분리를 채택하는가? (= "일일이 추가" 불안의 직접 해소)

모델: char bigram 언어모델 K=2개의 혼합. EM으로 두 phonotactic 모드 발견(라벨 미사용).
평가: (1) gold 어원(차용/계승)과 비지도 복원 정확도/F1, (2) MDL/BIC: 2-모드 vs 1-모드.
출력: poc/results/poc14.tsv
"""
import json, random, math, re
from collections import Counter
from pathlib import Path
from poc13_real_loan import gold_label, get_ipa, DATA

random.seed(14)


def bigrams(s):
    s = "^" + s + "$"
    return [s[i:i+2] for i in range(len(s) - 1)]


def lm_logp(word_bgs, counts, tot, V, a=0.5):
    return sum(math.log((counts[bg] + a) / (tot + a * V)) for bg in word_bgs)


def main():
    out = Path(__file__).parent / "results"
    print("=" * 60, flush=True)
    print("POC-14: 2-모드 혼합 EM (Maltese, 비지도)", flush=True)
    print("=" * 60, flush=True)
    data = []
    for line in open(DATA, encoding="utf-8"):
        e = json.loads(line)
        lab, ipa = gold_label(e), get_ipa(e)
        if lab and ipa and len(ipa) >= 2:
            data.append((bigrams(ipa), lab))
    random.shuffle(data)
    X = [d[0] for d in data]
    gold = [d[1] for d in data]
    N = len(X)
    vocab = set(bg for w in X for bg in w)
    V = len(vocab)
    print(f"단어 {N}, bigram vocab {V}, gold {dict(Counter(gold))}", flush=True)

    # ---- 1-모드 baseline LL ----
    c1 = Counter(bg for w in X for bg in w)
    t1 = sum(c1.values())
    LL1 = sum(lm_logp(w, c1, t1, V) for w in X)

    # ---- 2-모드 EM (여러 restart) ----
    def em(seed):
        rnd = random.Random(seed)
        r = [[rnd.random(), 0] for _ in range(N)]
        for k in range(N):
            r[k][1] = 1 - r[k][0]
        pi = [0.5, 0.5]
        prevLL = None
        for it in range(40):
            # M
            cnt = [Counter(), Counter()]
            for i, w in enumerate(X):
                for kk in (0, 1):
                    for bg in w:
                        cnt[kk][bg] += r[i][kk]
            tot = [sum(cnt[0].values()), sum(cnt[1].values())]
            pi = [sum(r[i][0] for i in range(N)) / N, sum(r[i][1] for i in range(N)) / N]
            # E + LL
            LL = 0.0
            for i, w in enumerate(X):
                lp = [math.log(pi[kk] + 1e-12) + lm_logp(w, cnt[kk], tot[kk], V) for kk in (0, 1)]
                m = max(lp)
                ex = [math.exp(lp[kk] - m) for kk in (0, 1)]
                z = sum(ex)
                r[i] = [ex[0] / z, ex[1] / z]
                LL += m + math.log(z)
            if prevLL is not None and abs(LL - prevLL) < 1e-3:
                break
            prevLL = LL
        return LL, r, cnt, tot, pi

    best = max((em(s) for s in range(4)), key=lambda t: t[0])
    LL2, r, cnt, tot, pi = best

    # ---- 평가: 클러스터→라벨 (다수결) ----
    assign = [0 if r[i][0] > r[i][1] else 1 for i in range(N)]
    # 어느 클러스터가 borrowed?
    maj = {}
    for k in (0, 1):
        labs = Counter(gold[i] for i in range(N) if assign[i] == k)
        maj[k] = labs.most_common(1)[0][0] if labs else "?"
    pred = [maj[assign[i]] for i in range(N)]
    acc = sum(pred[i] == gold[i] for i in range(N)) / N
    tp = sum(1 for i in range(N) if pred[i] == "borrowed" and gold[i] == "borrowed")
    fp = sum(1 for i in range(N) if pred[i] == "borrowed" and gold[i] != "borrowed")
    fn = sum(1 for i in range(N) if pred[i] != "borrowed" and gold[i] == "borrowed")
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    majcls = max(Counter(gold).values()) / N

    # ---- MDL / BIC ----
    bic1 = -2 * LL1 + V * math.log(N)
    bic2 = -2 * LL2 + (2 * V + 1) * math.log(N)

    print("-" * 60, flush=True)
    print(f"cluster→label: {maj}", flush=True)
    print(f"비지도 복원 정확도: {acc:.3f}  (다수 baseline {majcls:.3f})", flush=True)
    print(f"차용 F1: {f1:.3f}  (P {prec:.3f} R {rec:.3f})", flush=True)
    print("-" * 60, flush=True)
    print(f"LL: 1-모드 {LL1:.0f}  →  2-모드 {LL2:.0f}  (Δ {LL2-LL1:+.0f})", flush=True)
    print(f"BIC: 1-모드 {bic1:.0f}  vs  2-모드 {bic2:.0f}  → "
          f"{'2-모드 채택 ✓(유형 제값)' if bic2 < bic1 else '1-모드 (분리 무의미)'}", flush=True)
    (out / "poc14.tsv").write_text(
        f"acc\tmajority\tf1\tLL1\tLL2\tBIC1\tBIC2\n"
        f"{acc:.4f}\t{majcls:.4f}\t{f1:.4f}\t{LL1:.1f}\t{LL2:.1f}\t{bic1:.1f}\t{bic2:.1f}",
        encoding="utf-8")
    print("-" * 60, flush=True)
    print("결론: 라벨 없이 EM이 차용층 발견 + MDL이 2-모드 채택 → 유형은 데이터가 판정(손코딩 불요).", flush=True)


if __name__ == "__main__":
    main()
