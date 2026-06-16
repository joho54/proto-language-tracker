"""POC-21b: 반도 지명 coverage vs 유형론 대조군 — 사전등록 검정 실행.

(a) 한자 음가: Baxter-Sagart MC(data/pjaponic/baxtersagart.tsv), 미스는 한국 한자음 폴백.
(b) old↔new 정렬: 삼국사기37 286쌍(sg37_cache)에서 old 음차명↔new 의역명 형태소 정렬 →
    각 old 형태소 = (MC 음가, 의미=정렬된 new 한자 뜻).
(c) 검정: old 형태소 음가가 *그 의미*의 OJ 단어에 coarse 유사≥0.5로 매칭되나 →
    coverage(반도→Japonic) vs 대조군(Uralic/Turkic) + 의미-순열 null + 지역분해 + 수사제거.

사전등록(PIPELINE POC-21): Δ=cov(Jap)−cov(control) ± CI. ①floor / ②남부양성 / ③균일=아티팩트.
★성공=양성 아니라 교정된 CI. 매칭/의미 lookup은 Jap·대조군에 *동일* 적용 → 노이즈는 Δ서 상쇄.
"""
import re, html, random, csv
from collections import defaultdict
from pathlib import Path
from poc17c_korjap import hangul_phon, norm_gloss, load_proto  # 재사용(import 안전)

random.seed(21)
ROOT = Path(__file__).parent
DATA = ROOT.parent / "data"
CACHE = DATA / "pjaponic" / "sg37_cache"
BS = DATA / "pjaponic" / "baxtersagart.tsv"
KO = DATA / "kaikki" / "korean.jsonl"
OUT = ROOT / "results" / "poc21b.tsv"
LOG = ROOT / "results" / "poc21b.log"
SIM_THR = 0.5
NPERM = 2000

logf = open(LOG, "w")
def log(*a):
    print(*a, flush=True); print(*a, file=logf, flush=True)

# ── (a) 음가: Baxter-Sagart MC + 한국 한자음 폴백 ──
def mc_clean(s):
    """Baxter MC → coarse ASCII (성조 H/X·괄호 제거)."""
    s = s.split(",")[0].strip()
    s = re.sub(r"[HX]$", "", s)         # 성조
    s = s.replace("'", "")               # 성문음 표기
    return s

bs_read, bs_gloss = {}, {}
for r in csv.DictReader(open(BS), delimiter="\t"):
    z = r["zi"]
    if z and z not in bs_read:
        if r.get("MC", "").strip():
            bs_read[z] = mc_clean(r["MC"])
        if r.get("gloss", "").strip():
            bs_gloss[z] = r["gloss"].strip()

# 한국 한자음 폴백 (kaikki ko-hanja: 한자→음 한글)
sk_read = {}
import json
for line in open(KO, encoding="utf-8"):
    e = json.loads(line)
    if e.get("lang_code") != "ko":
        continue
    w = e.get("word", "")
    if len(w) == 1 and "一" <= w <= "鿿" and w not in sk_read:
        for h in e.get("head_templates", []):
            if h.get("name", "").startswith("ko-hanja"):
                args = h.get("args", {})
                keys = sorted((k for k in args if k.isdigit()), key=int)
                if keys and len(args[keys[-1]]) == 1 and "가" <= args[keys[-1]] <= "힣":
                    sk_read[w] = args[keys[-1]]
log(f"[a] Baxter-Sagart MC {len(bs_read)}자, gloss {len(bs_gloss)}자; 한국한자음 폴백 {len(sk_read)}자")

# 토포님 의미 형태소 → 영어 개념 (흔한 것 큐레이션; 미스는 BS gloss 폴백)
HAN_CONCEPT = {
    "水": "water", "川": "river", "城": "castle", "山": "mountain", "谷": "valley",
    "高": "high", "海": "sea", "石": "stone", "木": "tree", "大": "big", "長": "long",
    "牛": "cow", "馬": "horse", "金": "gold", "土": "earth", "泉": "well", "井": "well",
    "黑": "black", "白": "white", "赤": "red", "靑": "green", "鐵": "iron", "母": "mother",
    "王": "king", "心": "heart", "熊": "bear", "兎": "rabbit", "猪": "pig", "童": "child",
    "鵠": "swan", "鷲": "eagle", "深": "deep", "淺": "shallow", "穴": "hole", "峯": "peak",
    "嶺": "ridge", "峴": "pass", "原": "field", "野": "field", "土": "earth",
}

