"""POC-17(a)-fix: M1 카탈로그 끌림으로 불균형서 한자어 탐지 (배치가능 분리기).

POC-17(a)에서 naive 비지도 EM은 자연 불균형(83/17)서 majority-sino로 붕괴했다. 여기선
POC-15의 M1(카탈로그 끌림)을 한국어에 적용: **한자 음가 사전(Sino 음절 카탈로그)** 으로
"이 단어가 Sino 음절들로만 이뤄졌나"를 끌림 신호로 쓴다.

★ 비순환성: 카탈로그 = 단일 한자 엔트리의 음가(ko-hanja head_template 마지막 인자).
  이는 *사전 사실*(한자의 음)이지 우리가 검증하는 어원 라벨(ko-etym-sino/native)이 아님.
  → 라벨 없는 논쟁 케이스(POC-17b discovery)서도 외부 자원만으로 쓸 수 있는 도구.

신호:
  - sino_frac = 단어의 한글 음절 중 Sino-음절 카탈로그에 든 비율.
  - 결합: sino_frac ⊕ phonotactic LLR(계승 vs 차용 bigram) — POC-15식 융합.
평가(자연 불균형, balancing 없음): AUC + 최적임계 F1 + "전음절 Sino" 규칙 F1, gold 대조.
출력: poc/results/poc17b.tsv (증분), 로그 flush.
"""
import json, re, math
from collections import Counter
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "kaikki" / "korean.jsonl"
OUT = Path(__file__).parent / "results"


def is_hangul(w):
    return bool(w) and any("가" <= c <= "힣" for c in w) and all("가" <= c <= "힣" for c in w)


def gold_label(e):
    names = [t.get("name", "") for t in e.get("etymology_templates", [])]
    sino = any(n in ("ko-etym-sino", "ko-etym-Sino") for n in names)
    nat = any(n == "ko-etym-native" for n in names)
    if sino and not nat:
        return "sino"
    if nat and not sino:
        return "native"
    return None


def build_catalog_and_data():
    """카탈로그(Sino 음절) + 라벨 데이터(homograph 제거)를 한 번 순회로."""
    catalog = set()
    by_word = {}
    rep = {}
    for line in open(DATA, encoding="utf-8"):
        e = json.loads(line)
        if e.get("lang_code") != "ko":
            continue
        w = e.get("word", "")
        # 1) Sino 음절 카탈로그: 단일 한자 엔트리의 음(ko-hanja head_template 마지막 인자)
        if len(w) == 1 and "一" <= w <= "鿿":
            for h in e.get("head_templates", []):
                if h.get("name", "").startswith("ko-hanja"):
                    args = h.get("args", {})
                    keys = sorted((k for k in args if k.isdigit()), key=int)
                    if keys:
                        eum = args[keys[-1]]   # 마지막 = 음(읽기)
                        if len(eum) == 1 and is_hangul(eum):
                            catalog.add(eum)
        # 2) 라벨 데이터 (한글 단어만)
        g = gold_label(e)
        if g is None or not is_hangul(w):
            continue
        by_word.setdefault(w, set()).add(g)
        rep[(w, g)] = True
    homo = {w for w, labs in by_word.items() if len(labs) > 1}
    data = [(w, g) for (w, g) in rep if w not in homo]
    return catalog, data, len(homo)


