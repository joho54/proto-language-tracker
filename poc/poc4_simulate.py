"""POC-4: 부패 시뮬→역전(denoising) 증강 검증 (PIPELINE.md §D)

검증 가정 (3중):
  1. 정방향 부패(noising)를 학습으로 역전(denoising) 가능한가? (증강 전제)
  2. 병합(merger)이 있으면 단일 daughter로는 복원 불가 = 엔트로피↑ (정보 손실)
  3. 자매어(여러 daughter)가 늘면 병합 해소 = 복원↑, 엔트로피↓ (comparative method)
     → "한국어 방언을 자매어로 동원" 결정의 근거.

성공 기준: denoise > identity baseline, 그리고 #daughters↑ 에 따라 정확도↑·엔트로피↓ (단조).
출력: poc/results/poc4_results.tsv
"""
import random, math
from collections import defaultdict, Counter
from pathlib import Path

random.seed(42)

C = list("ptkbdgsmnrl")
V = list("aeiou")

# 부패 규칙 풀 (자연스러운 변화 + 병합). 모두 치환(길이보존) → 위치정렬 1-1.
RULE_POOL = [
    ("p", "f"), ("t", "θ"), ("k", "h"),          # 약화 (가역)
    ("b", "p"), ("d", "t"), ("g", "k"),          # 무성화 (병합 유발: b,p→p)
    ("o", "u"), ("e", "i"),                        # 모음 상승 (병합: o,u→u)
    ("s", "h"),                                    # 약화 (병합: s,k→h 가능)
    ("r", "l"),                                    # 병합 r,l→l
]


def make_proto(n_words=400):
    words = []
    for _ in range(n_words):
        nsyl = random.randint(2, 3)
        w = []
        for _ in range(nsyl):
            w.append(random.choice(C))
            w.append(random.choice(V))
        words.append(tuple(w))
    return words


def make_language(n_rules=4):
    """랜덤 규칙 캐스케이드 = 한 daughter 언어."""
    rules = dict(random.sample(RULE_POOL, n_rules))
    return rules


def apply_lang(word, rules):
    """동시 적용(POC-3): 각 입력 분절 1회 변환."""
    return tuple(rules.get(s, s) for s in word)


def learn_inverse(train_proto, daughter_rules):
    """gold cognate set(train)으로 daughter→proto 역대응 분포 학습.
    반환: inv[daughter_seg] = Counter(proto_seg)  (위치무관, 문맥무관 단순화)."""
    inv = defaultdict(Counter)
    for p in train_proto:
        d = apply_lang(p, daughter_rules)
        for ds, ps in zip(d, p):
            inv[ds][ps] += 1
    return inv


def reconstruct(daughter_forms, invs):
    """여러 daughter 증거를 곱해 위치별 proto 사후분포 → argmax + 엔트로피."""
    L = len(daughter_forms[0])
    recon, ent_sum = [], 0.0
    allseg = set(C + V + list("fθhuil"))
    for i in range(L):
        # 위치 i의 proto 분포: 각 daughter의 inverse 증거 곱 (로그합)
        logp = {ps: 0.0 for ps in allseg}
        for d, inv in zip(daughter_forms, invs):
            ds = d[i]
            counter = inv.get(ds)
            tot = sum(counter.values()) if counter else 0
            for ps in allseg:
                c = counter[ps] if counter else 0
                prob = (c + 0.1) / (tot + 0.1 * len(allseg))  # 라플라스 평활
                logp[ps] += math.log(prob)
        # 정규화 → 사후분포
        mx = max(logp.values())
        post = {ps: math.exp(lp - mx) for ps, lp in logp.items()}
        z = sum(post.values())
        post = {ps: v / z for ps, v in post.items()}
        best = max(post, key=post.get)
        recon.append(best)
        ent = -sum(v * math.log(v) for v in post.values() if v > 0)
        ent_sum += ent
    return tuple(recon), ent_sum / L


def evaluate(proto, langs, k, test):
    """k개 daughter 사용 시 복원 성능."""
    invs = [learn_inverse(train, lr) for lr in langs[:k]]
    seg_correct = seg_total = word_exact = 0
    ent_acc = 0.0
    for p in test:
        dfs = [apply_lang(p, lr) for lr in langs[:k]]
        rec, ent = reconstruct(dfs, invs)
        ent_acc += ent
        if rec == p:
            word_exact += 1
        for a, b in zip(rec, p):
            seg_total += 1
            if a == b:
                seg_correct += 1
    return seg_correct / seg_total, word_exact / len(test), ent_acc / len(test)


# train/test 분할을 위해 전역 train 노출
proto_all = make_proto(400)
train = proto_all[:300]
test = proto_all[300:]


def main():
    out = Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    # 5개 daughter 언어 생성 (서로 다른 규칙셋, 병합 포함)
    langs = [make_language(n_rules=5) for _ in range(5)]

    rows = ["n_daughters\tseg_acc\tword_exact\tmean_entropy"]
    print("=" * 60)
    print("POC-4: 부패 시뮬 → 역전(denoising) 증강 검증")
    print("=" * 60)
    # identity baseline (daughter1 그대로 proto로 추정)
    id_correct = id_total = 0
    for p in test:
        d = apply_lang(p, langs[0])
        for a, b in zip(d, p):
            id_total += 1
            if a == b:
                id_correct += 1
    id_acc = id_correct / id_total
    print(f"identity baseline (부패형 그대로): seg_acc={id_acc:.3f}")
    print("-" * 60)
    print(f"{'#daughters':>11}{'seg_acc':>9}{'word_exact':>12}{'mean_H':>9}")
    for k in [1, 2, 3, 5]:
        sa, we, ent = evaluate(proto_all, langs, k, test)
        print(f"{k:>11}{sa:>9.3f}{we:>12.3f}{ent:>9.3f}")
        rows.append(f"{k}\t{sa:.4f}\t{we:.4f}\t{ent:.4f}")

    (out / "poc4_results.tsv").write_text("\n".join(rows), encoding="utf-8")

    # 판정
    sa1, we1, ent1 = evaluate(proto_all, langs, 1, test)
    sa5, we5, ent5 = evaluate(proto_all, langs, 5, test)
    print("-" * 60)
    c1 = sa1 > id_acc                       # denoise > identity
    c2 = sa5 > sa1 and ent5 < ent1          # 자매어↑ → 정확도↑·엔트로피↓
    print(f"가정1 denoise>identity: {c1}  ({sa1:.3f} > {id_acc:.3f})")
    print(f"가정3 자매어 효과(정확도↑·엔트로피↓): {c2}  "
          f"(acc {sa1:.3f}→{sa5:.3f}, H {ent1:.3f}→{ent5:.3f})")
    print(f"판정: {'PASS' if (c1 and c2) else 'REVIEW'}")


if __name__ == "__main__":
    main()
