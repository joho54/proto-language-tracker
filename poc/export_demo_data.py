"""Falsifier Playground — 단어쌍만 bake (빌드타임).

★라이브 실행판: MI·순열·정렬은 *브라우저 JS가 라이브로* 돈다(app.js). 여기선 *단어쌍만* 추출해
web/data/presets/*.json 으로 굽는다(SPEC §3.2 축소판: pairs + meta, 통계는 클라이언트가 계산).
데이터(kaikki, gitignored)는 여기서만 읽음. perm 없으니 빠름.
"""
import json, random
from collections import defaultdict
from pathlib import Path
import falsifier_core as fc
from kaikki import cognate_sets

random.seed(22)
ROOT = Path(__file__).resolve().parent.parent
KA = ROOT / "data" / "kaikki"
OUT = ROOT / "web" / "data" / "presets"
OUT.mkdir(parents=True, exist_ok=True)
BAKE = 120        # 라이브 계산·표시용 쌍 수
NPERM = 500       # JS가 돌릴 순열 수(제안)
HORIZON = 18

def log(*a): print(*a, flush=True)

def load_korean():
    ko_all = defaultdict(list); catalog = set()
    for line in open(KA / "korean.jsonl", encoding="utf-8"):
        e = json.loads(line)
        if e.get("lang_code") != "ko":
            continue
        w = e.get("word", "")
        if len(w) == 1 and "一" <= w <= "鿿":
            for h in e.get("head_templates", []):
                if h.get("name", "").startswith("ko-hanja"):
                    ar = h.get("args", {}); ks = sorted((k for k in ar if k.isdigit()), key=int)
                    if ks and len(ar[ks[-1]]) == 1 and "가" <= ar[ks[-1]] <= "힣":
                        catalog.add(ar[ks[-1]])
        if w and all("가" <= c <= "힣" for c in w):
            for s in e.get("senses", []):
                for g in s.get("glosses") or []:
                    c = fc.norm_gloss(g)
                    if c and w not in ko_all[c]:
                        ko_all[c].append(w)
    return ko_all, catalog

def load_proto(path):
    pj = {}
    for line in open(path, encoding="utf-8"):
        e = json.loads(line); w = e.get("word")
        if not w:
            continue
        for s in e.get("senses", []):
            for g in s.get("glosses") or []:
                c = fc.norm_gloss(g)
                if c and (c not in pj or len(w) < len(pj[c])):
                    pj[c] = w
    return pj

def korean_vs_proto(ko_all, catalog, proto_path, strip_sino):
    proto = load_proto(proto_path)
    is_sino = lambda w: all(ch in catalog for ch in w)
    rows = []
    for c in sorted(set(proto) & set(ko_all)):
        cands = ko_all[c]
        if strip_sino:
            cands = [w for w in cands if not is_sino(w)]
        if not cands:
            continue
        kw = min(cands, key=len)
        a, b = fc.roman_phon(proto[c]), fc.hangul_phon(kw)
        if a and b:
            rows.append(dict(concept=c, a_raw=proto[c], b_raw=kw, a=a, b=b))
    return rows

def gmc_confirmed():
    rows = []
    for root, d in cognate_sets("Proto-Germanic", target_codes={"en", "de"}):
        if "en" in d and "de" in d:
            a, b = fc.clean_roman(d["en"]), fc.clean_roman(d["de"])
            if a and b:
                rows.append(dict(concept=root, a_raw=d["en"], b_raw=d["de"], a=a, b=b))
    return rows

def sim(a, b):
    al = fc.align(a, b)
    return (sum(1 for x, y in al if x == y and x is not None) / len(al)) if al else 0.0

def sample(rows, n):
    rows = rows[:]; random.shuffle(rows); return rows[:n]

def preset(rows, pid, label, kind, langA, langB, note, proper=None):
    d = dict(id=pid, label=label, kind=kind, langA=langA, langB=langB,
             n=len(rows), nperm=NPERM, horizon=HORIZON,
             pairs=[{"concept": r["concept"], "a_raw": r["a_raw"], "b_raw": r["b_raw"],
                     "a": r["a"], "b": r["b"]} for r in rows], note=note)
    if proper is not None:   # cherry: 선택 안 한 전체 모집단(proper null 시연용)
        d["proper"] = [{"a": r["a"], "b": r["b"]} for r in proper]
    return d

def main():
    log("Korean 로딩…")
    ko_all, catalog = load_korean()
    presets = []
    def add(t):
        (OUT / f"{t['id']}.json").write_text(json.dumps(t, ensure_ascii=False, indent=1), encoding="utf-8")
        presets.append({"id": t["id"], "label": t["label"], "kind": t["kind"], "file": f"{t['id']}.json"})
        log(f"  [{t['id']}] {len(t['pairs'])} pairs")

    add(preset(sample(gmc_confirmed(), BAKE), "confirmed-gmc",
               "Confirmed cognates · English ↔ German", "confirmed", "English", "German",
               "Sisters sharing one ancestor (Proto-Germanic). Systematic sound correspondences → high MI, tiny p."))
    kj = korean_vs_proto(ko_all, catalog, KA / "protojaponic.jsonl", strip_sino=True)
    add(preset(sample(kj, BAKE), "kor-jpn-native",
               "Korean ↔ Japanese (native layer)", "claim", "proto-Japonic", "Korean",
               "The Robbeets-style genealogy claim, Sino loans removed. Signal hovers near the floor."))
    ur = korean_vs_proto(ko_all, catalog, KA / "protouralic.jsonl", strip_sino=True)
    add(preset(sample(ur, BAKE), "unrelated-uralic",
               "Unrelated control · Korean ↔ Uralic", "control", "proto-Uralic", "Korean",
               "Korean vs an UNRELATED but typologically similar family. If it scores like Korean-Japanese, the signal is typology, not kinship."))
    ie = korean_vs_proto(ko_all, catalog, KA / "protoindoeuropean.jsonl", strip_sino=True)
    ie_full = sample(ie, BAKE)                       # 선택 안 한 모집단 = proper null
    ie.sort(key=lambda r: -sim(r["a"], r["b"]))
    add(preset(ie[:40], "cherry-lookalike",
               "Cherry-picked lookalikes (a trap)", "cherry", "proto-Indo-European", "Korean",
               "Unrelated (IE) pairs, but keeping only the ones that LOOK similar. The test 'detects' — but that's the trap: the signal is the selection, not the languages.",
               proper=ie_full))

    (OUT / "index.json").write_text(json.dumps({"presets": presets}, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"[완료] {len(presets)} 프리셋")

if __name__ == "__main__":
    main()
