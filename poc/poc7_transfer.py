"""POC-7 (v2): 어족 간 전이(LOFO) 실데이터 검증 — 배치+중첩트리+증량.

하중 가정: IE에서 배운 "음변화 자연성 prior"가 다른 어족에 전이되나?
v1 실패(데이터 부족) → v2: 배치페처, 중첩 descendants 트리의 모든 parent→child 엣지 추출,
어족당 200 lemma, 거친 자질변화 표현(변경된 자질이름 집합), 라벨순열검정.

변화 표현: 정렬된 (proto_seg, daughter_seg)에서 값이 바뀐 distinctive feature의 '이름 집합'.
  예: p→f, k→x 둘 다 {continuant} (인벤토리 독립) → 어족 간 풀링 가능 = 진짜 universal 검정.

판정: LL(타어족) > LL(shuffle null) = 전이 도움. 라벨순열로 유의성. Spearman으로 분포 일치.
출력: poc/results/poc7_lofo.tsv
"""
import re, math, random
from collections import Counter
from pathlib import Path
import panphon
from normalize import normalize_ipa
from wikt import cat_members, fetch_many

random.seed(7)
ft = panphon.FeatureTable()
FNAMES = ft.names
N_LEMMA = 200

FAMILIES = {
    "IE":      "Proto-Indo-European lemmas",
    "Uralic":  "Proto-Uralic lemmas",
    "Austro":  "Proto-Austronesian lemmas",
    "Japonic": "Proto-Japonic lemmas",
    "Turkic":  "Proto-Turkic lemmas",
}
LATIN = re.compile(r"[a-zɑ-ʯæœøðθβɣχʃʒŋɲʔ]")
# 중첩 줄 파서: 선두 * 깊이 + {{desc/desctree/l|code|form|...}}
LINE_RE = re.compile(r"^(\*+)\s*\{\{(?:desc(?:tree)?|l)\|([a-z0-9-]+)\|([^|}]*)([^}]*)\}\}")


def clean(form):
    f = form.strip().lstrip("*").replace("[[", "").replace("]]", "").replace("H", "h")
    f = f.split("|")[0].split("<")[0].strip()
    return normalize_ipa(f)[0] if f else None


def latinish(s):
    L = [c for c in s.lower() if c.isalpha()]
    return bool(L) and sum(bool(LATIN.match(c)) for c in L) / len(L) > 0.7


def usable(form, rest):
    m = re.search(r"tr=([^|}]+)", rest)
    if m:
        return clean(m.group(1))
    if latinish(form):
        return clean(form)
    return None


def edges_from_page(root_form, wikitext):
    """descendants 중첩 트리의 모든 parent→child 엣지 (양쪽 form 사용가능 시)."""
    i = wikitext.lower().find("descendants")
    if i < 0:
        return []
    section = wikitext[i:]
    stack = {0: root_form}      # depth → 정규화 form
    edges = []
    for line in section.splitlines():
        m = LINE_RE.match(line.strip()) or LINE_RE.match(line)
        if not m:
            continue
        depth = len(m.group(1))
        code, form, rest = m.group(2), m.group(3), m.group(4)
        cur = usable(form, rest)
        parent = stack.get(depth - 1)
        if cur:
            stack[depth] = cur
            # 더 깊은 잔존 스택 제거
            for d in list(stack):
                if d > depth:
                    del stack[d]
            if parent and parent != cur:
                edges.append((parent, cur))
        # cur가 없어도(native script) 다음 깊이의 부모가 될 수 있게 form 보존
        elif latinish(form) is False:
            stack[depth] = stack.get(depth, parent)  # 유지
    return edges


def align(p, d):
    ps, ds = ft.ipa_segs(p), ft.ipa_segs(d)
    n, m = len(ps), len(ds)
    if not n or not m:
        return []
    GAP = 0.8

    def vec(s):
        v = ft.word_to_vector_list(s, numeric=True)
        return v[0] if len(v) == 1 else None

    def sub(a, b):
        if a == b:
            return 0.0
        va, vb = vec(a), vec(b)
        if va is None or vb is None:
            return 1.0
        return sum(x != y for x, y in zip(va, vb)) / len(va)

    D = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        D[i][0] = i * GAP
    for j in range(1, m + 1):
        D[0][j] = j * GAP
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i][j] = min(D[i-1][j-1] + sub(ps[i-1], ds[j-1]),
                          D[i-1][j] + GAP, D[i][j-1] + GAP)
    i, j, al = n, m, []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and abs(D[i][j] - (D[i-1][j-1] + sub(ps[i-1], ds[j-1]))) < 1e-9:
            al.append((ps[i-1], ds[j-1])); i -= 1; j -= 1
        elif i > 0 and abs(D[i][j] - (D[i-1][j] + GAP)) < 1e-9:
            al.append((ps[i-1], None)); i -= 1
        else:
            al.append((None, ds[j-1])); j -= 1
    return al[::-1]


