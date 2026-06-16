"""POC-17(e): 확정 동계어 깊이 사다리 — 'blind 반박' (도구 검정력 측정).

17b의 공백: 한국어↔일본어가 무관 대조(Uralic)와 구별 불가 → "신호 0"인지 "도구가 0만 본다(blind)"인지
미상. 이걸 닫으려면 *같은 파이프라인*에 **깊이가 다른 확정(gold) 동계어**를 통과시켜, 알려진 신호가
어디서 우연 floor 아래로 가라앉는지 측정한다.

확정 동계어 = kaikki proto 트리서 같은 조상(같은 PIE/PGmc 어원)을 공유하는 두 자매 = gold cognate.
표기는 전부 로마자(재구 branch-proto·라틴문자 자매)라 17b/c와 동일 파이프라인(분절 MI + 순열 null).

★ 결정적 칸 = 깊은 칸(PIE branch-proto 간, ~5ky = 한-일 주장 깊이). 거기서 p≪0.05·MI≫floor면
  도구는 그 깊이서 *본다* → 한-일이 floor(17b: typed MI 0.52, p≈0.05)에 붙은 건 *대상 탓* = blind 반박.
출력: poc/results/poc17e.tsv (증분), 로그 flush.
"""
import json, re, random, math, unicodedata
from collections import Counter
from pathlib import Path
from poc5_reconstruct import align
from kaikki import cognate_sets

random.seed(17)
OUT = Path(__file__).parent / "results"


def clean(w):
    """로마자/재구표기 → a-z 음소열 (분음부호·라링게알 첨자·기호 제거)."""
    w = unicodedata.normalize("NFKD", w)
    w = "".join(c for c in w if not unicodedata.combining(c))
    w = w.lower()
    w = re.sub(r"[^a-z]", "", w)
    return w


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


def perm_p(pairs, nperm=1000):
    obs = mutual_info(pairs)
    A = [a for a, _ in pairs]; B = [b for _, b in pairs]
    ge = 0
    for _ in range(nperm):
        Bs = B[:]; random.shuffle(Bs)
        if mutual_info(list(zip(A, Bs))) >= obs:
            ge += 1
    return obs, (ge + 1) / (nperm + 1)


def _cap(out, cap):
    if len(out) > cap:
        idx = list(range(len(out))); random.Random(17).shuffle(idx)
        out = [out[i] for i in sorted(idx[:cap])]
    return out


def pairs_for(fam, slug, codeA, codeB, cap=700):
    """proto 트리서 codeA·codeB 둘 다 가진 set = gold cognate 쌍 (자매↔자매)."""
    out = []
    for root, daus in cognate_sets(fam, slug):
        if codeA in daus and codeB in daus:
            a, b = clean(daus[codeA]), clean(daus[codeB])
            if len(a) >= 1 and len(b) >= 1:
                out.append((a, b))
    return _cap(out, cap)


def pairs_root_daughter(fam, slug, code, cap=700):
    """조상 root ↔ 자손 = attested↔proto (한-일 셋업: 모던 한국어↔proto-Japonic과 매칭)."""
    out = []
    for root, daus in cognate_sets(fam, slug):
        if code in daus:
            a, b = clean(root), clean(daus[code])
            if len(a) >= 1 and len(b) >= 1:
                out.append((a, b))
    return _cap(out, cap)


