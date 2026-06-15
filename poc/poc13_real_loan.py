"""POC-13 (Tier-2, 실데이터): 형태만으로 차용 탐지 — Maltese gold 어원 대조.

합성(POC-12)의 한계(내가 차용을 심음)를 닫는다: 실제 Maltese 단어의 형태(IPA)만 보고
차용(로망스/영어) vs 계승(셈/아랍)을 분류 → kaikki gold 어원 라벨과 대조.
탐지되면 = 일탈(차용)이 실데이터서 형태 서명으로 추적 가능 = 프로젝트 핵심 신규성의 실데이터 traction.

방법: char n-gram(2,3) 다항 나이브베이즈(직접 구현, 의존성 0). 70/30 분할, gold 대조.
출력: poc/results/poc13.tsv
"""
import json, random, math, re
from collections import Counter, defaultdict
from pathlib import Path

random.seed(13)
DATA = Path(__file__).resolve().parent.parent / "data" / "kaikki" / "maltese.jsonl"


def gold_label(e):
    """:bor→borrowed, :inh→inherited. 없으면 None."""
    mark = None
    for t in e.get("etymology_templates", []):
        a = t.get("args", {})
        m = a.get("2", "")
        if m == ":bor" or t.get("name") in ("bor", "bor+", "lbor"):
            return "borrowed"
        if m == ":inh" or t.get("name") == "inh":
            mark = "inherited"
    return mark


def get_ipa(e):
    for s in e.get("sounds", []):
        ip = s.get("ipa")
        if ip:
            return re.sub(r"[/\[\]ˈˌ]", "", ip)
    return None


def ngrams(s, ns=(2, 3)):
    s = "^" + s + "$"
    out = []
    for n in ns:
        for i in range(len(s) - n + 1):
            out.append(s[i:i+n])
    return out


def main():
    out = Path(__file__).parent / "results"
    print("=" * 60, flush=True)
    print("POC-13: 형태만으로 차용 탐지 (Maltese, gold 어원)", flush=True)
    print("=" * 60, flush=True)
    data = []
    for line in open(DATA, encoding="utf-8"):
        e = json.loads(line)
        lab = gold_label(e)
        ipa = get_ipa(e)
        if lab and ipa and len(ipa) >= 2:
            data.append((ipa, lab))
    random.shuffle(data)
    cnt = Counter(l for _, l in data)
    print(f"라벨 있는 단어: {len(data)}  ({dict(cnt)})", flush=True)

    sp = int(len(data) * 0.7)
    train, test = data[:sp], data[sp:]

    # 다항 NB
    cls_ng = {c: Counter() for c in cnt}
    cls_n = Counter()
    vocab = set()
    for form, lab in train:
        g = ngrams(form)
        cls_ng[lab].update(g)
        cls_n[lab] += 1
        vocab.update(g)
    V = len(vocab)
    tot = sum(cls_n.values())
    cls_tot = {c: sum(cls_ng[c].values()) for c in cnt}

    def predict(form):
        g = ngrams(form)
        best, bl = -1e18, None
        for c in cnt:
            lp = math.log(cls_n[c] / tot)
            for ng in g:
                lp += math.log((cls_ng[c][ng] + 0.3) / (cls_tot[c] + 0.3 * V))
            if lp > best:
                best, bl = lp, c
        return bl

    # 평가
    tp = fp = fn = tn = 0
    correct = 0
    for form, lab in test:
        pred = predict(form)
        correct += (pred == lab)
        if lab == "borrowed" and pred == "borrowed": tp += 1
        elif lab != "borrowed" and pred == "borrowed": fp += 1
        elif lab == "borrowed" and pred != "borrowed": fn += 1
        else: tn += 1
    acc = correct / len(test)
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    maj = max(cnt.values()) / len(data)

    print("-" * 60, flush=True)
    print(f"정확도: {acc:.3f}  (다수 baseline {maj:.3f})", flush=True)
    print(f"차용 탐지: precision {prec:.3f}  recall {rec:.3f}  F1 {f1:.3f}", flush=True)
    print(f"혼동: TP {tp} FP {fp} FN {fn} TN {tn}", flush=True)

    # 예시
    print("-" * 60, flush=True)
    print("예측 예시:", flush=True)
    for form, lab in test[:8]:
        print(f"  {form:<14} gold={lab:<10} pred={predict(form)}", flush=True)

    (out / "poc13.tsv").write_text(
        f"acc\tmajority\tprecision\trecall\tf1\n{acc:.4f}\t{maj:.4f}\t{prec:.4f}\t{rec:.4f}\t{f1:.4f}",
        encoding="utf-8")
    print("-" * 60, flush=True)
    v = "형태 신호로 차용 탐지됨 ✓" if (acc > maj + 0.05 and f1 > 0.5) else "신호 약함"
    print(f"판정: {v}", flush=True)


if __name__ == "__main__":
    main()