def changes(p, d):
    """거친 변화토큰: 변경된 자질 '이름 집합' (값/방향 무시 → 인벤토리 독립)."""
    out = []
    for a, b in align(p, d):
        if a is None or b is None or a == b:
            continue
        va = ft.word_to_vector_list(a, numeric=True)
        vb = ft.word_to_vector_list(b, numeric=True)
        if len(va) != 1 or len(vb) != 1:
            continue
        names = frozenset(FNAMES[k] for k in range(len(va[0])) if va[0][k] != vb[0][k])
        if names:
            out.append(names)
    return out


def avg_ll(test, counter, tot, V):
    if not test:
        return float("nan")
    return sum(math.log((counter.get(t, 0) + 0.5) / (tot + 0.5 * V)) for t in test) / len(test)


def spearman(a, b):
    keys = list(set(a) | set(b))
    ra = {k: i for i, k in enumerate(sorted(keys, key=lambda k: a.get(k, 0)))}
    rb = {k: i for i, k in enumerate(sorted(keys, key=lambda k: b.get(k, 0)))}
    n = len(keys)
    if n < 2:
        return float("nan")
    dsq = sum((ra[k] - rb[k]) ** 2 for k in keys)
    return 1 - 6 * dsq / (n * (n * n - 1))


def main():
    out = Path(__file__).parent / "results"
    print("=" * 66)
    print("POC-7 v2: 어족 간 전이(LOFO) — 배치+중첩트리+증량")
    print("=" * 66)
    fam_tokens = {}
    for fam, cat in FAMILIES.items():
        titles = cat_members(cat, N_LEMMA)
        pages = fetch_many(titles)
        toks, n_edges = [], 0
        for t in titles:
            root = clean(t.split("/", 1)[1]) if "/" in t else None
            if not root:
                continue
            for p, d in edges_from_page(root, pages.get(t, "")):
                n_edges += 1
                toks += changes(p, d)
        fam_tokens[fam] = toks
        print(f"{fam:<9} lemma={len(titles):>4} 엣지={n_edges:>5} 변화토큰={len(toks):>6} "
              f"고유={len(set(toks)):>4}")

    vocab = set().union(*[set(t) for t in fam_tokens.values()])
    V = len(vocab)
    print(f"전역 고유 변화유형: {V}")
    print("-" * 66)
    rows = ["held_out\tn_tok\tLL_others\tLL_within\tLL_null\tSpearman\tperm_p\ttransfer"]
    print(f"{'held-out':<9}{'tok':>6}{'LL_타':>9}{'LL_자기':>9}{'LL_null':>9}"
          f"{'Spear':>8}{'perm_p':>8}{'판정':>7}")
    for fam in FAMILIES:
        test = fam_tokens[fam]
        if len(test) < 50:
            print(f"{fam:<9}  (데이터 부족 {len(test)} — 스킵)")
            continue
        others = [t for f2 in FAMILIES if f2 != fam for t in fam_tokens[f2]]
        oc = Counter(others); ot = sum(oc.values())
        ll_o = avg_ll(test, oc, ot, V)
        half = len(test) // 2
        wc = Counter(test[:half])
        ll_w = avg_ll(test[half:], wc, sum(wc.values()), V)
        nc = Counter({v: 1 for v in vocab})
        ll_n = avg_ll(test, nc, V, V)
        sp = spearman(Counter(test), oc)
        # 올바른 null: others의 빈도 '형태'(Zipf)는 보존하되 어떤 유형이 어느 빈도인지를
        # 셔플 → "흔한 건 어디서나 흔하다"를 통제. 실제 others가 더 잘 맞으면 진짜 전이.
        keys = list(vocab)
        vals = [oc.get(k, 0) for k in keys]
        ge = 0; NPERM = 300
        for _ in range(NPERM):
            random.shuffle(vals)
            sc = Counter(dict(zip(keys, vals)))
            if avg_ll(test, sc, sum(sc.values()), V) >= ll_o:
                ge += 1
        perm_p = (ge + 1) / (NPERM + 1)
        verdict = "도움" if (ll_o > ll_n and perm_p < 0.05) else (
            "해악" if ll_o < ll_n else "무익")
        print(f"{fam:<9}{len(test):>6}{ll_o:>9.3f}{ll_w:>9.3f}{ll_n:>9.3f}"
              f"{sp:>8.2f}{perm_p:>8.3f}{verdict:>7}")
        rows.append(f"{fam}\t{len(test)}\t{ll_o:.4f}\t{ll_w:.4f}\t{ll_n:.4f}\t"
                    f"{sp:.3f}\t{perm_p:.3f}\t{verdict}")

    (out / "poc7_lofo.tsv").write_text("\n".join(rows), encoding="utf-8")
    print("-" * 66)
    print("도움=타어족 prior가 null보다 유의하게 우월(전이 성립). 출력: poc7_lofo.tsv")


if __name__ == "__main__":
    main()