def auc(scores, labels, pos="sino"):
    """Mann-Whitney AUC (pos=sino 점수가 클수록 sino일 확률↑)."""
    pos_s = [s for s, l in zip(scores, labels) if l == pos]
    neg_s = [s for s, l in zip(scores, labels) if l != pos]
    if not pos_s or not neg_s:
        return float("nan")
    # rank-based
    allv = sorted(set(scores))
    rank = {v: i for i, v in enumerate(sorted(scores))}  # placeholder
    # 직접 비교 (작은 데이터라 O(n*m) 허용 가능하나 큰 경우 정렬법)
    paired = sorted(zip(scores, labels))
    # 효율적 AUC: 정렬 후 누적
    n_pos = len(pos_s); n_neg = len(neg_s)
    s_sorted = sorted(zip(scores, labels))
    rank_sum = 0.0
    i = 0; r = 1
    while i < len(s_sorted):
        j = i
        while j < len(s_sorted) and s_sorted[j][0] == s_sorted[i][0]:
            j += 1
        avg_rank = (r + (r + (j - i) - 1)) / 2.0
        for k in range(i, j):
            if s_sorted[k][1] == pos:
                rank_sum += avg_rank
        r += (j - i)
        i = j
    return (rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def best_f1(scores, labels, pos="sino"):
    """임계 스윕 최적 F1 (자연 불균형)."""
    cand = sorted(set(scores))
    best = (0, None)
    for th in cand:
        tp = sum(1 for s, l in zip(scores, labels) if s >= th and l == pos)
        fp = sum(1 for s, l in zip(scores, labels) if s >= th and l != pos)
        fn = sum(1 for s, l in zip(scores, labels) if s < th and l == pos)
        prec = tp / (tp + fp) if tp + fp else 0
        rec = tp / (tp + fn) if tp + fn else 0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
        if f1 > best[0]:
            best = (f1, (th, prec, rec))
    return best


def bigrams(s):
    s = "^" + s + "$"
    return [s[i:i+2] for i in range(len(s) - 1)]


def main():
    print("=" * 64, flush=True)
    print("POC-17(a)-fix: M1 카탈로그 끌림으로 불균형서 한자어 탐지", flush=True)
    print("=" * 64, flush=True)
    catalog, data, n_homo = build_catalog_and_data()
    cnt = Counter(g for _, g in data)
    N = len(data)
    print(f"Sino 음절 카탈로그: {len(catalog)}개 (단일 한자 음가, 어원라벨과 독립)", flush=True)
    print(f"라벨 데이터: {N} (homo {n_homo} 제거)  {dict(cnt)}  sino비율 {cnt['sino']/N:.3f}", flush=True)

    # --- 신호 1: sino_frac (음절 카탈로그 멤버십) ---
    def sino_frac(w):
        return sum(1 for c in w if c in catalog) / len(w)
    frac = [sino_frac(w) for w, _ in data]
    labels = [g for _, g in data]

    a1 = auc(frac, labels)
    f1_frac, info_frac = best_f1(frac, labels)
    # "전음절 Sino" 규칙
    allin = [1.0 if sino_frac(w) == 1.0 else 0.0 for w, _ in data]
    tp = sum(1 for s, l in zip(allin, labels) if s == 1 and l == "sino")
    fp = sum(1 for s, l in zip(allin, labels) if s == 1 and l != "sino")
    fn = sum(1 for s, l in zip(allin, labels) if s == 0 and l == "sino")
    p_all = tp / (tp + fp) if tp + fp else 0
    r_all = tp / (tp + fn) if tp + fn else 0
    f1_all = 2 * p_all * r_all / (p_all + r_all) if p_all + r_all else 0

    print("-" * 64, flush=True)
    print("[1] sino_frac (카탈로그 멤버십) — 자연 불균형, balancing 없음", flush=True)
    print(f"  AUC {a1:.3f}", flush=True)
    print(f"  최적임계 F1 {f1_frac:.3f}  (th={info_frac[0]:.2f} P {info_frac[1]:.3f} R {info_frac[2]:.3f})", flush=True)
    print(f"  '전음절 Sino' 규칙: F1 {f1_all:.3f} (P {p_all:.3f} R {r_all:.3f})", flush=True)

    # --- 신호 2: 융합 (sino_frac + phonotactic LLR), gold로 LM 적합은 안 함 →
    #     비지도: sino_frac>=0.999 를 seed로 차용층 정의 후 두 bigram LM 부트스트랩 (POC-15식) ---
    seed_sino = [w for w, _ in data if sino_frac(w) >= 0.999]
    seed_nat = [w for w, _ in data if sino_frac(w) < 0.5]
    vocab = set(bg for w, _ in data for bg in bigrams(w))
    V = len(vocab)

    def fit(words):
        c = Counter(bg for w in words for bg in bigrams(w))
        return c, sum(c.values())

    cs, ts = fit(seed_sino)
    cn, tn_ = fit(seed_nat)

    def llr(w):  # >0 → sino 쪽
        bg = bigrams(w)
        ls = sum(math.log((cs[b] + 0.5) / (ts + 0.5 * V)) for b in bg)
        ln = sum(math.log((cn[b] + 0.5) / (tn_ + 0.5 * V)) for b in bg)
        return (ls - ln) / len(bg)   # 길이정규화

    fused = [0.5 * sino_frac(w) + 0.5 * (1 / (1 + math.exp(-llr(w)))) for w, _ in data]
    a2 = auc(fused, labels)
    f1_fu, info_fu = best_f1(fused, labels)
    print("-" * 64, flush=True)
    print(f"[2] 융합 (카탈로그 frac ⊕ 부트스트랩 phonotactic LLR; seed sino={len(seed_sino)} nat={len(seed_nat)})", flush=True)
    print(f"  AUC {a2:.3f}  최적임계 F1 {f1_fu:.3f} (th={info_fu[0]:.2f} P {info_fu[1]:.3f} R {info_fu[2]:.3f})", flush=True)

    OUT.mkdir(exist_ok=True)
    with open(OUT / "poc17b.tsv", "w", encoding="utf-8") as f:
        f.write("signal\tauc\tf1\tprecision\trecall\n")
        f.write(f"sino_frac\t{a1:.4f}\t{f1_frac:.4f}\t{info_frac[1]:.4f}\t{info_frac[2]:.4f}\n")
        f.write(f"all_syllable_sino\t\t{f1_all:.4f}\t{p_all:.4f}\t{r_all:.4f}\n")
        f.write(f"fused\t{a2:.4f}\t{f1_fu:.4f}\t{info_fu[1]:.4f}\t{info_fu[2]:.4f}\n")
        f.write(f"# catalog={len(catalog)} N={N} sino_ratio={cnt['sino']/N:.4f}\n")

    print("-" * 64, flush=True)
    # 배치 지표 = 자연 불균형서의 F1 (frac은 거의 이산 → AUC는 과소평가, F1/융합AUC가 실제 지표)
    ok = f1_all > 0.85 and a2 > 0.85
    print(f"판정: 카탈로그 M1이 자연 불균형서 작동={'✓' if ok else '✗'}  "
          f"전음절-Sino F1 {f1_all:.3f}≈지도 0.951, 융합 AUC {a2:.3f} (naive EM은 붕괴=majority).", flush=True)
    print("주의: 여전히 validation. 카탈로그(한자음가)는 어원라벨과 독립이라 discovery(라벨없음)서 재사용 가능.", flush=True)


if __name__ == "__main__":
    main()
