"""POC-9 (1부): 형태론 레버 — 닫힌 부류가 깊이서 더 잘 보존되나?

가설: 문법/닫힌 부류(bound 형태소·대명사·수사…)는 음운 변화에 더 강건 → 깊이에서 살아남음.
성립하면: 깊은 음운 재구가 막혀도(POC-5b/c) 형태론으로 Phase2 가능.

측정: PIE 트리에서 proto→leaf 정규화 자질거리(=거리/길이). 깊이(트리 레벨)별·부류별 비교.
  닫힌: suffix/prefix/infix/pron/num/det/particle/conj  (bound 형태소 포함)
  열린: root/noun/verb/adj/adv
판정: 닫힌 부류의 정규화 변화 < 열린 부류 (특히 깊은 레벨에서) → 레버 성립.
출력: poc/results/poc9.tsv  (unbuffered)
"""
import re
from collections import defaultdict
from pathlib import Path
from poc5b_reconstruct import clean
from poc5_reconstruct import fdist, ft
import kaikki

CLOSED = {"suffix", "prefix", "infix", "pron", "num", "det", "particle", "conj", "adp", "prep"}
BOUND = {"suffix", "prefix", "infix"}
OPEN = {"root", "noun", "verb", "adj", "adv"}
LATIN = re.compile(r"[a-zɑ-ʯæœøðθβɣχʃʒŋɲʔ]")


def leaves(entry):
    """(leaf_word, depth) 말단 노드들 (Latin표기)."""
    out = []

    def walk(nodes, d):
        for nd in nodes or []:
            sub = nd.get("descendants")
            if sub:
                walk(sub, d + 1)
            else:
                w = clean(nd.get("word"))
                if w:
                    out.append((w, d))
    walk(entry.get("descendants"), 1)
    return out


def main():
    out = Path(__file__).parent / "results"
    print("=" * 60, flush=True)
    print("POC-9: 형태론 레버 — 닫힌 vs 열린 부류 보존 (PIE 트리)", flush=True)
    print("=" * 60, flush=True)

    # cls -> depthbin -> [d_norm]
    acc = defaultdict(lambda: defaultdict(list))
    countpos = defaultdict(int)
    for e in kaikki.load("Proto-Indo-European"):
        pos = e.get("pos", "?")
        if pos in CLOSED:
            cls = "닫힘(grammatical)"
        elif pos in OPEN:
            cls = "열림(lexical)"
        else:
            continue
        proto = clean(e.get("word"))
        if not proto:
            continue
        countpos[pos] += 1
        ps = ft.ipa_segs(proto)
        for w, depth in leaves(e):
            ws = ft.ipa_segs(w)
            denom = max(len(ps), len(ws), 1)
            dn = fdist(ps, ws) / denom
            bin_ = "얕음(d1-2)" if depth <= 2 else ("중간(d3-4)" if depth <= 4 else "깊음(d5+)")
            acc[cls][bin_].append(dn)
            acc[cls]["전체"].append(dn)
        # bound 형태소 따로
        if pos in BOUND:
            for w, depth in leaves(e):
                ws = ft.ipa_segs(w)
                dn = fdist(ps, ws) / max(len(ps), len(ws), 1)
                acc["bound형태소"][("얕음(d1-2)" if depth <= 2 else "중간(d3-4)" if depth <= 4 else "깊음(d5+)")].append(dn)
                acc["bound형태소"]["전체"].append(dn)

    bins = ["얕음(d1-2)", "중간(d3-4)", "깊음(d5+)", "전체"]
    print(f"{'부류':<20}" + "".join(f"{b:>13}" for b in bins), flush=True)
    rows = ["cls\t" + "\t".join(bins)]
    for cls in ["열림(lexical)", "닫힘(grammatical)", "bound형태소"]:
        cells = []
        for b in bins:
            v = acc[cls][b]
            cells.append(f"{sum(v)/len(v):.3f}(n{len(v)})" if v else "-")
        print(f"{cls:<20}" + "".join(f"{c:>13}" for c in cells), flush=True)
        rows.append(cls + "\t" + "\t".join(
            (f"{sum(acc[cls][b])/len(acc[cls][b]):.4f}" if acc[cls][b] else "") for b in bins))

    (out / "poc9.tsv").write_text("\n".join(rows), encoding="utf-8")
    print("-" * 60, flush=True)
    # 판정: 깊음 구간에서 닫힘 < 열림 ?
    def mean(cls, b):
        v = acc[cls][b]
        return sum(v) / len(v) if v else float("nan")
    for b in ["얕음(d1-2)", "깊음(d5+)", "전체"]:
        o, c = mean("열림(lexical)", b), mean("닫힘(grammatical)", b)
        print(f"[{b}] 열림 {o:.3f} vs 닫힘 {c:.3f} → "
              f"{'닫힘이 더 보존 ✓' if c < o else '차이 없음/역전'}", flush=True)


if __name__ == "__main__":
    main()