def main():
    print("=" * 70, flush=True)
    print("POC-17(e): 확정 동계어 깊이 사다리 — blind 반박 (검정력)", flush=True)
    print("=" * 70, flush=True)

    # (라벨, fam, slug, codeA, codeB, 대략깊이, 비고)
    RUNGS = [
        ("Germanic en↔de",       "Proto-Germanic", "protogermanic", "en", "de", "~1.5ky", "확정 얕음"),
        ("Germanic ang↔goh",     "Proto-Germanic", "protogermanic", "ang", "goh", "~1.5ky", "확정 고대자매"),
        ("IE itc-pro↔gem-pro",   "Proto-Indo-European", "protoindoeuropean", "itc-pro", "gem-pro", "~5ky", "★확정 깊음(한-일 깊이)"),
        ("IE iir-pro↔grk-pro",   "Proto-Indo-European", "protoindoeuropean", "iir-pro", "grk-pro", "~5.5ky", "★확정 깊음(Graeco-Aryan)"),
        ("IE itc-pro↔iir-pro",   "Proto-Indo-European", "protoindoeuropean", "itc-pro", "iir-pro", "~5.5ky", "★확정 깊음"),
    ]
    # attested↔proto (한-일 셋업 매칭: 한쪽 실증/지저분, 한쪽 깊은 재구)
    RUNGS_RD = [
        ("PGmc root↔en(영어)",   "Proto-Germanic", "protogermanic", "en", "~2ky", "★attested↔proto 얕음"),
        ("PIE root↔la(라틴)",    "Proto-Indo-European", "protoindoeuropean", "la", "~5.5ky", "★attested↔proto 깊음(한-일 매칭)"),
        ("PIE root↔grc(그리스)", "Proto-Indo-European", "protoindoeuropean", "grc", "~5.5ky", "★attested↔proto 깊음"),
    ]
    OUT.mkdir(exist_ok=True)
    tsv = OUT / "poc17e.tsv"
    tsv.write_text("rung\tdepth\tN\tMI\tp_value\tverdict\tnote\n", encoding="utf-8")
    print("참조 floor(17b 무관/한-일 typed): MI≈0.50, p≈0.05\n", flush=True)

    for label, fam, slug, ca, cb, depth, note in RUNGS:
        pairs = pairs_for(fam, slug, ca, cb)
        N = len(pairs)
        if N < 10:
            print(f"[{label:<22}] N={N} 부족 — 스킵", flush=True)
            with open(tsv, "a", encoding="utf-8") as f:
                f.write(f"{label}\t{depth}\t{N}\t\t\tskip\t{note}\n")
            continue
        mi, p = perm_p(pairs)
        # 검정력 판정: floor(p≈0.05, MI≈0.5) 대비 명확 초과인가
        power = p < 0.01 and mi > 0.7
        v = "검정력✓(floor 명확초과)" if power else ("약함" if p < 0.05 else "무유의")
        print(f"[{label:<22}] {depth:<7} N={N:<4} MI={mi:.3f} p={p:.4f}  {v}  ({note})", flush=True)
        with open(tsv, "a", encoding="utf-8") as f:
            f.write(f"{label}\t{depth}\t{N}\t{mi:.4f}\t{p:.4f}\t{v}\t{note}\n")

    print("-" * 70, flush=True)
    print("attested↔proto (한-일 셋업 매칭):", flush=True)
    for label, fam, slug, code, depth, note in RUNGS_RD:
        pairs = pairs_root_daughter(fam, slug, code)
        N = len(pairs)
        if N < 10:
            print(f"[{label:<22}] N={N} 부족 — 스킵", flush=True)
            continue
        mi, p = perm_p(pairs)
        power = p < 0.01 and mi > 0.7
        v = "검정력✓(floor 명확초과)" if power else ("약함" if p < 0.05 else "무유의")
        print(f"[{label:<22}] {depth:<7} N={N:<4} MI={mi:.3f} p={p:.4f}  {v}  ({note})", flush=True)
        with open(tsv, "a", encoding="utf-8") as f:
            f.write(f"{label}\t{depth}\t{N}\t{mi:.4f}\t{p:.4f}\t{v}\t{note}\n")

    print("=" * 70, flush=True)
    print("판독: 깊은 칸(IE branch-proto ~5ky)이 floor 명확초과면 → 도구는 그 깊이서 본다 = blind 반박,", flush=True)
    print("      한-일(17b)이 floor에 붙은 건 대상 탓. 깊은 칸도 floor면 → 파이프라인 무력(강화 선결).", flush=True)


if __name__ == "__main__":
    main()
