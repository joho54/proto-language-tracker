"""POC-20b: 두 독립 재구 머지 → 교차일치율 = contested CI 측정.

Set A: Wikipedia/Lee&Ramsey/Itabashi (Baxter MC)  — poc20_pjaponic.tsv (8 Japonic distinct).
Set B: Ulman 2014ish "Koguryo state: a critical reexamination" (Pulleyblank EMC) — 130 지명
       독립 재분석. 본 파일에 수동 전사(PDF data/pjaponic/ulman_*.pdf, p7-9 표).

핵심: 같은 삼국사기 코퍼스를 *다른 재구체계*로 본 두 학자가 어느 cognate에 동의하나.
  A∩B = 재구-견고 핵심(낮을수록 신호 약함)
  A∪B = 최대주의 셋
  이 [핵심 … 최대] 구간이 §4.1⑤의 정직한 CI. 손코딩 판정 아님 — 데이터가 분산을 자백.
"""
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent
SETA = ROOT / "results" / "poc20_pjaponic.tsv"
OUT = ROOT / "results" / "poc20b_merged.tsv"
LOG = ROOT / "results" / "poc20b_merge.log"

logf = open(LOG, "w")
def log(*a):
    print(*a, flush=True); print(*a, file=logf, flush=True)

# ── Set B: Ulman, "most probably related to Japanese" (p7-8) + 伊 (p9) ──
# (meaning_key, hanja, EMC(Pulleyblank), OJ/J cognate, N_toponyms)
ULMAN_JAPONIC = [
    ("water",     "買",      "*maij/mɛːj",        "mi, mizu",   11),
    ("three",     "蜜",      "*mit",              "mittsu",      1),
    ("willow",    "要(隱)",  "*ʔjiawʔin",         "ya, yanagi",  1),
    ("mouth",     "忽次/古次","*xwəttsʰi/*kətsʰi", "kuti",        4),
    ("deep",      "伏斯",    "*buwk siə/si",      "pukasi",      1),
    ("five",      "于次",    "*wua tsʰi",         "itu, itutu",  1),
    ("valley",    "呑/旦",   "*tʰən/tan",         "tani",        4),
    ("wave",      "内米",    "*nwəjmɛj",          "nami",        1),
    ("ten",       "德",      "*tək",              "towo",        1),
    ("water_deer","古斯",    "*kɔ siə/si",        "kujika",      2),
    ("rabbit",    "烏斯含",  "*ʔɔ si ɣəm/ɣam",    "usagi",       1),
    ("bear",      "功木",    "*kəwŋməwk",         "kuma",        1),
    ("mountain",  "達",      "*dat",              "takai",      14),
    ("seven",     "難(隱)",  "*nan(ʔin)",         "nana",        1),
    ("child",     "仇",      "*guw",              "ko (*kua)",   1),
    ("red",       "沙伏",    "*ʂɛː/ʂai buwk",     "sabi",        1),
    ("land",      "内/奴",   "*nwəj/nɔ",          "no",          4),
    ("cattle",    "烏",      "*ʔɔ",               "i, ushi",     4),
    ("tree",      "斤",      "*kin",              "ki, ko",      3),
    ("take",      "冬",      "*tawŋ",             "toru",        1),
    ("enter",     "伊",      "*ʔji",              "iru",         1),
]
# 양면(J·K 둘 다 가능, p6) — 어느 계보로도 끌 수 있는 = 가장 약한 증거
ULMAN_AMBIG = [
    ("sea",  "波旦", "*pa tsʰia",   "wata (OJ pata)", "bada"),
    ("leek", "(買)", "*maij/mɛːjɕi","nira (OJ mira)", "maneul"),
    ("well", "(泉)", "*ʔia",        "i (OJ wi)",      "u (umul)"),
]
# 문법/synsemantic 형태소 (p10) — Georg 위험지대(소-인벤토리 우연충돌). 별도 카테고리.
ULMAN_GRAM = [
    ("隱", "*ʔin",      "2, none primary"),
    ("斯", "*siə/si",   "15, none primary"),
    ("乙", "*ʔit",      "10, once primary"),
    ("次", "*tsʰi",     "10, none primary"),
    ("尸", "*ɕi",       "11, none primary"),
]

