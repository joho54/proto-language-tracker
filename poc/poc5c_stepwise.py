"""POC-5c: 단계적(stepwise) vs 직접(direct) 재구 — 깊이의 벽을 넘는가.

가설: 깊은 재구를 '얕은 단계들의 연쇄'로 분해하면 직접 깊은 도약보다 낫다.
테스트: Proto-Germanic 트리 (PGmc → 서/북게르만 중간조어 → 현대어), 전부 라틴문자.
  - 직접:   PGmc ← 현대어 leaves (한 방, 깊음)
  - 단계적: 현대어 → 중간조어 재구(얕음) → 그것으로 PGmc 재구(얕음)
판정: 단계적 거리 < 직접 거리 → 단계적이 벽을 넘음.
출력: poc/results/poc5c.tsv  (unbuffered)
"""
import re, random
from collections import Counter
from pathlib import Path
from poc5b_reconstruct import clean, learn, reconstruct
from poc5_reconstruct import fdist, ft
import kaikki

random.seed(5)


def parse_tree(entry):
    """반환: (pgmc_word, intermediates, direct_leaves)
    intermediates: [(inter_word, {leaf_code: word})]  (proto 중간노드 + 그 말단 leaves)
    direct_leaves: {code: word}  (PGmc 직속 말단)
    """
    pgmc = clean(entry.get("word"))
    if not pgmc:
        return None
    inters, direct = [], {}

    def leaves_under(node):
        out = {}
        for ch in node.get("descendants") or []:
            sub = ch.get("descendants")
            if sub:
                out.update(leaves_under(ch))
            else:
                w = clean(ch.get("word"))
                if w and ch.get("lang_code"):
                    out.setdefault(ch["lang_code"], w)
        return out

    for nd in entry.get("descendants") or []:
        code = nd.get("lang_code", "")
        if nd.get("descendants"):                 # 중간노드(자식 있음)
            iw = clean(nd.get("word"))
            lv = leaves_under(nd)
            if iw and len(lv) >= 2:
                inters.append((code, iw, lv))
        else:                                      # PGmc 직속 말단
            w = clean(nd.get("word"))
            if w and code:
                direct.setdefault(code, w)
    return pgmc, inters, direct


def main():
    out = Path(__file__).parent / "results"
    print("=" * 64, flush=True)
    print("POC-5c: 단계적 vs 직접 재구 (Proto-Germanic 트리)", flush=True)
    print("=" * 64, flush=True)

    data = []
    for e in kaikki.load("Proto-Germanic"):
        t = parse_tree(e)
        if not t:
            continue
        pgmc, inters, direct = t
        # 비교 가능 조건: 중간조어 >=2개(각 leaf>=2), 또는 풍부한 leaves
        all_leaves = dict(direct)
        for _, _, lv in inters:
            all_leaves.update(lv)
        if len(inters) >= 2 and len(all_leaves) >= 3:
            data.append((pgmc, inters, direct, all_leaves))
    random.shuffle(data)
    sp = int(len(data) * 0.7)
    train, test = data[:sp], data[sp:]
    if len(test) > 300:
        test = test[:300]
    print(f"비교가능 셋: {len(data)} (train {len(train)} / test {len(test)})", flush=True)

    # ── 채널 학습 ──
    # 레벨L(중간조어 ← leaves): 모든 중간조어를 풀링
    L_train = [(iw, lv) for _, inters, _, _ in train for code, iw, lv in inters]
    # 레벨P(PGmc ← 중간조어): 자손=중간조어 gold
    P_train = [(pgmc, {code: iw for code, iw, _ in inters}) for pgmc, inters, _, _ in train if inters]
    # 직접(PGmc ← leaves)
    D_train = [(pgmc, al) for pgmc, _, _, al in train]

    fwdL, lmL, uniL, vocL = learn(L_train)
    fwdP, lmP, uniP, vocP = learn(P_train)
    fwdD, lmD, uniD, vocD = learn(D_train)
    aL = Counter(c for _, lv in L_train for c in lv).most_common(1)[0][0]
    aP = Counter(c for _, d in P_train for c in d).most_common(1)[0][0]
    aD = Counter(c for _, d in D_train for c in d).most_common(1)[0][0]
    print(f"앵커 L={aL} P={aP} D={aD}", flush=True)

    dirT = stepT = base = n = 0.0
    for pgmc, inters, direct, all_leaves in test:
        gold = ft.ipa_segs(pgmc)
        # 직접
        rec_d, _ = reconstruct(all_leaves, fwdD, lmD, uniD, vocD, aD)
        # 단계적: 각 중간조어 재구 → PGmc 재구
        rec_inter = {}
        for code, iw, lv in inters:
            ri, _ = reconstruct(lv, fwdL, lmL, uniL, vocL, aL)
            rec_inter[code] = "".join(ri)
        if len(rec_inter) < 2:
            continue
        rec_s, _ = reconstruct(rec_inter, fwdP, lmP, uniP, vocP, aP)
        dirT += fdist(rec_d, gold)
        stepT += fdist(rec_s, gold)
        # baseline: 가장 보수적 leaf (앵커D) 그대로
        if aD in all_leaves:
            base += fdist(ft.ipa_segs(all_leaves[aD]), gold)
        n += 1

    print("-" * 64, flush=True)
    print(f"테스트 {int(n)}셋", flush=True)
    print(f"직접 재구 (PGmc←현대어 한방):   거리 {dirT/n:.3f}", flush=True)
    print(f"단계적 재구 (현대어→중간→PGmc): 거리 {stepT/n:.3f}", flush=True)
    print("-" * 64, flush=True)
    win = stepT < dirT
    print(f"판정: {'단계적 우월 ✓ (깊이의 벽 넘음)' if win else '단계적 이점 없음'} "
          f"(Δ={(dirT-stepT)/n:+.3f})", flush=True)
    (out / "poc5c.tsv").write_text(
        f"direct\tstepwise\tn\n{dirT/n:.4f}\t{stepT/n:.4f}\t{int(n)}", encoding="utf-8")


if __name__ == "__main__":
    main()
