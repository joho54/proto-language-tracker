"""Falsifier Playground — 프리셋 trace bake (빌드타임).

falsifier_core를 4 프리셋에 실행 → SPEC §3.2 스키마 JSON으로 web/data/presets/ 에 굽는다.
동일 N(CAP)·nperm으로 apples-to-apples (한-일 floor ≈ 무관 Uralic = 차이가 N 아닌 신호).
데이터(kaikki, gitignored)는 여기서만 읽고, 산출 JSON만 commit/배포.
"""
import json, re, random
from collections import defaultdict
from pathlib import Path
import falsifier_core as fc
from kaikki import cognate_sets

random.seed(22)
ROOT = Path(__file__).resolve().parent.parent
KA = ROOT / "data" / "kaikki"
OUT = ROOT / "web" / "data" / "presets"
OUT.mkdir(parents=True, exist_ok=True)
STAT_CAP = 300   # 통계 쌍 cap(풀셋 가깝게)
DISPLAY = 40     # 화면 표시 쌍
NPERM = 2000
HORIZON = 18

def log(*a): print(*a, flush=True)

# ── Korean: concept→words + sino 카탈로그 ──
def load_korean():
    ko_all = defaultdict(list); catalog = set()
    for line in open(KA / "korean.jsonl", encoding="utf-8"):
        e = json.loads(line)
        if e.get("lang_code") != "ko":
            continue
        w = e.get("word", "")
        if len(w) == 1 and "一" <= w <= "鿿":      # 한자 음가 카탈로그
            for h in e.get("head_templates", []):
                if h.get("name", "").startswith("ko-hanja"):
                    ar = h.get("args", {}); ks = sorted((k for k in ar if k.isdigit()), key=int)
                    if ks and len(ar[ks[-1]]) == 1 and "가" <= ar[ks[-1]] <= "힣":
                        catalog.add(ar[ks[-1]])
        if w and all("가" <= c <= "힣" for c in w):   # 한글 단어
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

# ── 프리셋별 meta 쌍 구성: [{concept,a_raw,b_raw,a,b}] ──
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

def sim(a, b):  # cherry용 표면유사도 (정렬 매칭/길이)
    al = fc.align(a, b)
    if not al:
        return 0.0
    match = sum(1 for x, y in al if x == y and x is not None)
    return match / len(al)

def sample(rows, n):
    rows = rows[:]; random.shuffle(rows)
    return rows[:n]

def trace(rows, pid, label, kind, langA, langB, note):
    pairs = [(r["a"], r["b"]) for r in rows]          # 통계 = 전체 rows
    obs, nulls, p = fc.perm_with_null(pairs, NPERM)
    rws, cls, cnt = fc.build_matrix(pairs)
    N = len(pairs)
    verdict = "BELOW_HORIZON" if N < HORIZON else ("DETECTED" if p < 0.05 else "FLOOR")
    disp = rows[:DISPLAY]                              # 표시 = 앞 DISPLAY쌍
    return dict(id=pid, label=label, kind=kind, langA=langA, langB=langB,
                n=N, nperm=NPERM, horizon=HORIZON,
                pairs=[{"concept": r["concept"], "a_raw": r["a_raw"], "b_raw": r["b_raw"],
                        "a": r["a"], "b": r["b"]} for r in disp],
                alignments=fc.align_trace([(r["a"], r["b"]) for r in disp]),
                matrix={"rows": rws, "cols": cls, "counts": cnt},
                mi=round(obs, 4), null={"values": [round(v, 4) for v in nulls]},
                p=round(p, 4), verdict=verdict, note=note)

def main():
    log("Korean 로딩(대용량 1패스)…")
    ko_all, catalog = load_korean()
    log(f"  ko_all 개념 {len(ko_all)} / sino 카탈로그 {len(catalog)}")

    presets = []
    def add(t):
        (OUT / f"{t['id']}.json").write_text(json.dumps(t, ensure_ascii=False, indent=1), encoding="utf-8")
        presets.append({"id": t["id"], "label": t["label"], "kind": t["kind"], "file": f"{t['id']}.json"})
        log(f"  [{t['id']}] N={t['n']} MI={t['mi']} p={t['p']} → {t['verdict']}")

    # 1) 확정 동계어 (게르만 자매)
    add(trace(sample(gmc_confirmed(), STAT_CAP), "confirmed-gmc",
              "확정 동계어 · 영어↔독일어", "confirmed", "English", "German",
              "같은 조상(Proto-Germanic)을 공유하는 자매어. 체계적 대응이 또렷 → MI 높고 p 작음 = DETECTED."))

    # 2) 한-일 고유어 (한자어 제거)
    kj = korean_vs_proto(ko_all, catalog, KA / "protojaponic.jsonl", strip_sino=True)
    add(trace(sample(kj, STAT_CAP), "kor-jpn-native",
              "한국어 ↔ 일본어 (고유어)", "claim", "proto-Japonic", "Korean",
              "Robbeets류 계보 주장. 한자어 제거 후 고유어층. 신호가 floor 근처 → 무관 대조군과 구별 어려움."))

    # 3) 무관·유형론매칭 대조군 (한국어↔proto-Uralic)
    ur = korean_vs_proto(ko_all, catalog, KA / "protouralic.jsonl", strip_sino=True)
    add(trace(sample(ur, STAT_CAP), "unrelated-uralic",
              "무관 대조군 · 한국어 ↔ Uralic", "control", "proto-Uralic", "Korean",
              "한국어와 계보 무관하나 유형론(교착·CV)이 비슷. ★한-일과 *동급* 신호가 나오면 = 한-일 신호는 계보 아닌 유형론."))

    # 4) 체리픽 lookalike (무관쌍에서 표면유사 상위만)
    ie = korean_vs_proto(ko_all, catalog, KA / "protoindoeuropean.jsonl", strip_sino=True)
    ie.sort(key=lambda r: -sim(r["a"], r["b"]))
    add(trace(ie[:40], "cherry-lookalike",
              "체리픽 함정 · 무관쌍의 lookalike만", "cherry", "proto-Indo-European", "Korean",
              "무관(IE)쌍 중 *닮은 것만 골라냄*. p가 작게 나와도 = 사후선별 산물. proper null(전체 쌍)이면 사라짐 = POC-11 함정."))

    (OUT / "index.json").write_text(json.dumps({"presets": presets}, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"\n[완료] {len(presets)} 프리셋 → {OUT}")

if __name__ == "__main__":
    main()
