"""POC-7 (v3): 어족 간 전이(LOFO) — kaikki 데이터(오프라인, 10~30배).

v2(wikitext, 데이터부족) → v3(kaikki, rate-limit 없음, 구조화 descendants).
변화추출(자질이름 집합)·LOFO·교정 null·Spearman은 v2(poc7_transfer) 재사용.
더 많은 독립 어족 시도. 어족당 엣지 상한으로 균형.
출력: poc/results/poc7_kaikki.tsv  (로그는 unbuffered 파일 기록)
"""
import re, random
from collections import Counter
from pathlib import Path
import poc7_transfer as p7          # changes(), avg_ll(), spearman(), ft, FNAMES
import kaikki
from normalize import normalize_ipa

random.seed(7)
V_FT = p7.ft
EDGE_CAP = 6000                      # 어족당 엣지 상한 (균형·속도)

# 유전적으로 독립된 어족 후보 (kaikki 제목)
CANDIDATES = [
    "Proto-Indo-European", "Proto-Uralic", "Proto-Turkic", "Proto-Japonic",
    "Proto-Dravidian", "Proto-Austronesian", "Proto-Sino-Tibetan",
    "Proto-Semitic", "Proto-Mongolic", "Proto-Tai",
]
LATIN = re.compile(r"[a-zɑ-ʯæœøðθβɣχʃʒŋɲʔ]")


def clean(w):
    w = (w or "").strip().lstrip("*").replace("H", "h")
    w = w.split(",")[0].split(";")[0].strip()
    if not w or " " in w:
        return None
    L = [c for c in w.lower() if c.isalpha()]
    if not L or sum(bool(LATIN.match(c)) for c in L) / len(L) < 0.7:
        return None                  # native script 제외(IPA 파싱 불가)
    return normalize_ipa(w)[0]


def family_tokens(fam):
    """fam의 모든 엣지에서 자질-변화 토큰. 실패(404)면 None."""
    try:
        entries = list(kaikki.load(fam))
    except Exception as e:
        print(f"  {fam}: 로드 실패 {type(e).__name__}", flush=True)
        return None
    edges = []
    for e in entries:
        for parent, child, code in kaikki.edges_of(e):
            p, d = clean(parent), clean(child)
            if p and d and p != d:
                edges.append((p, d))
    if len(edges) > EDGE_CAP:
        edges = random.sample(edges, EDGE_CAP)
    toks = []
    for p, d in edges:
        toks += p7.changes(p, d)
    return edges, toks


def main():
    out = Path(__file__).parent / "results"
    print("=" * 70, flush=True)
    print("POC-7 v3: 어족 간 전이(LOFO) — kaikki 오프라인 데이터", flush=True)
    print("=" * 70, flush=True)
    fam_tokens = {}
    for fam in CANDIDATES:
        r = family_tokens(fam)
        if not r:
            continue
        edges, toks = r
        if len(toks) < 200:
            print(f"{fam:<22} 토큰 부족({len(toks)}) — 제외", flush=True)
            continue
        fam_tokens[fam] = toks
        print(f"{fam:<22} 엣지={len(edges):>6} 변화토큰={len(toks):>6} 고유={len(set(toks)):>4}",
              flush=True)

    vocab = set().union(*[set(t) for t in fam_tokens.values()])
    V = len(vocab)
    print(f"어족 수={len(fam_tokens)}  전역 고유 변화유형={V}", flush=True)
    print("-" * 70, flush=True)

    rows = ["held_out\tn_tok\tLL_others\tLL_within\tLL_null\tSpearman\tperm_p\ttransfer"]
    print(f"{'held-out':<22}{'tok':>7}{'LL_타':>9}{'LL_자기':>9}{'LL_null':>9}"
          f"{'Spear':>7}{'perm_p':>8}{'판정':>7}", flush=True)
    for fam in fam_tokens:
        test = fam_tokens[fam]
        others = [t for f2 in fam_tokens if f2 != fam for t in fam_tokens[f2]]
        oc = Counter(others); ot = sum(oc.values())
        ll_o = p7.avg_ll(test, oc, ot, V)
        half = len(test) // 2
        wc = Counter(test[:half])
        ll_w = p7.avg_ll(test[half:], wc, sum(wc.values()), V)
        nc = Counter({v: 1 for v in vocab})
        ll_n = p7.avg_ll(test, nc, V, V)
        sp = p7.spearman(Counter(test), oc)
        # 교정 null: others 빈도형태 보존 + 유형라벨 셔플
        keys = list(vocab); vals = [oc.get(k, 0) for k in keys]
        ge = 0; NPERM = 300
        for _ in range(NPERM):
            random.shuffle(vals)
            sc = Counter(dict(zip(keys, vals)))
            if p7.avg_ll(test, sc, sum(sc.values()), V) >= ll_o:
                ge += 1
        perm_p = (ge + 1) / (NPERM + 1)
        verdict = "도움" if (ll_o > ll_n and perm_p < 0.05) else ("해악" if ll_o < ll_n else "무익")
        print(f"{fam:<22}{len(test):>7}{ll_o:>9.3f}{ll_w:>9.3f}{ll_n:>9.3f}"
              f"{sp:>7.2f}{perm_p:>8.3f}{verdict:>7}", flush=True)
        rows.append(f"{fam}\t{len(test)}\t{ll_o:.4f}\t{ll_w:.4f}\t{ll_n:.4f}\t"
                    f"{sp:.3f}\t{perm_p:.3f}\t{verdict}")

    (out / "poc7_kaikki.tsv").write_text("\n".join(rows), encoding="utf-8")
    print("-" * 70, flush=True)
    print("도움=타어족 prior가 null보다 유의 우월. 출력: poc7_kaikki.tsv", flush=True)


if __name__ == "__main__":
    main()