# ── Set A 로드 (Wikipedia/Baxter) ──
GLOSS2KEY = {  # set A gloss 영어 → 표준 meaning_key
    "three": "three", "five": "five", "seven": "seven", "ten": "ten",
    "valley": "valley", "rabbit": "rabbit", "lead": "lead", "water": "water",
    "river": "water", "mother": "mother", "cliff": "cliff", "boulder": "cliff",
    "layer": "layer", "ox": "ox", "pool": "pool", "earth": "earth", "sea": "sea",
    "jade": "jade", "eggplant": "eggplant", "castle": "castle", "mountain": "mountain",
    "king": "king", "heart": "heart", "bear": "bear", "green": "green", "black": "black",
}
def keyof(gloss):
    for w in re.findall(r"'([^']+)'", gloss):
        first = w.split(",")[0].split("/")[0].split()[0].strip().lower()
        if first in GLOSS2KEY:
            return GLOSS2KEY[first]
    return gloss.strip().lower()

setA = {}  # meaning_key → dict
for ln in SETA.read_text().splitlines()[1:]:
    c = ln.split("\t")
    if len(c) < 6:
        continue
    script, mc, sk, gloss, comp, fam = c[:6]
    k = keyof(gloss)
    if k not in setA:  # 첫 표기만(valley 등 rowspan 중복 흡수)
        setA[k] = dict(hanja=script, baxter=mc, comp=comp, fam=fam)

setB = {m[0]: dict(hanja=m[1], emc=m[2], jcomp=m[3], n=m[4]) for m in ULMAN_JAPONIC}
ambig_keys = {m[0] for m in ULMAN_AMBIG}

# ── 머지 ──
all_keys = sorted(set(setA) | set(setB) | ambig_keys)
rows = []
for k in all_keys:
    a, b = setA.get(k), setB.get(k)
    a_jap = bool(a and a["fam"] == "Japonic")
    a_kor = bool(a and a["fam"] in ("Koreanic", "Tungusic"))
    in_both_jap = a_jap and bool(b)
    rows.append(dict(
        meaning=k,
        setA_fam=(a["fam"] if a else "-"),
        setA_hanja=(a["hanja"] if a else "-"),
        setA_baxter=(a["baxter"] if a else "-"),
        setB_hanja=(b["hanja"] if b else ("amb" if k in ambig_keys else "-")),
        setB_emc=(b["emc"] if b else "-"),
        setB_jcomp=(b["jcomp"] if b else "-"),
        setB_n=(str(b["n"]) if b else "-"),
        japonic_in=("A+B" if in_both_jap else ("B" if b else ("A" if a_jap else
                    ("ambig" if k in ambig_keys else "-")))),
    ))

cols = ["meaning", "japonic_in", "setA_fam", "setA_hanja", "setA_baxter",
        "setB_hanja", "setB_emc", "setB_jcomp", "setB_n"]
with open(OUT, "w") as f:
    f.write("\t".join(cols) + "\n")
    for r in rows:
        f.write("\t".join(r[c] for c in cols) + "\n")

# ── 교차일치 통계 = contested CI ──
A_jap = {k for k, v in setA.items() if v["fam"] == "Japonic"}
B_jap = set(setB)
both = A_jap & B_jap
a_only = A_jap - B_jap
b_only = B_jap - A_jap
union = A_jap | B_jap

log("=== POC-20b: 두 독립 재구 Japonic cognate 교차일치 ===\n")
log(f"Set A (Baxter MC, Lee&Ramsey/Itabashi)  Japonic distinct : {len(A_jap)}")
log(f"Set B (Pulleyblank EMC, Ulman)          Japonic distinct : {len(B_jap)}")
log(f"  + 양면(J·K) {len(ULMAN_AMBIG)}, 문법형태소 {len(ULMAN_GRAM)}(Georg 위험지대)\n")
log(f"A∩B (두 재구 모두 = 견고 핵심) : {len(both)}   {sorted(both)}")
log(f"A only                        : {len(a_only)}   {sorted(a_only)}")
log(f"B only                        : {len(b_only)}   {sorted(b_only)}")
log(f"A∪B (최대주의)                : {len(union)}\n")
log(f"★ 정직한 CI = [견고 {len(both)} … 최대 {len(union)}]  (지평 ~15–20쌍 기준)")
log(f"  - 견고 핵심 {len(both)} = 지평 {'위 ✓' if len(both)>=15 else '밑 ✗'}")
log(f"  - 최대주의 {len(union)} = 지평 {'위 ✓' if len(union)>=15 else '밑 ✗'}")
log("  → 결론이 *재구 가정에 달림* = 바로 이 민감도가 우리가 잴 contested CI.")
log("\nUlman 자체 집계(맥락): 130지명 중 26 강한 J-형태소 + 40 약한 = ~50%,")
log("  단 '투명한 J 지명도 미상 형태소(*xwət fort, *paʔi peak)로 끝남 → substrate 가능' (정직한 기권).")
log(f"\n[머지] {len(rows)}행 → {OUT}")
logf.close()
