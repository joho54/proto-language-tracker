"""POC-17(b)-강화: 공유-Sino 함정 공격적 시연 (모던 Korean↔Japanese).

한자어(Sino-Korean)와 한어(Sino-Japanese)는 *둘 다 중세 중국어 차용* → 같은 개념서 음운 유사
(예: 家族 가족 kajok / kazoku). 안 걷으면 이 **공유 차용**이 가짜 계보 신호를 낸다(Georg 함정).
typed 분해(양쪽 Sino 제거)가 이를 제거하는지 = 방법론의 *양성 통제* 시연.

3 조건, 개념정렬(영어 gloss), coarse 음소 분절 MI + 순열 null(nperm=2000):
  - naive       : 전체 단어(개념당 최단)
  - sino-only   : 양쪽 다 Sino (함정의 출처 — 강한 가짜 대응 예상)
  - native-only : 양쪽 다 고유어 (typed = 함정 제거 후 잔여)
Sino 탐지: Korean=한자 음가 카탈로그(POC-17b), Japanese=어원(Middle Chinese 파생/중국어 차용) vs inh.
출력: poc/results/poc17d.tsv (증분), 로그 flush.
"""
import json, re, random, math
from collections import Counter, defaultdict
from pathlib import Path
from poc5_reconstruct import align

random.seed(17)
DATA = Path(__file__).resolve().parent.parent / "data" / "kaikki"
KO = DATA / "korean.jsonl"
JA = DATA / "japanese.jsonl"
OUT = Path(__file__).parent / "results"

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


# romaji → Korean coarse 음소 집합 {a e i o u k n t r m p s h} 와 동일 알파벳으로 환원
_DIGR = [("sh", "s"), ("ch", "t"), ("ts", "t"), ("ky", "k"), ("gy", "k"), ("ny", "n"),
         ("hy", "h"), ("my", "m"), ("ry", "r"), ("by", "p"), ("py", "p"), ("ju", "tu"),
         ("ja", "ta"), ("jo", "to"), ("ji", "ti"), ("je", "te")]
_SING = {"ō": "o", "ū": "u", "ā": "a", "ē": "e", "ī": "i", "ô": "o", "û": "u",
         "g": "k", "z": "s", "d": "t", "b": "p", "f": "h", "v": "p", "j": "t",
         "c": "k", "l": "r", "q": "k", "x": "s"}


def ja_phon(r):
    r = r.lower().strip()
    r = r.replace("'", "").replace("-", "").replace("ʼ", "")
    for a, b in _DIGR:
        r = r.replace(a, b)
    out = []
    for ch in r:
        if ch in "aeiou":
            out.append(ch)
        elif ch in "kntrmpsh":
            out.append(ch)
        elif ch in _SING:
            out.append(_SING[ch])
        elif ch in "wy":
            continue   # 활음 탈락 (Korean 집합에 없음)
        # else: drop (n', 장음부호 등)
    return "".join(out)


def norm_gloss(g):
    g = g.lower().strip()
    g = re.sub(r"^(to |a |an |the )", "", g)
    g = re.sub(r"[;,(].*$", "", g).strip()
    return g


def basic_concept(c):
    """단일 토큰 gloss만 = 기초어휘 근사 (구-gloss 노이즈·폭증 차단)."""
    return c and " " not in c and c.isalpha() and 2 <= len(c) <= 12


def is_hangul(w):
    return bool(w) and all("가" <= c <= "힣" for c in w)


def build_sino_catalog():
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
                    if keys and len(args[keys[-1]]) == 1 and "가" <= args[keys[-1]] <= "힣":
                        cat.add(args[keys[-1]])
    return cat


def ja_romaji(e):
    for f in e.get("forms", []):
        if "romanization" in (f.get("tags") or []):
            return f.get("form")
    for s in e.get("sounds", []):
        if s.get("roman"):
            return s["roman"]
    return None


def ja_is_sino(e):
    names = [t.get("name", "") for t in e.get("etymology_templates", [])]
    if any(n in ("ltc-l", "och-l", "ltc", "och") for n in names):
        return True
    for t in e.get("etymology_templates", []):
        if t.get("name") in ("bor", "bor+", "der") and t.get("args", {}).get("2") in ("ltc", "och", "zh", "cmn"):
            return True
    return False


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


