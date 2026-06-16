"""POC-20 Tier-A: Peninsular Japonic cognate 검정셋 추출 (삼국사기 권37 glosses).

§4.1⑤ 삼각측량용 검정셋의 *분자* — 반도 form 증인. 깨끗한 cognate가 실제 몇 개이고
어느 비교어족(Japonic/Koreanic/Tungusic)으로 갈리는지를 확정해 소-N 벽을 *측정*한다.

데이터: Wikipedia "Placename glosses in the Samguk sagi" wikitable
        (Lee&Ramsey 2011 / Itabashi 2003 / Lim 2000의 검증된 비교셋 통합본).
규칙(CLAUDE.md): 원본 wikitext는 디스크 캐시(data/pjaponic/wiki_glosses_raw.txt) —
        없으면 1회 fetch, 있으면 재사용(idempotent). 산출 TSV는 한 번에 디스크로.

이건 *시드*다. 학자별(Beckwith/Vovin) 논쟁 판독은 책 PDF에서 수동 보강(컬럼 source로 분리).
"""
import re, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
RAW = ROOT.parent / "data" / "pjaponic" / "wiki_glosses_raw.txt"
OUT = ROOT / "results" / "poc20_pjaponic.tsv"
LOG = ROOT / "results" / "poc20_pjaponic.log"
URL = "https://en.wikipedia.org/wiki/Placename_glosses_in_the_Samguk_sagi?action=raw"
UA = {"User-Agent": "proto-lang-tracker-poc/0.2 (research; joho0504)"}

logf = open(LOG, "w")
def log(*a):
    print(*a, flush=True)
    print(*a, file=logf, flush=True)


def ensure_raw():
    """캐시 우선 — 없을 때만 1회 fetch 후 저장."""
    if RAW.exists():
        log(f"[cache] {RAW} ({RAW.stat().st_size}B)")
        return RAW.read_text(encoding="utf-8")
    RAW.parent.mkdir(parents=True, exist_ok=True)
    log(f"[fetch] {URL}")
    txt = urllib.request.urlopen(
        urllib.request.Request(URL, headers=UA), timeout=30).read().decode("utf-8")
    RAW.write_text(txt, encoding="utf-8")
    log(f"[saved] {RAW} ({len(txt)}B)")
    return txt


def clean(s):
    """wikitext 마크업 제거 → 평문 form."""
    s = re.sub(r"\{\{sfnp\|[^}]*\}\}", "", s)          # 인용 각주 제거
    s = re.sub(r"\{\{linktext\|lang=zh\|([^}]*)\}\}", r"\1", s)
    s = re.sub(r"\{\{Not a typo\|([^}]*)\}\}", r"\1", s)
    s = re.sub(r"\{\{efn[^}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)  # [[a|b]]→b, [[a]]→a
    s = s.replace("''", "").replace("'''", "")
    s = re.sub(r"<sub>([^<]*)</sub>", r"\1", s)         # 갑류/을류 첨자
    s = re.sub(r"<sup>([^<]*)</sup>", r"\1", s)         # 성조 H/X
    s = re.sub(r"<[^>]+>", "", s)
    return s.strip()


def family(comparandum):
    c = comparandum.lower()
    if "old japanese" in c or "japonic" in c:
        return "Japonic"
    if "korean" in c:                                   # Middle Korean
        return "Koreanic"
    if "tungusic" in c or "manchu" in c:
        return "Tungusic"
    return "?"


def parse(wikitext):
    """wikitable 파싱 — rowspan으로 gloss/comparandum 상속 처리."""
    m = re.search(r'\{\|\s*class="wikitable".*?\n(.*?)\n\|\}', wikitext, re.S)
    if not m:
        log("!! wikitable 못 찾음"); sys.exit(1)
    body = m.group(1)
    # 헤더(! …) 제거하고 데이터 행만
    rows = re.split(r"\n\|-\n", body)
    records, carry_gloss, carry_comp = [], (None, 0), (None, 0)
    for row in rows:
        if "!" in row.split("\n")[0] and "||" not in row:
            continue  # 헤더 블록
        # 셀 추출: 줄별로, '||'로도 분할
        cells = []
        for line in row.split("\n"):
            line = line.strip()
            if not line.startswith("|") or line.startswith("|+") or line.startswith("|}"):
                continue
            line = line[1:]  # 선행 |
            for part in line.split("||"):
                rs = re.match(r'\s*rowspan="(\d+)"\s*\|(.*)', part, re.S)
                if rs:
                    cells.append((int(rs.group(1)), rs.group(2)))
                else:
                    cells.append((1, part))
        if not cells or all(not clean(c[1]) for c in cells):
            continue
        # script/MC/SK = 처음 3개; 그다음 gloss, comparandum (rowspan 상속)
        script = clean(cells[0][1]) if len(cells) > 0 else ""
        mc = clean(cells[1][1]) if len(cells) > 1 else ""
        sk = clean(cells[2][1]) if len(cells) > 2 else ""
        if len(cells) >= 5:
            gloss = clean(cells[3][1]); carry_gloss = (gloss, cells[3][0] - 1)
            comp = clean(cells[4][1]); carry_comp = (comp, cells[4][0] - 1)
        elif len(cells) == 4:
            # script만 1셀 줄였거나; gloss만 새로
            gloss = clean(cells[3][1]); carry_gloss = (gloss, cells[3][0] - 1)
            comp, carry_comp = carry_comp[0], (carry_comp[0], carry_comp[1] - 1)
        else:  # 3셀 — gloss/comp 상속
            gloss, carry_gloss = carry_gloss[0], (carry_gloss[0], carry_gloss[1] - 1)
            comp, carry_comp = carry_comp[0], (carry_comp[0], carry_comp[1] - 1)
        records.append(dict(script=script, mc=mc, sk=sk, gloss=gloss,
                            comparandum=comp, family=family(comp or "")))
    return records


def main():
    txt = ensure_raw()
    recs = parse(txt)
    cols = ["script", "mc", "sk", "gloss", "comparandum", "family"]
    with open(OUT, "w") as f:
        f.write("\t".join(cols) + "\n")
        for r in recs:
            f.write("\t".join(r[c] for c in cols) + "\n")
    log(f"\n[추출] {len(recs)}행 → {OUT}")
    # 소-N 벽 측정: 어족별 cognate 수
    from collections import Counter
    fam = Counter(r["family"] for r in recs)
    log("\n=== 비교어족별 cognate 수 (소-N 벽 측정) ===")
    for k, v in fam.most_common():
        log(f"  {k:10s} {v}")
    log(f"\n  ★ Japonic(=~3ky 노드 검정 분자) = {fam.get('Japonic',0)}개"
        f"  / POC-6·11 지평 ~15–20쌍")
    log("  → Koreanic/Tungusic은 *다른 가설*(계보 경쟁): 같은 셋이 세 어족에 분산")
    logf.close()


if __name__ == "__main__":
    main()
