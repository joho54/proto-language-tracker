"""POC-17(b) discovery: Koreanic↔Japonic 고유어층 대응 — 명명된 주장 감사.

검증된 분리기(POC-17a/b)를 *명명된 양성주장*(Robbeets류 Koreanic↔Japonic 계보)에 건다.
핵심: 한자어(Sino-Korean)는 중국어 차용 → 안 걷으면 일본어 한어(Sino-Japanese)와의 *공유 차용*이
가짜 계보 신호를 낼 수 있음(Georg 함정, POC-12 합성서 입증). 여기선 실데이터로:
  - naive: Korean 전체 단어 ↔ proto-Japonic, 개념 정렬, 분절 MI + 순열 null.
  - typed: Korean에서 한자어(카탈로그 분리기) 제거한 고유어만 ↔ proto-Japonic.
→ 산출: 두 조건의 p값 + 동원어후보 개수(N) vs 탐지 지평(~15-20쌍, POC-6/11).

★ 정직성: proto-Japonic은 재구 고유어층(한어 적음)이라 Korean측 stripping이 주효. 결과가
  "유의"든 "판정불가+지평"든 *수치로* 보고 = 무가치한 '판정불가 자체'가 아니라 주장의 제약/반증.
출력: poc/results/poc17c.tsv (증분), 로그 flush.
"""
import json, re, random, math
from collections import Counter, defaultdict
from pathlib import Path
from poc5_reconstruct import align

random.seed(17)
KO = Path(__file__).resolve().parent.parent / "data" / "kaikki" / "korean.jsonl"
PJ = Path(__file__).resolve().parent.parent / "data" / "kaikki" / "protojaponic.jsonl"
OUT = Path(__file__).parent / "results"

# --- 한글 → coarse 음소 (proto-Japonic 로마자와 비교가능한 거친 표현) ---
CHO = ["k", "k", "n", "t", "t", "r", "m", "p", "p", "s", "s", "", "t", "t", "t", "k", "t", "p", "h"]
JUNG = ["a", "e", "a", "e", "o", "e", "o", "e", "o", "a", "e", "o", "o", "u", "o", "e", "u", "u", "u", "i", "i"]
JONG = ["", "k", "k", "k", "n", "n", "n", "t", "r", "k", "m", "p", "t", "t", "p", "h", "m", "p", "p", "t", "t", "n", "t", "t", "k", "t", "p", "h"]


def hangul_phon(w):
    out = []
    for ch in w:
        o = ord(ch) - 0xAC00
        if 0 <= o < 11172:
            cho, jung, jong = o // 588, (o % 588) // 28, o % 28
            c = CHO[cho]
            if c:
                out.append(c)
            out.append(JUNG[jung])
            j = JONG[jong]
            if j:
                out.append(j)
    return "".join(out)


def pj_phon(w):
    w = w.lower()
    w = re.sub(r"[^a-z]", "", w)
    return w


def norm_gloss(g):
    g = g.lower().strip()
    g = re.sub(r"^(to |a |an |the )", "", g)
    g = re.sub(r"[;,(].*$", "", g).strip()
    return g


# --- Sino 음절 카탈로그 (POC-17b: 단일 한자 음가, 어원라벨 독립) ---
def build_catalog():
    cat = set()
    for line in open(KO, encoding="utf-8"):
        e = json.loads(line)
        if e.get("lang_code") != "ko":
            continue
        w = e.get("word", "")
        if len(w) == 1 and "一" <= w <= "鿿":
            for h in e.get("head_templates", []):
                if h.get("name", "").startswith("ko-hanja"):
                    args = h.get("args", {})
                    keys = sorted((k for k in args if k.isdigit()), key=int)
                    if keys:
                        eum = args[keys[-1]]
                        if len(eum) == 1 and "가" <= eum <= "힣":
                            cat.add(eum)
    return cat


def is_hangul(w):
    return bool(w) and all("가" <= c <= "힣" for c in w)


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


def perm_p(pairs, nperm=300):
    obs = mutual_info(pairs)
    A = [a for a, _ in pairs]; B = [b for _, b in pairs]
    ge = 0
    for _ in range(nperm):
        Bs = B[:]; random.shuffle(Bs)
        if mutual_info(list(zip(A, Bs))) >= obs:
            ge += 1
    return obs, (ge + 1) / (nperm + 1)