def char_reading(c):
    if c in bs_read:
        return bs_read[c]
    if c in sk_read:                     # 폴백: 한글음 → coarse
        return hangul_phon(sk_read[c])
    return None

def char_concept(c):
    if c in HAN_CONCEPT:
        return HAN_CONCEPT[c]
    if c in bs_gloss:
        return norm_gloss(bs_gloss[c])
    return None

# ── (b) 삼국사기37 286쌍 파싱 + old↔new 형태소 정렬 ──
ADMIN = "郡縣州城忽達"  # 행정/지명 접미 후보 — 단 stem서 흔해 정렬은 stem 동일길이일 때만
SUF = "郡縣州"          # 안전 접미(이것만 strip)
pair_re = re.compile(r"([가-힣]{1,6})\(([一-鿿]{2,5})\)\s*[:：]\s*(.{0,80}?)([一-鿿]{2,5})\)(?:으로|로)\s*(?:고치|바꾸|개칭)")

def strip_suf(s):
    return s[:-1] if len(s) > 1 and s[-1] in SUF else s

toponyms = []  # {section, old, new, morphs:[(char, reading, concept)]}
for f in sorted(CACHE.glob("sg_037r_*.html")):
    sec = re.search(r"(sg_037r_\d{4})_", f.name).group(1)
    txt = html.unescape(re.sub(r"<[^>]+>", "\n", f.read_text(encoding="utf-8")))
    seen = set()
    for _, old, _, new in pair_re.findall(txt):
        if (old, new) in seen:
            continue
        seen.add((old, new))
        o, n = strip_suf(old), strip_suf(new)
        morphs = []
        if len(o) == len(n):             # 동일길이만 위치정렬(보수적)
            for co, cn in zip(o, n):
                morphs.append((co, char_reading(co), char_concept(cn)))
        toponyms.append(dict(section=sec, old=old, new=new, morphs=morphs))

aligned = [t for t in toponyms if t["morphs"]]
log(f"[b] 파싱 {len(toponyms)}쌍, 동일길이 정렬가능 {len(aligned)}쌍")
ex = [t for t in aligned if any(m[2] for m in t["morphs"])][:6]
for t in ex:
    log(f"    {t['old']}→{t['new']}: " + ", ".join(f"{m[0]}[{m[1]}={m[2]}]" for m in t["morphs"]))

# ── coarse 음소 + 유사도 ──
IPA = {"ɛ": "e", "ə": "e", "ɔ": "o", "æ": "a", "ɨ": "u", "ŋ": "n", "ɕ": "s", "ʂ": "s", "ɣ": "g"}
def coarse(s):
    if not s:
        return ""
    s = re.sub(r"\(.*?\)", "", s).split("/")[0].split(",")[0].strip().lstrip("*")
    s = s.lower()
    s = "".join(IPA.get(c, c) for c in s)
    return re.sub(r"[^a-z]", "", s)

def lev(a, b):
    if not a or not b:
        return max(len(a), len(b))
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
    return d[-1]

def sim(a, b):
    a, b = coarse(a), coarse(b)
    if not a or not b:
        return 0.0
    return 1 - lev(a, b) / max(len(a), len(b))

# ── (c) coverage: old 형태소 음가가 *그 의미*의 비교어 단어에 매칭? ──
def coverage(proto, topos, drop_numerals=False, meaning_perm=None):
    """proto: concept→word. meaning_perm: 의미 라벨 셔플 맵(null용)."""
    NUM = {"three", "five", "seven", "ten"}
    covered = 0; total = 0
    for t in topos:
        if not t["morphs"]:
            continue
        total += 1
        hit = False
        for c, reading, concept in t["morphs"]:
            if not reading or not concept:
                continue
            if drop_numerals and concept in NUM:
                continue
            look = meaning_perm.get(concept, concept) if meaning_perm else concept
            w = proto.get(look)
            if w and sim(reading, w) >= SIM_THR:
                hit = True; break
        if hit:
            covered += 1
    return covered, total

