"""POC-10: 이산 vs 연속(sound vector) 추출기 — 어느 쪽이 탐지 지평을 더 미나?

가설(H-표현): 이산법은 hard threshold로 약한 분산 신호를 버린다 → 연속 자질벡터법이
  더 낮은 동원어 생존율에서도 탐지(지평을 민다).
대립(H-정보): 신호 파괴가 한계 → 둘 다 같은 데서 붕괴(표현 무관).

둘 다 순열검정으로 게이트(falsifiability 유지). 같은 동원어-손실 합성에 나란히.
  이산:  정렬 분절 '동일성' 상호정보 (POC-6)
  연속:  정렬 자질벡터 회귀 R² (A자질→B자질 예측, sub-분절 gradient 적분)
출력: poc/results/poc10.tsv  (unbuffered)
"""
import random, math
from pathlib import Path
import numpy as np
from poc6_stats import make_proto, corrupt, align, mutual_info, RULES
from poc5b_reconstruct import ft

random.seed(10)
np.random.seed(10)


def vec(seg):
    v = ft.word_to_vector_list(seg, numeric=True)
    return v[0] if len(v) == 1 else None


def gather_xy(pairs):
    X, Y = [], []
    for a, b in pairs:
        for x, y in align(a, b):
            if x is None or y is None:
                continue
            vx, vy = vec(x), vec(y)
            if vx is not None and vy is not None:
                X.append(vx); Y.append(vy)
    return np.array(X, float), np.array(Y, float)


def r2_stat(pairs):
    X, Y = gather_xy(pairs)
    if len(X) < 10:
        return 0.0
    Xb = np.hstack([X, np.ones((len(X), 1))])
    lam = 1.0
    W = np.linalg.solve(Xb.T @ Xb + lam * np.eye(Xb.shape[1]), Xb.T @ Y)
    Yh = Xb @ W
    ssr = ((Y - Yh) ** 2).sum()
    sst = ((Y - Y.mean(0)) ** 2).sum()
    return 1 - ssr / sst if sst > 0 else 0.0


def perm_p(pairs, stat_fn, nperm=200):
    obs = stat_fn(pairs)
    A = [a for a, _ in pairs]; B = [b for _, b in pairs]
    ge = 0
    for _ in range(nperm):
        Bs = B[:]; random.shuffle(Bs)
        if stat_fn(list(zip(A, Bs))) >= obs:
            ge += 1
    return obs, (ge + 1) / (nperm + 1)


def main():
    out = Path(__file__).parent / "results"
    print("=" * 66, flush=True)
    print("POC-10: 이산 vs 연속(sound vector) 탐지 지평", flush=True)
    print("=" * 66, flush=True)
    proto = make_proto(200)

    def daughters(d):
        return dict(random.sample(RULES, d))

    rows = ["keep\tdisc_MI\tdisc_p\tcont_R2\tcont_p\tdisc\tcont"]
    print(f"{'동원어생존율':<12}{'이산MI':>8}{'이산p':>8}{'연속R²':>8}{'연속p':>8}  탐지(이산/연속)", flush=True)
    for keep in [0.15, 0.10, 0.08, 0.05, 0.03]:
        rA, rB = daughters(6), daughters(6)
        other = make_proto(200)
        pr = []
        for i, w in enumerate(proto):
            if random.random() < keep:
                pr.append((corrupt(w, rA), corrupt(w, rB)))
            else:
                pr.append((corrupt(w, rA), corrupt(other[i], rB)))
        mi, pmi = perm_p(pr, mutual_info)
        r2, pr2 = perm_p(pr, r2_stat)
        dd = "✓" if pmi < 0.05 else "✗"
        dc = "✓" if pr2 < 0.05 else "✗"
        print(f"{keep:<12.0%}{mi:>8.3f}{pmi:>8.3f}{r2:>8.3f}{pr2:>8.3f}     {dd} / {dc}", flush=True)
        rows.append(f"{keep}\t{mi:.4f}\t{pmi:.4f}\t{r2:.4f}\t{pr2:.4f}\t{dd}\t{dc}")

    (out / "poc10.tsv").write_text("\n".join(rows), encoding="utf-8")
    print("-" * 66, flush=True)
    print("연속이 더 낮은 생존율서 ✓ = H-표현(지평 민다). 둘이 같이 무너지면 = H-정보(한계).", flush=True)


if __name__ == "__main__":
    main()
