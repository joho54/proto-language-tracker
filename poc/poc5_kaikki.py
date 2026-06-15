"""POC-5 (v2): 베이지안 재구 미니 (Phase 0) — kaikki 오프라인.

Wikimedia 버전 폐기(429 + cat_members 버그). kaikki proto 파일에서 조어를 자손으로 재구.
대상: Proto-Indo-European (gold=PIE word, 자손=1차 분기 반사형 중 Latin표기, >=3).
※ gold가 재구형(Wiktionary PIE)이므로 "정설 재구의 재현" 일관성 검정 (SPEC §7 Phase0).

방법은 poc5_reconstruct 재사용(forward-channel 베이지안, anchor 정렬, 칼럼 argmax).
판정: 재구 < baseline(자질거리), #daughters↑ → 거리↓·엔트로피↓ (POC-4 실데이터 재현).
출력: poc/results/poc5_kaikki.tsv  (unbuffered 로그)
"""
import re, random
from collections import Counter
from pathlib import Path
from poc5_reconstruct import align, learn_channel, reconstruct, fdist, ft
from normalize import normalize_ipa
import kaikki

random.seed(5)
FAM = "Proto-Indo-European"
LATIN = re.compile(r"[a-zɑ-ʯæœøðθβɣχʃʒŋɲʔ]")


def clean(w):
    w = (w or "").strip().lstrip("*").replace("H", "h")
    w = w.split(",")[0].split(";")[0].strip()
    if not w or " " in w:
        return None
    L = [c for c in w.lower() if c.isalpha()]
    if not L or sum(bool(LATIN.match(c)) for c in L) / len(L) < 0.7:
        return None
    ipa = normalize_ipa(w)[0]
    return ipa if len(ft.ipa_segs(ipa)) >= 2 else None


def get_sets():
    sets = []
    for e in kaikki.load(FAM):
        proto = clean(e.get("word"))
        if not proto:
            continue
        daughters = {}
        for nd in e.get("descendants") or []:
            tmp = []
            kaikki._walk(e.get("word"), [nd], tmp, None)
            for _, w, code in tmp:
                d = clean(w)
                if d and code and code not in daughters:
                    daughters[code] = d
        if len(daughters) >= 3:
            sets.append((proto, daughters))
    return sets


def main():
    out = Path(__file__).parent / "results"
    print("=" * 64, flush=True)
    print("POC-5 v2: 베이지안 재구 (PIE 자손→PIE, kaikki 오프라인)", flush=True)
    print("=" * 64, flush=True)
    sets = get_sets()
    random.shuffle(sets)
    split = int(len(sets) * 0.7)
    train, test = sets[:split], sets[split:]
    print(f"동원어셋: {len(sets)} (train {len(train)} / test {len(test)})", flush=True)
    cov = Counter(c for _, ds in sets for c in ds)
    print("자손코드 top:", cov.most_common(10), flush=True)

    fwd = learn_channel(train)
    vocab = set()
    for proto, _ in train:
        vocab |= set(ft.ipa_segs(proto))

    # anchor = 훈련상 gold에 가장 가까운(보수적) 자손
    sc = {}
    for code in cov:
        pairs = [(p, d[code]) for p, d in train if code in d]
        if len(pairs) >= 10:
            sc[code] = sum(fdist(ft.ipa_segs(p), ft.ipa_segs(x)) for p, x in pairs) / len(pairs)
    anchor = min(sc, key=sc.get)
    print(f"anchor(최보수) = {anchor} (평균거리 {sc[anchor]:.2f})", flush=True)

    base = [fdist(ft.ipa_segs(ds[anchor]), ft.ipa_segs(p)) for p, ds in test if anchor in ds]
    base_mean = sum(base) / len(base) if base else float("nan")
    print(f"baseline (anchor '{anchor}' 그대로): {base_mean:.3f}", flush=True)
    print("-" * 64, flush=True)

    rows = ["n_daughters\tmean_dist\texact\tmean_entropy"]
    print(f"{'#daughters':>11}{'mean_dist':>11}{'exact':>8}{'mean_H':>9}", flush=True)
    for k in [1, 2, 3, 99]:
        dt = et = ex = nv = 0.0
        for proto, ds in test:
            sub = dict(list(ds.items())[:k]) if k < 99 else ds
            if not sub:
                continue
            rec, ent = reconstruct(sub, fwd, vocab, anchor)
            dt += fdist(rec, ft.ipa_segs(proto)); et += ent
            ex += (rec == tuple(ft.ipa_segs(proto))); nv += 1
        kk = "all" if k == 99 else k
        print(f"{str(kk):>11}{dt/nv:>11.3f}{ex/nv:>8.2f}{et/nv:>9.3f}", flush=True)
        rows.append(f"{kk}\t{dt/nv:.4f}\t{ex/nv:.4f}\t{et/nv:.4f}")

    (out / "poc5_kaikki.tsv").write_text("\n".join(rows), encoding="utf-8")
    d_all = float(rows[-1].split("\t")[1]); d_1 = float(rows[1].split("\t")[1])
    print("-" * 64, flush=True)
    print(f"판정: 재구(all) {d_all:.3f} vs baseline {base_mean:.3f} "
          f"→ {'재구 우월' if d_all < base_mean else '개선 없음'}", flush=True)
    print(f"      자매어 효과: {d_1:.3f}(1) → {d_all:.3f}(all) "
          f"{'(개선)' if d_all < d_1 else '(없음)'}", flush=True)


if __name__ == "__main__":
    main()
