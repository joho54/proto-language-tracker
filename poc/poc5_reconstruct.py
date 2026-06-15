"""POC-5: 베이지안 재구 미니 (Phase 0) — 실데이터.

검증: 실제 로망스어(it/es/pt/fr/ro/ca)에서 라틴어를 베이지안 재구 → 정답 라틴어와 비교.
POC-4(이상화 시뮬)가 실데이터에서 얼마나 무너지나? 자매어↑ 효과가 실제로도 성립하나?

방법(forward-channel 베이지안):
  - 훈련 동원어셋(gold 라틴 + 로망스 반사형)에서 정렬(panphon NW)로
    언어별 P(daughter_seg | latin_seg) 학습 (삭제<DEL> 포함).
  - 테스트: anchor 언어(훈련상 가장 보수적) 프레임에 다른 daughter 정렬 →
    각 칼럼에서 argmax_latin ∏_lang P(관측 | latin) (균등 prior) → 재구 + 엔트로피.
  - 정답 라틴어와 panphon 자질 편집거리 비교. baseline: 보수적 daughter 그대로.

판정: 재구 < baseline(거리), 그리고 #daughters↑ → 거리↓·엔트로피↓ (POC-4 재현).
출력: poc/results/poc5_results.tsv
"""
import re, math, random
from collections import Counter, defaultdict
from pathlib import Path
import panphon
from panphon.distance import Distance
from normalize import normalize_ipa
from wikt import cat_members, fetch_many

random.seed(5)
ft = panphon.FeatureTable()
dist = Distance()
TARGETS = ["it", "es", "pt", "fr", "ro", "ca"]   # 로망스 daughter
N_LEMMA = 300
DESC_RE = re.compile(r"\{\{desc(?:tree)?\|([a-z-]+)\|([^|}]*)")


def clean(form):
    f = form.strip().lstrip("*").replace("[[", "").replace("]]", "")
    f = f.split("|")[0].split("<")[0].strip()
    return normalize_ipa(f)[0] if f and " " not in f else None


def get_cognsets():
    titles = cat_members("Latin lemmas", N_LEMMA)
    pages = fetch_many(titles)
    sets = []
    for t in titles:
        latin = clean(t.split(":", 1)[1]) if ":" in t else None
        if not latin or len(ft.ipa_segs(latin)) < 2:
            continue
        w = pages.get(t, "")
        i = w.lower().find("descendants")
        if i < 0:
            continue
        daughters = {}
        for code, form in DESC_RE.findall(w[i:i + 1500]):
            if code in TARGETS and code not in daughters:
                d = clean(form)
                if d and len(ft.ipa_segs(d)) >= 2:
                    daughters[code] = d
        if len(daughters) >= 3:
            sets.append((latin, daughters))
    return sets


def align(p, d):
    ps, ds = ft.ipa_segs(p), ft.ipa_segs(d)
    n, m = len(ps), len(ds)
    GAP = 0.8

    def vec(s):
        v = ft.word_to_vector_list(s, numeric=True)
        return v[0] if len(v) == 1 else None

    def sub(a, b):
        if a == b:
            return 0.0
        va, vb = vec(a), vec(b)
        return 1.0 if va is None or vb is None else sum(x != y for x, y in zip(va, vb)) / len(va)

    D = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        D[i][0] = i * GAP
    for j in range(1, m + 1):
        D[0][j] = j * GAP
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i][j] = min(D[i-1][j-1] + sub(ps[i-1], ds[j-1]), D[i-1][j] + GAP, D[i][j-1] + GAP)
    i, j, al = n, m, []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and abs(D[i][j] - (D[i-1][j-1] + sub(ps[i-1], ds[j-1]))) < 1e-9:
            al.append((ps[i-1], ds[j-1])); i -= 1; j -= 1
        elif i > 0 and abs(D[i][j] - (D[i-1][j] + GAP)) < 1e-9:
            al.append((ps[i-1], None)); i -= 1
        else:
            al.append((None, ds[j-1])); j -= 1
    return al[::-1]


def learn_channel(train):
    """P(daughter_seg | latin_seg) per language, <DEL> 포함."""
    fwd = defaultdict(lambda: defaultdict(Counter))   # lang -> latin_seg -> Counter(daughter_seg)
    for latin, ds in train:
        for lang, form in ds.items():
            for l, d in align(latin, form):
                if l is None:
                    continue                          # daughter 삽입 — 스킵
                fwd[lang][l][d if d is not None else "<DEL>"] += 1
    return fwd


