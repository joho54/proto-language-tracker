"""POC-12: 교체 유형화 — 계보 vs 접촉 구별 + 접촉층 신호 복원.

사용자 아이디어: 교체를 '무신호'로 끝내지 말고 유형화(차용 from 출처 S / 혁신)하면
  (a) 차용층을 걷어내 계보 검정을 깨끗이, (b) 차용층 자체를 접촉 신호로 *창조*.
한국어 직결: 한자어(Sino-xenic) 차용층이 한-일에 가짜 계보 신호 → 유형화로 걷어야 정직한 검정.

두 시나리오 (둘 다 A,B가 출처 S에서 공유 차용):
  S1: A,B 계보 관련 + 공유 차용층
  S2: A,B 무관, 공유 차용층만 (순수 접촉) ← Georg 함정
검정:
  naive  = 모든 쌍에 MI+순열 (차용+계보 혼동)
  typed  = 차용 탐지(둘 다 S와 닮음) 제거 후 잔여로 MI+순열 (정직한 계보)
판정: naive는 S2서도 가짜 유의. typed는 S1=유의/S2=무유의로 구별 + 차용 수 보고(접촉 신호).
출력: poc/results/poc12.tsv
"""
import random
from pathlib import Path
from poc6_stats import corrupt, mutual_info, perm_p, RULES
from poc5_reconstruct import fdist
from poc5b_reconstruct import ft

random.seed(12)
N = 300
# 큰 음소 인벤토리 → 무작위 단어 우연 유사성 ↓ (POC-11/초기 POC-12 병 해결)
BC = list("ptkbdgfszmnrlhwjθʃxŋ")
BV = list("aeiouɛɔə")


def make_proto(n=N):
    return ["".join(random.choice(BC) + random.choice(BV)
                    for _ in range(random.randint(3, 4))) for _ in range(n)]


def nd(a, b):
    """분절 동일성 정규화 편집거리(Levenshtein). 차용 탐지용 — 자질거리는 무관어도 작아서 못 씀."""
    sa, sb = ft.ipa_segs(a), ft.ipa_segs(b)
    n, m = len(sa), len(sb)
    D = list(range(m + 1))
    for i in range(1, n + 1):
        prev, D[0] = D[0], i
        for j in range(1, m + 1):
            cur = D[j]
            D[j] = min(D[j] + 1, D[j-1] + 1, prev + (sa[i-1] != sb[j-1]))
            prev = cur
    return D[m] / max(n, m, 1)


def build(proto, src, related, rA, rB, rLA, rLB, p_loan=0.4, retention=0.6):
    """개념별 유형: 차용(공유 from S) / 계승(related시) / 혁신."""
    pairs, truth = [], []
    for i in range(N):
        u = random.random()
        if u < p_loan:
            pairs.append((corrupt(src[i], rLA), corrupt(src[i], rLB))); truth.append("loan")
        elif related and random.random() < retention:
            pairs.append((corrupt(proto[i], rA), corrupt(proto[i], rB))); truth.append("inherit")
        else:
            pairs.append((corrupt(mk(), rA), corrupt(mk(), rB))); truth.append("innov")
    return pairs, truth


def mk():
    return "".join(random.choice(BC) + random.choice(BV) for _ in range(random.randint(3, 4)))


def detect_loans(pairs, src, theta=0.5):
    """둘 다 출처 S와 닮으면 공유 차용으로 플래그."""
    flag = []
    for i, (a, b) in enumerate(pairs):
        flag.append(nd(a, src[i]) < theta and nd(b, src[i]) < theta)
    return flag


def run(name, related, proto, src, rA, rB, rLA, rLB):
    pairs, truth = build(proto, src, related, rA, rB, rLA, rLB)
    _, p_naive = perm_p(pairs, nperm=200)
    flag = detect_loans(pairs, src)
    kept = [pairs[i] for i in range(N) if not flag[i]]
    _, p_typed = perm_p(kept, nperm=200) if len(kept) > 20 else (0, 1.0)
    n_loan_true = truth.count("loan")
    n_loan_det = sum(flag)
    # 탐지 정확도
    tp = sum(1 for i in range(N) if flag[i] and truth[i] == "loan")
    prec = tp / n_loan_det if n_loan_det else 0
    rec = tp / n_loan_true if n_loan_true else 0
    print(f"[{name}] 관련={related}", flush=True)
    print(f"  naive(전체) p={p_naive:.3f} {'유의' if p_naive<0.05 else '무유의'}", flush=True)
    print(f"  typed(차용제거 후 {len(kept)}쌍) p={p_typed:.3f} "
          f"{'유의=계보 ✓' if p_typed<0.05 else '무유의=계보 없음'}", flush=True)
    print(f"  차용 탐지: {n_loan_det}개 (실제 {n_loan_true}, precision {prec:.2f} recall {rec:.2f}) = 접촉층 신호", flush=True)
    return name, related, p_naive, p_typed, n_loan_det, n_loan_true, prec, rec


def main():
    out = Path(__file__).parent / "results"
    print("=" * 68, flush=True)
    print("POC-12: 교체 유형화 — 계보 vs 접촉 구별", flush=True)
    print("=" * 68, flush=True)
    proto = make_proto(N)
    src = make_proto(N)                       # 출처 S (A,B와 무관)
    rA, rB = dict(random.sample(RULES, 6)), dict(random.sample(RULES, 6))
    rLA, rLB = dict(random.sample(RULES, 2)), dict(random.sample(RULES, 2))  # 차용 적응(약)

    rows = ["scenario\trelated\tnaive_p\ttyped_p\tloan_det\tloan_true\tprec\trecall"]
    r1 = run("S1 관련+차용", True, proto, src, rA, rB, rLA, rLB)
    print("-" * 68, flush=True)
    r2 = run("S2 무관+차용만", False, proto, src, rA, rB, rLA, rLB)
    for r in (r1, r2):
        rows.append("\t".join(str(x) for x in r))
    (out / "poc12.tsv").write_text("\n".join(rows), encoding="utf-8")
    print("-" * 68, flush=True)
    print("기대: naive는 S2(무관)서도 차용 때문에 가짜 유의. typed는 S1만 유의→계보/접촉 구별.", flush=True)


if __name__ == "__main__":
    main()
