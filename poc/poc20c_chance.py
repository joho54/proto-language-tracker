"""POC-20 step-1: 반도 Japonic 검정셋에 chance-null — CI [7…22] 양 끝에서.

POC-20b가 측정한 정직한 CI [견고 7 … 최대 22] 위에서 첫 검정:
  반도 형태(EMC/MC 재구) ↔ Old Japanese cognate 의 분절 대응이 우연을 넘는가?
  → 견고 핵심(A∩B=7)과 최대주의(A∪B=22) *양 끝*에서 MI + 순열 null.

★ 정직성(핵심 발견 예고): 이 검정셋은 *학자가 닮은 것만 골라낸* 사전선별 목록이다.
  쌍-셔플 null은 "이 OJ형이 *자기* 반도짝에 특이적으로 닮았나"만 보는데, 선별이 이미
  유사 임계를 통과시킴 → null이 *너무 쉽다*(POC-11 체리피킹 함정의 구조). 따라서:
  - 여기서 '유의'가 나와도 = 관계 확정 ❌. = 선택편향된 null의 산물일 수 있음.
  - 정직한 검정 = 130 지명 *전체*(denominator, 안 닮은 ~64개 포함) + 유형론-매칭 대조군.
  이 POC는 (a) 검정 하니스 가동 + (b) denominator 필요를 *수치로* 입증 = step-1.
"""
import re, csv
from pathlib import Path
from poc17c_korjap import align, mutual_info, perm_p  # 동일 MI·순열 기계 재사용

ROOT = Path(__file__).parent
MERGED = ROOT / "results" / "poc20b_merged.tsv"
SETA = ROOT / "results" / "poc20_pjaponic.tsv"
OUT = ROOT / "results" / "poc20c.tsv"
LOG = ROOT / "results" / "poc20c.log"
NPERM = 5000

logf = open(LOG, "w")
def log(*a):
    print(*a, flush=True); print(*a, file=logf, flush=True)

# IPA/재구기호 → coarse ASCII 음소 (반도재구·OJ로마자 비교가능하게)
IPA = {"ɛ": "e", "ə": "e", "ɔ": "o", "æ": "a", "ɨ": "u", "ʉ": "u", "ø": "o",
       "ɣ": "g", "ʔ": "", "ɕ": "s", "ʂ": "s", "ʐ": "s", "ŋ": "n", "ç": "s",
       "β": "b", "ð": "d", "θ": "t", "χ": "h", "ʁ": "g"}

def coarse(s):
    """첫 변이형만, 마크업·성조·기식 제거, IPA→ASCII, 자모만 남김."""
    s = re.sub(r"\(.*?\)", "", s)          # 괄호 주석/대안 제거
    s = s.split("/")[0].split(",")[0]       # 첫 변이형
    s = s.strip().lstrip("*").strip()
    for ch in ["ʰ", "ː", "ˀ", "ʼ", "ⁿ", "ˤ", "´", "`", "ˈ", "ˌ"]:
        s = s.replace(ch, "")
    s = s.lower()
    s = "".join(IPA.get(c, c) for c in s)
    s = re.sub(r"[^a-z]", "", s)
    return s

# 검정셋 로드: merged TSV의 Japonic 행 (반도 reading, OJ cognate)
setA_jap = {}  # meaning → (reading, ojcomp)  — A-only(lead) 채우기용
for r in csv.DictReader(open(SETA), delimiter="\t"):
    if r["family"] == "Japonic":
        # gloss "鉛 'lead'" → key는 merged와 맞추기 위해 영어 첫 단어
        m = re.findall(r"'([^']+)'", r["gloss"])
        key = (m[0].split(",")[0].split("/")[0].split()[0].lower() if m else r["gloss"])
        comp = re.sub(r"'[^']*'", "", r["comparandum"])  # 인용 gloss 제거
        setA_jap[key] = (r["mc"], comp.replace("Old Japanese", "").strip())

robust, full = [], []   # (반도, OJ) coarse 쌍
rows = list(csv.DictReader(open(MERGED), delimiter="\t"))
for r in rows:
    tag = r["japonic_in"]
    if tag not in ("A+B", "B", "A"):
        continue
    if r["setB_emc"] != "-":
        reading, oj = r["setB_emc"], r["setB_jcomp"]
    else:  # A-only (lead): set A에서
        reading, oj = setA_jap.get(r["meaning"], ("", ""))
    a, b = coarse(reading), coarse(oj)
    if not a or not b:
        continue
    full.append((a, b, r["meaning"]))
    if tag == "A+B":
        robust.append((a, b, r["meaning"]))

log("=" * 60)
log("POC-20 step-1: 반도 Japonic 검정셋 chance-null (CI 양 끝)")
log("=" * 60)
log(f"nperm={NPERM}\n")

OUT.write_text("set\tN\tMI\tp_value\tnote\n")
for name, data, note in [
    ("robust(A∩B)", robust, "재구-견고 핵심; 전부 Swadesh = Georg 우연충돌 최고위험"),
    ("max(A∪B)", full, "최대주의; B-only는 재구-취약(Ulman 단독)"),
]:
    pairs = [(a, b) for a, b, _ in data]
    mi, p = perm_p(pairs, NPERM)
    log(f"[{name}]  N={len(pairs)}  MI={mi:.4f}  p={p:.4f}")
    log(f"   {note}")
    log(f"   쌍: {[(m, a, b) for a, b, m in data]}\n")
    with open(OUT, "a") as f:
        f.write(f"{name}\t{len(pairs)}\t{mi:.4f}\t{p:.4f}\t{note}\n")

log("-" * 60)
log("★ 판독(정직): 이 셋은 학자 사전선별 → 쌍-셔플 null은 선택편향(너무 쉬움).")
log("  '유의'여도 관계 확정 아님 = POC-11 체리피킹 함정의 구조적 재현.")
log("  정직한 검정 = 130 지명 denominator(안 닮은 ~64 포함) + 유형론-매칭 대조군.")
log("  → POC-20 step-2: Ulman 130 전사 확보 → coverage rate vs chance + 대조군.")
logf.close()
