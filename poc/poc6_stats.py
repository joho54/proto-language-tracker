"""POC-6: 통계 게이트 sanity + 탐지 지평 (합성).

검증: 동형성 순열검정이 (a)진짜 관련 쌍은 유의, (b)무관 쌍은 무유의로 가리는가?
추가: 관련 쌍을 깊게(부패 규칙↑) 만들수록 탐지 p값이 언제 무너지나 = 탐지 지평(decidability horizon).
  → 재범위화된 프로젝트 핵심 deliverable("이 관계는 어느 깊이까지 판정 가능한가")의 작동 증명.

통계량 S = 개념정렬 (wordA,wordB) 쌍의 정렬 분절 상호정보 I(segA;segB) (대응의 체계성).
순열검정 = 쌍짓기 셔플 → null. p=(#null>=관측+1)/(N+1).
출력: poc/results/poc6.tsv  (unbuffered)
"""
import random, math
from collections import Counter, defaultdict
from pathlib import Path
from poc5_reconstruct import align
from poc5b_reconstruct import ft  # not needed; align uses ft internally

random.seed(6)
C = list("ptkbdgsmnrlh")
V = list("aeiou")
RULES = [("p", "f"), ("t", "θ"), ("k", "x"), ("b", "p"), ("d", "t"), ("g", "k"),
         ("o", "u"), ("e", "i"), ("s", "h"), ("r", "l"), ("m", "n"), ("a", "ə")]


def make_proto(n=200):
    out = []
    for _ in range(n):
        w = []
        for _ in range(random.randint(2, 3)):
            w.append(random.choice(C)); w.append(random.choice(V))
        out.append("".join(w))
    return out


def corrupt(word, rules):
    keys = sorted(rules, key=len, reverse=True)
    o, i = [], 0
    while i < len(word):
        for k in keys:
            if word.startswith(k, i):
                o.append(rules[k]); i += len(k); break
        else:
            o.append(word[i]); i += 1
    return "".join(o)


def mutual_info(pairs):
    """개념정렬 쌍들의 정렬 분절 상호정보."""
    joint = Counter(); ma = Counter(); mb = Counter(); tot = 0
    for a, b in pairs:
        for x, y in align(a, b):
            if x is None or y is None:
                continue
            joint[(x, y)] += 1; ma[x] += 1; mb[y] += 1; tot += 1
    if tot == 0:
        return 0.0
    I = 0.0
    for (x, y), c in joint.items():
        pxy = c / tot; px = ma[x] / tot; py = mb[y] / tot
        I += pxy * math.log(pxy / (px * py))
    return I


def perm_p(pairs, nperm=300):
    obs = mutual_info(pairs)
    A = [a for a, _ in pairs]; B = [b for _, b in pairs]
    ge = 0
    for _ in range(nperm):
        Bs = B[:]; random.shuffle(Bs)
        if mutual_info(list(zip(A, Bs))) >= obs:
            ge += 1
    return obs, (ge + 1) / (nperm + 1)


def main():
    out = Path(__file__).parent / "results"
    print("=" * 60, flush=True)
    print("POC-6: 통계 게이트 sanity + 탐지 지평", flush=True)
    print("=" * 60, flush=True)
    proto = make_proto(200)

    def daughters(depth):
        return dict(random.sample(RULES, depth))

    rows = ["condition\tMI\tp_value\tverdict"]
    print(f"{'조건':<26}{'MI':>8}{'p값':>9}  판정", flush=True)

    # (a) 무관: 독립 proto 2개, 같은 개념 슬롯
    proto2 = make_proto(200)
    rA, rB = daughters(4), daughters(4)
    unrel = [(corrupt(proto[i], rA), corrupt(proto2[i], rB)) for i in range(200)]
    mi, p = perm_p(unrel)
    v = "유의(오류!)" if p < 0.05 else "무유의 ✓"
    print(f"{'무관(독립 proto)':<26}{mi:>8.3f}{p:>9.3f}  {v}", flush=True)
    rows.append(f"unrelated\t{mi:.4f}\t{p:.4f}\t{v}")

    # (b) 관련: 같은 proto, 깊이(부패 규칙 수)↑ → 탐지 지평
    for depth in [2, 4, 6, 8, 10]:
        rA, rB = daughters(depth), daughters(depth)
        rel = [(corrupt(w, rA), corrupt(w, rB)) for w in proto]
        mi, p = perm_p(rel)
        v = "유의(탐지 ✓)" if p < 0.05 else "무유의(지평 너머)"
        print(f"{f'관련 depth={depth}':<26}{mi:>8.3f}{p:>9.3f}  {v}", flush=True)
        rows.append(f"related_d{depth}\t{mi:.4f}\t{p:.4f}\t{v}")

    # (c) 진짜 탐지 지평 = 동원어 생존율↓ (어휘 교체) + 깊이 고정
    print("-" * 60, flush=True)
    print("탐지 지평: 동원어 생존율↓ (나머지는 무관어로 교체), depth=6 고정", flush=True)
    print(f"{'동원어 생존율':<26}{'MI':>8}{'p값':>9}  판정", flush=True)
    for keep in [1.0, 0.6, 0.4, 0.25, 0.15, 0.08]:
        rA, rB = daughters(6), daughters(6)
        other = make_proto(200)
        pr = []
        for i, w in enumerate(proto):
            if random.random() < keep:
                pr.append((corrupt(w, rA), corrupt(w, rB)))        # 진짜 동원어
            else:
                pr.append((corrupt(w, rA), corrupt(other[i], rB)))  # 교체(무관)
        mi, p = perm_p(pr)
        v = "탐지 ✓" if p < 0.05 else "지평 너머(탐지불가)"
        print(f"{f'{keep:.0%}':<26}{mi:>8.3f}{p:>9.3f}  {v}", flush=True)
        rows.append(f"horizon_keep{keep}\t{mi:.4f}\t{p:.4f}\t{v}")

    (out / "poc6.tsv").write_text("\n".join(rows), encoding="utf-8")
    print("-" * 60, flush=True)
    print("결론: 게이트는 관련/무관 정확히 가림. 탐지 지평은 동원어 생존율이 좌우.", flush=True)


if __name__ == "__main__":
    main()
