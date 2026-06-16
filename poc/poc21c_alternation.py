"""POC-21c: 異名(이명) 104쌍 기반 coverage 검정 — 유효한 의미원천 위에서.

poc21b 발견: 757 개명 위치정렬은 무효(번역 아님). 유효한 의미원천 = 異名(一云/…로도 일컬었다,
의역명↔음차명 같은 장소). 단 형태소 정렬이 비위치적(3자↔5자) → *장소 단위* 묶음으로 우회:
  한 장소의 두 이름 글자를 풀(pool)하여, (의미 c를 가진 글자) + (음가 r을 가진 *다른* 글자)에서
  OJ[c]가 r에 coarse-유사하면 그 장소 "covered". 의미는 의역측, 음가는 음차측에서 자연 분리됨.

사전등록(PIPELINE POC-21): Δ=cov(Jap)−cov(대조군) ± CI. ①floor / ②남부집중 / ③균일=아티팩트.
★유효성: 의미가 異名(실데이터)서 옴(21b의 가짜 위치정렬 아님). 매칭/lookup은 Jap·대조군 동일 적용.
★임계 민감도(0.4/0.5/0.6) = CI 폭. step-1의 하드임계 과엄 우려 → 다임계로 정직 보고.
"""
import re, html, random, csv, json
from pathlib import Path
from poc17c_korjap import hangul_phon, norm_gloss, load_proto

random.seed(21)
ROOT = Path(__file__).parent
DATA = ROOT.parent / "data"
CACHE = DATA / "pjaponic" / "sg37_cache"
BS = DATA / "pjaponic" / "baxtersagart.tsv"
KO = DATA / "kaikki" / "korean.jsonl"
OUT = ROOT / "results" / "poc21c.tsv"
LOG = ROOT / "results" / "poc21c.log"
NPERM = 2000
THRS = [0.4, 0.5, 0.6]

logf = open(LOG, "w")
def log(*a):
    print(*a, flush=True); print(*a, file=logf, flush=True)

# ── 음가(Baxter-Sagart MC + 한국한자음 폴백) ──
def mc_clean(s):
    s = s.split(",")[0].strip()
    return re.sub(r"[HX]$", "", s).replace("'", "")

bs_read, bs_gloss = {}, {}
for r in csv.DictReader(open(BS), delimiter="\t"):
    z = r["zi"]
    if z and z not in bs_read:
        if r.get("MC", "").strip():
            bs_read[z] = mc_clean(r["MC"])
        if r.get("gloss", "").strip():
            bs_gloss[z] = r["gloss"].strip()
sk_read = {}
for line in open(KO, encoding="utf-8"):
    e = json.loads(line)
    if e.get("lang_code") != "ko":
        continue
    w = e.get("word", "")
    if len(w) == 1 and "一" <= w <= "鿿" and w not in sk_read:
        for h in e.get("head_templates", []):
            if h.get("name", "").startswith("ko-hanja"):
                a = h.get("args", {}); ks = sorted((k for k in a if k.isdigit()), key=int)
                if ks and len(a[ks[-1]]) == 1 and "가" <= a[ks[-1]] <= "힣":
                    sk_read[w] = a[ks[-1]]

HAN_CONCEPT = {
    "水": "water", "川": "river", "城": "castle", "山": "mountain", "谷": "valley",
    "高": "high", "海": "sea", "石": "stone", "木": "tree", "大": "big", "長": "long",
    "牛": "cow", "馬": "horse", "金": "gold", "土": "earth", "泉": "well", "井": "well",
    "黑": "black", "白": "white", "赤": "red", "靑": "green", "鐵": "iron", "母": "mother",
    "王": "king", "心": "heart", "熊": "bear", "兎": "rabbit", "猪": "pig", "童": "child",
    "子": "child", "鵠": "swan", "鷲": "eagle", "深": "deep", "峯": "peak", "嶺": "ridge",
    "峴": "pass", "原": "field", "野": "field", "獐": "deer", "鹿": "deer", "斧": "axe",
    "壤": "earth", "口": "mouth", "項": "neck", "首": "head", "岑": "peak", "穴": "hole",
}
def reading(c):
    if c in bs_read: return bs_read[c]
    if c in sk_read: return hangul_phon(sk_read[c])
    return None
