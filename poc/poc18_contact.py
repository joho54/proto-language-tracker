"""POC-18 (방향 A de-risk): Transeurasian 유사성 = 계보 vs 접촉 — 지리 감쇠 서명.

가설: Koreanic·Japonic·Turkic·Mongolic·Tungusic·Uralic의 유사성이
  - *계보(공통조상)*면 → 어족 내부 규칙적, 어족-간엔 거의 없음(있어도 지리 무관).
  - *접촉(areal)*면 → **어족-간 유사도가 지리적 근접에 집중**(거리에 따라 감쇠) = 접촉 서명.

검정: ASJP 기초어휘(100개념)로 언어쌍 어휘유사도(1 - 정규화 Levenshtein, ASJP LDN 표준).
  - **어족-간(cross-family)** 쌍만 골라 유사도 vs 지리거리 Spearman + Mantel 순열 null.
  - 대조: ① 어족-내(within) = 계보 참조 ② 무관 대조지역(예: Atlantic-Congo) 같은 검정 →
    지리감쇠가 Transeurasian-zone 특이적인지(접촉) 보편 아티팩트인지.
  - 유형론 통제: 유사도가 음절구조 유사면 거리무관 평평해야 함 → 거리감쇠가 곧 접촉증거.
출력: poc/results/poc18.tsv (증분), 로그 flush.
"""
import csv, math, random
from collections import defaultdict
from pathlib import Path

random.seed(18)
ASJP = Path(__file__).resolve().parent.parent / "data" / "asjp"
OUT = Path(__file__).parent / "results"