def reconstruct(daughters, fwd, latin_vocab, anchor_lang):
    """anchor 프레임 + 칼럼별 argmax_latin ∏ P(관측|latin)."""
    if anchor_lang not in daughters:
        anchor_lang = next(iter(daughters))
    A = daughters[anchor_lang]
    segsA = ft.ipa_segs(A)
    # 다른 daughter를 anchor에 정렬 → anchor 위치별 관측 모으기
    obs = [dict() for _ in segsA]      # 위치 -> {lang: seg or <DEL>}
    for pos, s in enumerate(segsA):
        obs[pos][anchor_lang] = s
    for lang, form in daughters.items():
        if lang == anchor_lang:
            continue
        ai = 0
        for a, d in align(A, form):
            if a is None:
                continue                # anchor gap (daughter 삽입) 스킵
            if ai < len(segsA):
                obs[ai][lang] = d if d is not None else "<DEL>"
            ai += 1
    recon, ent_sum = [], 0.0
    for col in obs:
        logp = {}
        for cand in latin_vocab:
            lp = 0.0
            for lang, o in col.items():
                c = fwd[lang].get(cand)
                tot = sum(c.values()) if c else 0
                prob = ((c[o] if c else 0) + 0.3) / (tot + 0.3 * (len(latin_vocab) + 1))
                lp += math.log(prob)
            logp[cand] = lp
        mx = max(logp.values())
        post = {k: math.exp(v - mx) for k, v in logp.items()}
        z = sum(post.values())
        post = {k: v / z for k, v in post.items()}
        best = max(post, key=post.get)
        recon.append(best)
        ent_sum += -sum(v * math.log(v) for v in post.values() if v > 0)
    return tuple(s for s in recon if s != "<DEL>"), ent_sum / max(len(obs), 1)


def fdist(a, b):
    return dist.feature_edit_distance("".join(a), "".join(b))


def main():
    out = Path(__file__).parent / "results"
    print("=" * 64)
    print("POC-5: 베이지안 재구 (로망스→라틴, Phase 0)")
    print("=" * 64)
    sets = get_cognsets()
    random.shuffle(sets)
    split = int(len(sets) * 0.7)
    train, test = sets[:split], sets[split:]
    print(f"동원어셋: {len(sets)} (train {len(train)} / test {len(test)})")
    cov = Counter(l for _, ds in sets for l in ds)
    print("daughter 커버리지:", dict(cov))

    fwd = learn_channel(train)
    latin_vocab = set()
    for latin, _ in train:
        latin_vocab |= set(ft.ipa_segs(latin))

    # anchor = 훈련상 gold에 가장 가까운(보수적) 언어
    anchor_score = {}
    for lang in TARGETS:
        ds = [(la, d[lang]) for la, d in train if lang in d]
        if ds:
            anchor_score[lang] = sum(fdist(ft.ipa_segs(la), ft.ipa_segs(d)) for la, d in ds) / len(ds)
    anchor = min(anchor_score, key=anchor_score.get)
    print(f"anchor(최보수 daughter) = {anchor}  (평균거리 {anchor_score[anchor]:.2f})")
    print("-" * 64)

    # baseline: anchor 그대로를 라틴으로
    base_d = []
    for latin, ds in test:
        if anchor in ds:
            base_d.append(fdist(ft.ipa_segs(ds[anchor]), ft.ipa_segs(latin)))
    base_mean = sum(base_d) / len(base_d) if base_d else float("nan")
    print(f"baseline (anchor '{anchor}' 그대로): 평균 자질거리 {base_mean:.3f}")
    print("-" * 64)

    rows = ["n_daughters\tmean_dist\texact\tmean_entropy"]
    print(f"{'#daughters':>11}{'mean_dist':>11}{'exact':>8}{'mean_H':>9}")
    for k in [1, 2, 3, 99]:
        dtot = etot = exact = nval = 0.0
        for latin, ds in test:
            sub = dict(list(ds.items())[:k]) if k < 99 else ds
            if not sub:
                continue
            rec, ent = reconstruct(sub, fwd, latin_vocab, anchor)
            dtot += fdist(rec, ft.ipa_segs(latin))
            etot += ent
            exact += (rec == tuple(ft.ipa_segs(latin)))
            nval += 1
        kk = "all" if k == 99 else k
        print(f"{str(kk):>11}{dtot/nval:>11.3f}{exact/nval:>8.2f}{etot/nval:>9.3f}")
        rows.append(f"{kk}\t{dtot/nval:.4f}\t{exact/nval:.4f}\t{etot/nval:.4f}")

    (out / "poc5_results.tsv").write_text("\n".join(rows), encoding="utf-8")
    print("-" * 64)
    # 판정
    d_all = float(rows[-1].split("\t")[1])
    d_1 = float(rows[1].split("\t")[1])
    print(f"판정: 재구(all) {d_all:.3f} vs baseline {base_mean:.3f} "
          f"→ {'재구 우월' if d_all < base_mean else '개선 없음'}")
    print(f"      자매어 효과: 거리 {d_1:.3f}(1) → {d_all:.3f}(all) "
          f"{'(개선)' if d_all < d_1 else '(없음)'}")


if __name__ == "__main__":
    main()