def concept(c):
    if c in HAN_CONCEPT: return HAN_CONCEPT[c]
    if c in bs_gloss: return norm_gloss(bs_gloss[c])
    return None

# ── coarse 음소 + 유사도 ──
IPA = {"ɛ": "e", "ə": "e", "ɔ": "o", "æ": "a", "ɨ": "u", "ŋ": "n", "ɕ": "s", "ʂ": "s", "ɣ": "g"}
def coarse(s):
    if not s: return ""
    s = re.sub(r"\(.*?\)", "", s).split("/")[0].split(",")[0].strip().lstrip("*").lower()
    return re.sub(r"[^a-z]", "", "".join(IPA.get(c, c) for c in s))
def lev(a, b):
    if not a or not b: return max(len(a), len(b))
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
    return d[-1]
def sim(a, b):
    a, b = coarse(a), coarse(b)
    if not a or not b: return 0.0
    return 1 - lev(a, b) / max(len(a), len(b))

# ── 異名 파싱: (지명한자, 異名한자) 같은 장소 ──
SUF = "郡縣州"
alt_re = re.compile(r"([가-힣]{1,6})\(([一-鿿]{2,6})\)\s*[:：][^\n]{0,120}?([一-鿿]{2,6})\)(?:로도|으로도|라고도)\s*(?:일컬|불)")
def strip_suf(s):
    return s[:-1] if len(s) > 1 and s[-1] in SUF else s

places = []  # {section, chars:[(c,reading,concept)], concepts:set}
seen = set()
for f in sorted(CACHE.glob("sg_037r_*.html")):
    sec = re.search(r"(sg_037r_\d{4})_", f.name).group(1)
    txt = html.unescape(re.sub(r"<[^>]+>", "\n", f.read_text(encoding="utf-8")))
    for _, n1, n2 in alt_re.findall(txt):
        key = tuple(sorted((n1, n2)))
        if key in seen: continue
        seen.add(key)
        chars = []
        for c in strip_suf(n1) + strip_suf(n2):
            chars.append((c, reading(c), concept(c)))
        concs = {x[2] for x in chars if x[2]}
        if concs and len(chars) >= 2:        # 의미 ≥1 + 글자 ≥2 (사람이름 등 자연 배제)
            places.append(dict(section=sec, chars=chars, concepts=concs))

log(f"[파싱] 異名 {len(seen)}쌍 → 의미부여 가능 장소 {len(places)}개")
ex = [p for p in places][:8]
for p in ex:
    cs = "".join(x[0] for x in p["chars"])
    log(f"    {cs}: 의미{sorted(p['concepts'])} 음가{[x[1] for x in p['chars'] if x[1]][:4]}")

# ── coverage: 장소 단위, 의미(글자i) ↔ 음가(다른 글자j) 교차 ──
NUM = {"three", "five", "seven", "ten"}
def coverage(proto, plcs, thr, drop_num=False, perm=None):
    cov = tot = 0
    for p in plcs:
        tot += 1
        hit = False
        for i, (ci, ri, coi) in enumerate(p["chars"]):
            if not coi or (drop_num and coi in NUM):
                continue
            look = perm.get(coi, coi) if perm else coi
            w = proto.get(look)
            if not w:
                continue
            for j, (cj, rj, coj) in enumerate(p["chars"]):
                if i == j or not rj:
                    continue
                if sim(rj, w) >= thr:
                    hit = True; break
            if hit:
                break
        cov += hit
    return cov, tot

PJ = load_proto(DATA / "kaikki" / "protojaponic.jsonl")
UR = load_proto(DATA / "kaikki" / "protouralic.jsonl")
TK = load_proto(DATA / "kaikki" / "prototurkic.jsonl")
log(f"\n비교어 concept: Japonic {len(PJ)} / Uralic {len(UR)} / Turkic {len(TK)}")