def load_langs():
    L = {}
    with open(ASJP / "languages.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                lat, lon = float(r["Latitude"]), float(r["Longitude"])
            except (ValueError, TypeError):
                continue
            L[r["ID"]] = dict(name=r["Name"], fam=r["Family"], area=r["Macroarea"], lat=lat, lon=lon)
    return L


def load_forms(keep_ids):
    """language → {concept: segment_string}. 한 개념 여러 form이면 첫 번째."""
    F = defaultdict(dict)
    with open(ASJP / "forms.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            lid = r["Language_ID"]
            if lid not in keep_ids:
                continue
            c = r["Parameter_ID"]
            seg = r["Segments"].replace(" ", "")
            if c not in F[lid] and seg:
                F[lid][c] = seg
    return F


def ldn(a, b):
    """정규화 Levenshtein 거리 (ASJP LDN)."""
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return 1.0
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        for j in range(1, lb + 1):
            cur[j] = min(prev[j] + 1, cur[j-1] + 1, prev[j-1] + (a[i-1] != b[j-1]))
        prev = cur
    return prev[lb] / max(la, lb)


def sim(fa, fb):
    """두 언어 공유개념 평균 (1-LDN). 공유<10이면 None."""
    shared = set(fa) & set(fb)
    if len(shared) < 10:
        return None, 0
    s = sum(1 - ldn(fa[c], fb[c]) for c in shared) / len(shared)
    return s, len(shared)


def haversine(a, b):
    R = 6371.0
    p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
    dlat = p2 - p1
    dlon = math.radians(b["lon"] - a["lon"])
    h = math.sin(dlat/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlon/2)**2
    return 2 * R * math.asin(min(1, math.sqrt(h)))


def spearman(xs, ys):
    n = len(xs)
    if n < 5:
        return 0.0
    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        rk = [0.0]*n; i = 0
        while i < n:
            j = i
            while j < n and v[order[j]] == v[order[i]]:
                j += 1
            r = (i + j - 1) / 2.0 + 1
            for k in range(i, j):
                rk[order[k]] = r
            i = j
        return rk
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx)/n, sum(ry)/n
    num = sum((rx[i]-mx)*(ry[i]-my) for i in range(n))
    den = math.sqrt(sum((rx[i]-mx)**2 for i in range(n)) * sum((ry[i]-my)**2 for i in range(n)))
    return num/den if den else 0.0


def analyze(label, lang_ids, L, forms, nperm=1000):
    """어족-간 쌍의 유사도 vs (-거리) Spearman + Mantel 순열 + 거리 bin 평균."""
    ids = [i for i in lang_ids if i in forms]
    pairs_sim, pairs_dist, pairs_meta = [], [], []
    within_sim = []
    for i in range(len(ids)):
        for j in range(i+1, len(ids)):
            a, b = ids[i], ids[j]
            s, nsh = sim(forms[a], forms[b])
            if s is None:
                continue
            if L[a]["fam"] == L[b]["fam"]:
                within_sim.append(s)
            else:
                d = haversine(L[a], L[b])
                pairs_sim.append(s); pairs_dist.append(d); pairs_meta.append((a, b))
    if len(pairs_sim) < 20:
        return None
    rho = spearman(pairs_sim, [-d for d in pairs_dist])
    # Mantel 순열: 언어 라벨 셔플 → sim과 dist의 연관 깨기 (간이: dist 리스트 셔플)
    ge = 0
    for _ in range(nperm):
        sh = pairs_dist[:]; random.shuffle(sh)
        if spearman(pairs_sim, [-d for d in sh]) >= rho:
            ge += 1
    p = (ge + 1) / (nperm + 1)
    # 거리 bin 평균
    bins = {"<1000km": [], "1-3000": [], "3-6000": [], ">6000": []}
    for s, d in zip(pairs_sim, pairs_dist):
        k = "<1000km" if d < 1000 else "1-3000" if d < 3000 else "3-6000" if d < 6000 else ">6000"
        bins[k].append(s)
    binmean = {k: (sum(v)/len(v), len(v)) for k, v in bins.items() if v}
    return dict(n_cross=len(pairs_sim), rho=rho, p=p,
                within=sum(within_sim)/len(within_sim) if within_sim else None,
                n_within=len(within_sim), bins=binmean)


def main():
    print("=" * 66, flush=True)
    print("POC-18: Transeurasian 유사성 = 계보 vs 접촉 (지리 감쇠 서명)", flush=True)
    print("=" * 66, flush=True)
    L = load_langs()
    ZONE = {"Koreanic", "Japonic", "Turkic", "Mongolic-Khitan", "Tungusic", "Uralic"}
    zone_ids = [i for i, d in L.items() if d["fam"] in ZONE]
    # 대조지역: *다어족* 대륙 (Africa) — 어족-간 쌍 존재하도록. zone 규모로 표본.
    ctrl_all = [i for i, d in L.items() if d["area"] == "Africa"]
    ctrl_fam_n = len(set(L[i]["fam"] for i in ctrl_all))
    random.Random(18).shuffle(ctrl_all)
    ctrl_ids = ctrl_all[:300]
    print(f"Transeurasian-zone 언어 {len(zone_ids)}({len(ZONE)}어족) | "
          f"대조 Africa 표본 {len(ctrl_ids)}({ctrl_fam_n}어족)", flush=True)

    print("forms 로딩...", flush=True)
    forms = load_forms(set(zone_ids) | set(ctrl_ids))
    print(f"form 보유 {len(forms)}", flush=True)

    OUT.mkdir(exist_ok=True)
    tsv = OUT / "poc18.tsv"
    tsv.write_text("region\tn_cross\trho(sim~-dist)\tp\twithin_fam_sim\tbin_means\n", encoding="utf-8")

    for label, ids in [("Transeurasian-zone", zone_ids), ("대조-AtlanticCongo", ctrl_ids)]:
        print("-" * 66, flush=True)
        print(f"[{label}] 분석...", flush=True)
        r = analyze(label, ids, L, forms)
        if r is None:
            print("  쌍 부족 — 스킵", flush=True)
            continue
        print(f"  어족-간 쌍 N={r['n_cross']}  어족-내 평균유사={r['within']:.3f}(n{r['n_within']})", flush=True)
        print(f"  ★유사도~(-거리) Spearman ρ={r['rho']:.3f}  Mantel p={r['p']:.4f}  "
              f"{'지리감쇠=접촉서명✓' if r['p']<0.05 and r['rho']>0 else '감쇠 없음'}", flush=True)
        bm = "  ".join(f"{k}:{v[0]:.3f}(n{v[1]})" for k, v in r["bins"].items())
        print(f"  거리 bin 평균유사: {bm}", flush=True)
        with open(tsv, "a", encoding="utf-8") as f:
            f.write(f"{label}\t{r['n_cross']}\t{r['rho']:.4f}\t{r['p']:.4f}\t{r['within']:.4f}\t{bm}\n")

    print("=" * 66, flush=True)
    print("판독: zone서 어족-간 유사도가 지리근접에 집중(ρ>0,p<.05)하고 대조지역엔 약하면", flush=True)
    print("      → Transeurasian 유사성에 *접촉* 성분 실재 = 방향 A 신호 있음(양성 발견 씨앗).", flush=True)


if __name__ == "__main__":
    main()