def perm_p(pairs, nperm=2000):
    obs = mutual_info(pairs)
    A = [a for a, _ in pairs]; B = [b for _, b in pairs]
    ge = 0
    for _ in range(nperm):
        Bs = B[:]; random.shuffle(Bs)
        if mutual_info(list(zip(A, Bs))) >= obs:
            ge += 1
    return obs, (ge + 1) / (nperm + 1)


def main():
    print("=" * 64, flush=True)
    print("POC-17(b)-강화: 공유-Sino 함정 시연 (모던 Korean↔Japanese)", flush=True)
    print("=" * 64, flush=True)
    catalog = build_sino_catalog()
    ko_is_sino = lambda w: all(c in catalog for c in w)
    NPERM = 1000
    print("(쌍 상한 700, nperm 1000)", flush=True)

    # Korean: concept → {'sino':[hangul], 'native':[hangul]}
    ko = defaultdict(lambda: {"sino": [], "native": []})
    for line in open(KO, encoding="utf-8"):
        e = json.loads(line)
        if e.get("lang_code") != "ko":
            continue
        w = e.get("word", "")
        if not is_hangul(w):
            continue
        kind = "sino" if ko_is_sino(w) else "native"
        for s in e.get("senses", []):
            for g in s.get("glosses") or []:
                c = norm_gloss(g)
                if basic_concept(c) and w not in ko[c][kind]:
                    ko[c][kind].append(w)

    # Japanese: concept → {'sino':[romaji], 'native':[romaji]}
    ja = defaultdict(lambda: {"sino": [], "native": []})
    for line in open(JA, encoding="utf-8"):
        e = json.loads(line)
        if e.get("lang_code") != "ja":
            continue
        r = ja_romaji(e)
        if not r:
            continue
        kind = "sino" if ja_is_sino(e) else "native"
        for s in e.get("senses", []):
            for g in s.get("glosses") or []:
                c = norm_gloss(g)
                if basic_concept(c):
                    ja[c][kind].append(r)

    concepts = sorted(set(ko) & set(ja))
    print(f"Sino 카탈로그 {len(catalog)} | 공유 개념 {len(concepts)} | nperm {NPERM}", flush=True)

    MAXPAIRS = 700   # 조건당 쌍 상한 (속도; 결정적 샘플)

    def build(kind_ko, kind_ja):
        """kind in {'sino','native','any'}. any=둘 합쳐 최단."""
        pairs = []; used = []
        for c in concepts:
            kc = ko[c]["sino"] + ko[c]["native"] if kind_ko == "any" else ko[c][kind_ko]
            jc = ja[c]["sino"] + ja[c]["native"] if kind_ja == "any" else ja[c][kind_ja]
            if not kc or not jc:
                continue
            kw = min(kc, key=len)
            jw = min(jc, key=lambda x: len(x))
            a = hangul_phon(kw); b = ja_phon(jw)
            if len(a) >= 1 and len(b) >= 1:
                pairs.append((a, b)); used.append((c, kw, jw))
        if len(pairs) > MAXPAIRS:
            idx = list(range(len(pairs)))
            random.Random(17).shuffle(idx)
            idx = sorted(idx[:MAXPAIRS])
            pairs = [pairs[i] for i in idx]; used = [used[i] for i in idx]
        return pairs, used

    OUT.mkdir(exist_ok=True)
    tsv = OUT / "poc17d.tsv"
    tsv.write_text("condition\tN_pairs\tMI\tp_value\tverdict\n", encoding="utf-8")

    CONDS = [
        ("naive(전체)",      "any", "any"),
        ("sino-only(양쪽한어)", "sino", "sino"),
        ("native-only(typed)", "native", "native"),
    ]
    for name, kk, kj in CONDS:
        pairs, used = build(kk, kj)
        N = len(pairs)
        mi, p = perm_p(pairs, NPERM)
        v = "유의" if p < 0.05 else "무유의"
        print("-" * 64, flush=True)
        print(f"[{name}] N={N}  MI={mi:.4f}  p={p:.4f}  {v}", flush=True)
        print(f"  예시: {used[:8]}", flush=True)
        with open(tsv, "a", encoding="utf-8") as f:
            f.write(f"{name}\t{N}\t{mi:.4f}\t{p:.4f}\t{v}\n")

    print("=" * 64, flush=True)
    print("판독: naive 유의 + sino-only 강유의 + native-only 약화 → 공유-Sino 함정 실재,", flush=True)
    print("      typed 분해가 차용성 가짜 신호 제거 = 방법론 양성통제. (계보 결론은 17b: native도 유형론)", flush=True)


if __name__ == "__main__":
    main()