def load_proto(path):
    """proto 조어 파일: concept(norm gloss) → 최단 word."""
    pj = {}
    for line in open(path, encoding="utf-8"):
        e = json.loads(line); w = e.get("word")
        if not w:
            continue
        for s in e.get("senses", []):
            for g in s.get("glosses") or []:
                c = norm_gloss(g)
                if c and (c not in pj or len(w) < len(pj[c])):
                    pj[c] = w
    return pj


def main():
    print("=" * 64, flush=True)
    print("POC-17(b): Koreanic↔Japonic 고유어 대응 + 음성 대조군 [DISCOVERY]", flush=True)
    print("=" * 64, flush=True)
    catalog = build_catalog()
    is_sino = lambda w: all(c in catalog for c in w)
    NPERM = 2000
    HORIZON = 18

    # Korean: concept → [words] (전체 개념)
    ko_all = defaultdict(list)
    for line in open(KO, encoding="utf-8"):
        e = json.loads(line)
        if e.get("lang_code") != "ko":
            continue
        w = e.get("word", "")
        if not is_hangul(w):
            continue
        for s in e.get("senses", []):
            for g in s.get("glosses") or []:
                c = norm_gloss(g)
                if w not in ko_all[c]:
                    ko_all[c].append(w)

    DATA = Path(__file__).resolve().parent.parent / "data" / "kaikki"
    # (라벨, 파일, 관계주장)
    SOURCES = [
        ("Japonic",  DATA / "protojaponic.jsonl",     "★주장(Robbeets Koreanic↔Japonic)"),
        ("Turkic",   DATA / "prototurkic.jsonl",       "Transeurasian 공동주장(참고)"),
        ("Uralic",   DATA / "protouralic.jsonl",       "음성대조(Koreanic-Uralic 주장 없음)"),
        ("IndoEuro", DATA / "protoindoeuropean.jsonl",  "음성대조(명백 무관)"),
    ]

    def build_pairs(proto, concepts, strip_sino):
        pairs = []; used = []
        for c in concepts:
            cands = ko_all[c]
            if strip_sino:
                cands = [w for w in cands if not is_sino(w)]
            if not cands:
                continue
            kw = min(cands, key=len)
            a = pj_phon(proto[c]); b = hangul_phon(kw)
            if len(a) >= 1 and len(b) >= 1:
                pairs.append((a, b)); used.append((c, proto[c], kw))
        return pairs, used

    OUT.mkdir(exist_ok=True)
    tsv = OUT / "poc17c.tsv"
    tsv.write_text("source\tclaim\tcondition\tN_pairs\tMI\tp_value\tverdict\n", encoding="utf-8")
    print(f"Sino 카탈로그 {len(catalog)} | nperm {NPERM} | 지평 D={HORIZON}", flush=True)

    for label, path, claim in SOURCES:
        if not path.exists():
            print(f"[{label}] 파일 없음 — 스킵", flush=True)
            continue
        proto = load_proto(path)
        concepts = sorted(set(proto) & set(ko_all.keys()))
        print("=" * 64, flush=True)
        print(f"[{label}] {claim} | 공유개념 {len(concepts)}", flush=True)
        for cond, strip in [("naive", False), ("typed", True)]:
            pairs, used = build_pairs(proto, concepts, strip)
            N = len(pairs)
            mi, p = perm_p(pairs, NPERM)
            if N < HORIZON:
                v = f"지평아래(N<{HORIZON})"
            elif p < 0.05:
                v = "유의"
            else:
                v = "무유의"
            print(f"  {cond:<6} N={N:<4} MI={mi:.4f} p={p:.4f}  {v}", flush=True)
            if label == "Japonic" and cond == "typed":
                print(f"    예시: {[(c, j, k) for c, j, k in used[:8]]}", flush=True)
            with open(tsv, "a", encoding="utf-8") as f:
                f.write(f"{label}\t{claim}\t{cond}\t{N}\t{mi:.4f}\t{p:.4f}\t{v}\n")

    print("=" * 64, flush=True)
    print("판독: Japonic typed만 유의하고 IndoEuro/Uralic typed는 무유의면 → 진짜 신호.", flush=True)
    print("      대조군도 유의하면 → 파이프라인 아티팩트(coarse 음소/gloss 다의성). 둘 다 *수치*로 정직 보고.", flush=True)


if __name__ == "__main__":
    main()