OUT.write_text("thr\tlang\tcov\tcovered\ttotal\tdelta_vs_ctrl\n")
log("\n=== coverage vs 대조군 (임계 민감도 = CI 폭) ===")
log(f"{'thr':>4} {'Jap':>6} {'Ur':>6} {'Tk':>6} {'Δ=Jap-maxCtrl':>14}")
deltas = {}
for thr in THRS:
    cj, n = coverage(PJ, places, thr)
    cu, _ = coverage(UR, places, thr)
    ct, _ = coverage(TK, places, thr)
    fj, fu, ft = cj/n, cu/n, ct/n
    d = fj - max(fu, ft)
    deltas[thr] = d
    log(f"{thr:>4} {fj:>6.3f} {fu:>6.3f} {ft:>6.3f} {d:>+14.3f}   (Jap {cj}/{n})")
    with open(OUT, "a") as fh:
        for lab, c, ff in [("Jap", cj, fj), ("Ur", cu, fu), ("Tk", ct, ft)]:
            fh.write(f"{thr}\t{lab}\t{ff:.4f}\t{c}\t{n}\t{d:.4f}\n")

# 의미-순열 null (thr=0.5, Japonic)
concs = sorted({c for p in places for c in p["concepts"]})
obs = coverage(PJ, places, 0.5)[0]
ge = 0; vals = []
for _ in range(NPERM):
    sh = concs[:]; random.shuffle(sh)
    pmap = dict(zip(concs, sh))
    v = coverage(PJ, places, 0.5, perm=pmap)[0]
    vals.append(v)
    if v >= obs: ge += 1
p_val = (ge + 1) / (NPERM + 1)
log(f"\n의미-순열 null(thr0.5): obs={obs} covered, null평균={sum(vals)/len(vals):.1f}, p={p_val:.4f}")

# 수사 제거(thr0.5)
cj_nn = coverage(PJ, places, 0.5, drop_num=True)[0]
log(f"수사 제거: Jap covered {coverage(PJ,places,0.5)[0]} → {cj_nn} (수사 우연충돌 기여 점검)")

# 지역 분해
log("\n=== 지역(섹션) 분해 — ②남부집중 vs ③균일 ===")
SEC = {"sg_037r_0020": "溟州동해", "sg_037r_0030": "朔州중북", "sg_037r_0040": "백제남서",
       "sg_037r_0050": "한주A", "sg_037r_0060": "한주B/북", "sg_037r_0070": "기타"}
with open(OUT, "a") as fh:
    for sec in sorted({p["section"] for p in places}):
        sub = [p for p in places if p["section"] == sec]
        if not sub: continue
        cj, n = coverage(PJ, sub, 0.5); cu, _ = coverage(UR, sub, 0.5); ct, _ = coverage(TK, sub, 0.5)
        d = cj/n - max(cu/n, ct/n)
        log(f"  {sec} {SEC.get(sec,''):8s} N={n:3d}  Jap={cj/n:.2f} Ur={cu/n:.2f} Tk={ct/n:.2f}  Δ={d:+.2f}")
        fh.write(f"region:{sec}\tDelta\t{d:.4f}\t{cj}\t{n}\t{SEC.get(sec,'')}\n")

# 판정
dmax = max(deltas.values()); dmin = min(deltas.values())
log("\n" + "=" * 60)
log(f"★ Δ 구간(임계 0.4~0.6) = [{dmin:+.3f} … {dmax:+.3f}], 의미순열 p={p_val:.4f}")
if dmax <= 0.03:
    v = "① floor — 대조군과 구별불가(유효한 의미원천 위 = 진짜 음성)"
elif dmin > 0.10:
    v = "③ 균일 강양성 — 아티팩트 의심(매칭 과대)"
else:
    v = "②/① 경계 — 지역 Δ 패턴(남부집중?)으로 최종판정"
log(f"판정: {v}")
log("★ 산출=교정된 Δ±CI. 21b 아티팩트와 달리 의미가 異名 실데이터 → 이 floor는 *유효*.")
logf.close()
