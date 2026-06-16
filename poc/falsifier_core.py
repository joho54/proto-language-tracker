"""falsifier 코어 — 데이터 의존 없는 슬림 모듈.

align(NW+panphon) · mutual_info · perm_with_null · coarse 매퍼 · trace 빌더.
export 스크립트(빌드타임)와 잠재적 serverless 함수가 공유. poc17c/poc17e의
중복 정의를 단일 출처로(SPEC §7 리스크 해소). 데이터(kaikki) 로딩은 여기 없음.
"""
import re, random, math, unicodedata
from collections import Counter
import panphon

ft = panphon.FeatureTable()

# ── 분절 정렬 (Needleman-Wunsch, panphon 자질거리) — poc5_reconstruct:61 이식 ──
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

# ── 상호정보량 — poc17c:83 ──
def mutual_info(pairs):
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

# ── 순열 null (분포 반환) — poc17c:99 확장 ──
def perm_with_null(pairs, nperm=2000, seed=17, max_null=400):
    rng = random.Random(seed)
    obs = mutual_info(pairs)
    A = [a for a, _ in pairs]; B = [b for _, b in pairs]
    nulls = []; ge = 0
    for _ in range(nperm):
        Bs = B[:]; rng.shuffle(Bs)
        mi = mutual_info(list(zip(A, Bs)))
        nulls.append(mi)
        if mi >= obs:
            ge += 1
    p = (ge + 1) / (nperm + 1)
    if len(nulls) > max_null:
        step = len(nulls) / max_null
        nulls = [nulls[int(k * step)] for k in range(max_null)]
    return obs, nulls, p

# ── 대응표 (히트맵용) ──
def build_matrix(pairs, top=12):
    joint = Counter(); ma = Counter(); mb = Counter()
    for a, b in pairs:
        for x, y in align(a, b):
            if x is None or y is None:
                continue
            joint[(x, y)] += 1; ma[x] += 1; mb[y] += 1
    rows = [s for s, _ in ma.most_common(top)]
    cols = [s for s, _ in mb.most_common(top)]
    counts = [[joint.get((r, c), 0) for c in cols] for r in rows]
    return rows, cols, counts

# ── 정렬 trace (분절정렬 시각화용) ──
def align_trace(pairs, limit=14):
    out = []
    for i, (a, b) in enumerate(pairs[:limit]):
        out.append({"i": i, "cells": [[x, y] for x, y in align(a, b)]})
    return out

# ── coarse 매퍼 (poc17c:30/46, poc17e:22) ──
_CHO = ["k","k","n","t","t","r","m","p","p","s","s","","t","t","t","k","t","p","h"]
_JUNG = ["a","e","a","e","o","e","o","e","o","a","e","o","o","u","o","e","u","u","u","i","i"]
_JONG = ["","k","k","k","n","n","n","t","r","k","m","p","t","t","p","h","m","p","p","t","t","n","t","t","k","t","p","h"]
def hangul_phon(w):
    out = []
    for ch in w:
        o = ord(ch) - 0xAC00
        if 0 <= o < 11172:
            cho, jung, jong = o // 588, (o % 588) // 28, o % 28
            c = _CHO[cho]
            if c:
                out.append(c)
            out.append(_JUNG[jung])
            j = _JONG[jong]
            if j:
                out.append(j)
    return "".join(out)
def roman_phon(w):
    w = w.lower(); w = re.sub(r"[^a-z]", "", w)
    return w
def clean_roman(w):
    w = unicodedata.normalize("NFKD", w)
    w = "".join(c for c in w if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", w.lower())
def norm_gloss(g):
    g = g.lower().strip()
    g = re.sub(r"^(to |a |an |the )", "", g)
    return re.sub(r"[;,(].*$", "", g).strip()