# 비교어 로드
PJ = load_proto(DATA / "kaikki" / "protojaponic.jsonl")
UR = load_proto(DATA / "kaikki" / "protouralic.jsonl")
TK = load_proto(DATA / "kaikki" / "prototurkic.jsonl")
log(f"\n[c] 비교어 concept 수: Japonic {len(PJ)} / Uralic {len(UR)} / Turkic {len(TK)}")

def cov_frac(proto, topos, **kw):
    c, n = coverage(proto, topos, **kw)
    return c / n if n else 0.0, c, n

# 전체 + 수사제거
OUT.write_text("scope\tlang\tcov\tcovered\ttotal\tnote\n")
log("\n=== coverage (전체 286 정렬셋) ===")
results = {}
for label, proto in [("Japonic", PJ), ("Uralic", UR), ("Turkic", TK)]:
    f_all, c_all, n = cov_frac(proto, aligned)
    f_nn, c_nn, _ = cov_frac(proto, aligned, drop_numerals=True)
    results[label] = (f_all, f_nn)
    log(f"  {label:8s} cov={f_all:.3f} ({c_all}/{n})   수사제거 {f_nn:.3f} ({c_nn}/{n})")
    with open(OUT, "a") as fh:
        fh.write(f"all\t{label}\t{f_all:.4f}\t{c_all}\t{n}\t수사포함\n")
        fh.write(f"all_noNum\t{label}\t{f_nn:.4f}\t{c_nn}\t{n}\t수사제거\n")

ctrl_max = max(results["Uralic"][0], results["Turkic"][0])
delta = results["Japonic"][0] - ctrl_max
log(f"\n★ Δ(전체) = cov(Jap) − max(대조군) = {results['Japonic'][0]:.3f} − {ctrl_max:.3f} = {delta:+.3f}")

# 의미-순열 null (Japonic): 의미 라벨 셔플 → chance coverage 분포
concepts = sorted({m[2] for t in aligned for m in t["morphs"] if m[2]})
obs = cov_frac(PJ, aligned)[0]
ge = 0; perm_vals = []
for _ in range(NPERM):
    shuf = concepts[:]; random.shuffle(shuf)
    pmap = dict(zip(concepts, shuf))
    v = cov_frac(PJ, aligned, meaning_perm=pmap)[0]
    perm_vals.append(v)
    if v >= obs:
        ge += 1
p_mean = sum(perm_vals) / len(perm_vals)
p_val = (ge + 1) / (NPERM + 1)
log(f"\n의미-순열 null(Japonic): obs={obs:.3f}  null평균={p_mean:.3f}  p={p_val:.4f}")

# 지역 분해 (②/③ 판정)
log("\n=== 지역(섹션) 분해 — ②남부집중 vs ③균일 ===")
SEC_NAME = {"sg_037r_0020": "溟州(동해안)", "sg_037r_0030": "朔州(중북부)",
            "sg_037r_0040": "백제(남서)", "sg_037r_0050": "한주?", "sg_037r_0060": "한주/북", "sg_037r_0070": "기타"}
with open(OUT, "a") as fh:
    for sec in sorted({t["section"] for t in aligned}):
        sub = [t for t in aligned if t["section"] == sec]
        fj = cov_frac(PJ, sub); fu = cov_frac(UR, sub); ft = cov_frac(TK, sub)
        d = fj[0] - max(fu[0], ft[0])
        log(f"  {sec} {SEC_NAME.get(sec,''):10s} N={fj[2]:3d}  Jap={fj[0]:.2f} Ur={fu[0]:.2f} Tk={ft[0]:.2f}  Δ={d:+.2f}")
        fh.write(f"region:{sec}\tDelta\t{d:.4f}\t{fj[1]}\t{fj[2]}\t{SEC_NAME.get(sec,'')}\n")

# 판정
log("\n" + "=" * 60)
verdict = ("③ 균일 강양성=아티팩트 의심" if delta > 0.15 and p_val < 0.05
           else "②/① 경계 — 지역분해·CI로 판정" if delta > 0.03
           else "① floor(대조군과 구별불가)")
log(f"판정(1차): Δ={delta:+.3f}, null-p={p_val:.4f} → {verdict}")
log("★ CI·최종판정은 지역 Δ 패턴(남부집중=② / 균일=③ / 무=①)과 함께. 산출=교정된 Δ±근사CI.")
logf.close()
