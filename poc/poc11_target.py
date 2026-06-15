"""POC-11: 안정어 타겟팅이 탐지 지평을 미는가? (+ 순환논증 함정 시연)

아이디어(사용자): 전부 말고 '끝까지 살아남는 일부'만 타겟해 밀자 = 안정 핵심어휘 비교.
이질적 생존율: 개념마다 단위시간 보존율 base_i 다름(안정 0.9~0.98 / 불안정 0.6~0.8).
깊이 d에서 보존율 = base_i ** d. 안정어가 깊이서 더 오래 생존.

전략:
  (a) 전체 비교
  (b) 안정어 부분집합 — base_i 상위 K (★독립기준, A·B와 무관) = 정당
  (c) 유사도 부분집합 — A·B에서 닮은 상위 K (★결과로 선택) = 순환논증, 무관 데이터에도 가짜탐지

판정: (b)가 (a)보다 깊은 d서 탐지 = 타겟팅이 지평 민다. (c)가 무관쌍서 유의 = 함정 실증.
출력: poc/results/poc11.tsv
"""
import random
from pathlib import Path
from poc6_stats import make_proto, corrupt, align, mutual_info, perm_p, RULES
from poc5_reconstruct import fdist
from poc5b_reconstruct import ft

random.seed(11)
N = 300
K = 80


def make_bases():
    b = []
    for _ in range(N):
        b.append(random.uniform(0.93, 0.99) if random.random() < 0.4
                 else random.uniform(0.50, 0.70))   # 안정/불안정 격차 ↑
    return b


def build(proto, bases, depth, rA, rB, related=True, proto2=None):
    """관련 쌍(또는 무관). 개념별 보존율 base^depth로 동원어 유지/교체."""
    pairs = []
    for i, w in enumerate(proto):
        keep = bases[i] ** depth
        if related and random.random() < keep:
            pairs.append((corrupt(w, rA), corrupt(w, rB)))          # 진짜 동원어
        else:
            oa = make_one(); ob = proto2[i] if proto2 else make_one()
            pairs.append((corrupt(oa, rA), corrupt(ob, rB)))         # 교체/무관
    return pairs


def make_one():
    C = list("ptkbdgsmnrlh"); V = list("aeiou")
    return "".join(random.choice(C) + random.choice(V) for _ in range(random.randint(2, 3)))


def sim(a, b):
    return -fdist(ft.ipa_segs(a), ft.ipa_segs(b))   # 높을수록 닮음


def topk_by(pairs, scores, k):
    idx = sorted(range(len(pairs)), key=lambda i: scores[i], reverse=True)[:k]
    return [pairs[i] for i in idx]


def main():
    out = Path(__file__).parent / "results"
    print("=" * 70, flush=True)
    print("POC-11: 안정어 타겟팅 vs 전체, + 순환논증 함정", flush=True)
    print("=" * 70, flush=True)
    proto = make_proto(N)
    bases = make_bases()
    rA, rB = dict(random.sample(RULES, 6)), dict(random.sample(RULES, 6))

    rows = ["depth\tall_p\tstable_p\tall_keep\tstable_keep"]
    print(f"{'깊이':<6}{'(a)전체 p':>12}{'(b)안정어 p':>13}   (평균 생존율 전체/안정)", flush=True)
    for d in [8, 15, 25, 40, 60]:
        pairs = build(proto, bases, d, rA, rB, related=True)
        # (a) 전체
        _, pa = perm_p(pairs, nperm=200)
        # (b) 안정어: base_i 상위 K (독립기준)
        stable = topk_by(pairs, bases, K)
        _, ps = perm_p(stable, nperm=200)
        # 진단용 평균 보존율
        ak = sum(b ** d for b in bases) / N
        sidx = sorted(range(N), key=lambda i: bases[i], reverse=True)[:K]
        sk = sum(bases[i] ** d for i in sidx) / K
        da = "✓" if pa < 0.05 else "✗"; ds = "✓" if ps < 0.05 else "✗"
        print(f"{d:<6}{pa:>9.3f} {da}{ps:>10.3f} {ds}      {ak:.2f} / {sk:.2f}", flush=True)
        rows.append(f"{d}\t{pa:.4f}\t{ps:.4f}\t{ak:.4f}\t{sk:.4f}")

    # (c) 순환논증 함정: 무관 데이터에서 '우연 lookalike'를 골라내면 설득력 있어 보임
    print("-" * 70, flush=True)
    proto2 = make_proto(N)
    unrel = build(proto, bases, 6, rA, rB, related=False, proto2=proto2)
    # 개념정렬 무관쌍 중 정규화 편집거리 낮은(닮은) 것 = 체리피킹 탄약
    lk = []
    for a, b in unrel:
        dn = fdist(ft.ipa_segs(a), ft.ipa_segs(b)) / max(len(ft.ipa_segs(a)), len(ft.ipa_segs(b)), 1)
        if dn < 0.34:
            lk.append((a, b, dn))
    lk.sort(key=lambda t: t[2])
    print("순환논증 함정 (★무관 데이터인데):", flush=True)
    print(f"  전체 {N}쌍 중 '설득력 있는 lookalike'(정규화거리<0.34): {len(lk)}개 존재", flush=True)
    print(f"  상위 예시: {[(a,b) for a,b,_ in lk[:6]]}", flush=True)
    print(f"  → 이 {len(lk)}개만 골라 나열하면 '관계 증거'처럼 보이나 전부 우연.", flush=True)
    rows.append(f"unrel_lookalikes\t{len(lk)}\tof\t{N}\t")

    (out / "poc11.tsv").write_text("\n".join(rows), encoding="utf-8")
    print("-" * 70, flush=True)
    print("결론: (b)안정어가 (a)전체보다 깊이서 탐지하면 타겟팅이 지평 민다.", flush=True)
    print("      (c)유사도선택이 무관쌍서 유의=결과로 표본 고르면 가짜신호(독립기준 필수).", flush=True)


if __name__ == "__main__":
    main()
