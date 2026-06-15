"""POC-2: Wiktionary AlignedPair 추출 검증 (PIPELINE.md §D)

검증 가정: Wiktionary 재구/descendants에서 AlignedPair(스키마 A.3)를 뽑을 수 있나?
성공 기준: 정렬 스키마로 90%+ 표현 가능 + 추출 yield 확인.

발견(정찰): descendants는 중간 조어(cel-pro, itc-pro...)를 거치는 계층 트리.
→ 각 단계가 (proto→descendant) AlignedPair. 다중 시간심도 supervision 확보.
출력: poc/results/poc2_pairs.tsv, poc/results/poc2_issues.tsv
"""
import re, json, urllib.request, urllib.parse, unicodedata
from pathlib import Path
from normalize import normalize_ipa

UA = {"User-Agent": "proto-lang-tracker-poc/0.1 (research; contact joho0504)"}
API = "https://en.wiktionary.org/w/api.php?"

# PIE 어근 재구 페이지 (잘 알려진 것들; 없는 페이지는 스킵 = yield 측정에 포함)
ROOTS = [
    "ph₂tḗr", "méh₂tēr", "dwóh₁", "tréyes", "nókʷts", "ḱḗr",
    "pṓds", "ǵómbʰos", "swéḱs", "ḱwṓ", "h₂stḗr", "yugóm",
]

# Wiktionary 언어코드 → (이름, family, is_proto)
LANG = {
    "cel-pro": ("Proto-Celtic", "ie", True),
    "gem-pro": ("Proto-Germanic", "ie", True),
    "grk-pro": ("Proto-Hellenic", "ie", True),
    "iir-pro": ("Proto-Indo-Iranian", "ie", True),
    "itc-pro": ("Proto-Italic", "ie", True),
    "ine-bsl-pro": ("Proto-Balto-Slavic", "ie", True),
    "sla-pro": ("Proto-Slavic", "ie", True),
    "xcl": ("Classical Armenian", "ie", False),
    "la": ("Latin", "ie", False),
    "sa": ("Sanskrit", "ie", False),
    "grc": ("Ancient Greek", "ie", False),
    "got": ("Gothic", "ie", False),
    "xto": ("Tocharian A", "ie", False),
    "txb": ("Tocharian B", "ie", False),
}

DESC_RE = re.compile(r"\{\{desc(?:tree)?\|([a-z0-9-]+)\|([^|}]*)")


def fetch_wikitext(title: str):
    url = API + urllib.parse.urlencode(
        {"action": "parse", "page": "Reconstruction:Proto-Indo-European/" + title,
         "prop": "wikitext", "format": "json"})
    req = urllib.request.Request(url, headers=UA)
    try:
        d = json.load(urllib.request.urlopen(req, timeout=20))
        return d["parse"]["wikitext"]["*"]
    except Exception as e:
        return None


def clean_form(raw: str):
    """*표·링크·공백 제거 → 정규화 IPA. H(미지 라링게알 cover) → h."""
    f = raw.strip().lstrip("*").strip()
    f = f.replace("[[", "").replace("]]", "")
    f = f.replace("H", "h")          # 미지 라링게알 cover 기호
    if not f:
        return None
    ipa, prosody = normalize_ipa(f)
    return ipa, prosody, f


def main():
    out = Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    pairs = ["proto_lang\tdaughter_lang\tfamily\tdaughter_is_proto\tproto_ipa\tdaughter_ipa\traw"]
    issues = ["root\tcode\traw_form\tissue"]

    n_roots_found = 0
    n_pairs = 0
    n_unknown_lang = 0
    n_norm_fail = 0

    for root in ROOTS:
        wt = fetch_wikitext(root)
        if wt is None:
            issues.append(f"{root}\t-\t-\tPAGE_MISSING")
            continue
        n_roots_found += 1
        proto_norm = clean_form(root)
        proto_ipa = proto_norm[0] if proto_norm else root
        idx = wt.lower().find("descendants")
        section = wt[idx:] if idx >= 0 else ""
        for code, form in DESC_RE.findall(section):
            if code not in LANG:
                n_unknown_lang += 1
                issues.append(f"{root}\t{code}\t{form}\tUNKNOWN_LANG_CODE")
                continue
            name, fam, is_proto = LANG[code]
            cf = clean_form(form)
            if cf is None:
                n_norm_fail += 1
                issues.append(f"{root}\t{code}\t{form}\tEMPTY_OR_NORM_FAIL")
                continue
            d_ipa, d_pros, d_raw = cf
            pairs.append(f"PIE\t{name}\t{fam}\t{is_proto}\t{proto_ipa}\t{d_ipa}\t{d_raw}")
            n_pairs += 1

    (out / "poc2_pairs.tsv").write_text("\n".join(pairs), encoding="utf-8")
    (out / "poc2_issues.tsv").write_text("\n".join(issues), encoding="utf-8")

    total_desc = n_pairs + n_unknown_lang + n_norm_fail
    repr_rate = n_pairs / total_desc * 100 if total_desc else 0
    print("=" * 60)
    print("POC-2: Wiktionary AlignedPair 추출 결과")
    print("=" * 60)
    print(f"어근 페이지: {n_roots_found}/{len(ROOTS)} 존재")
    print(f"추출 descendant: {total_desc}개")
    print(f"  → AlignedPair 성공: {n_pairs}")
    print(f"  → 미등록 언어코드: {n_unknown_lang} (매핑 추가하면 회수 가능)")
    print(f"  → 정규화 실패: {n_norm_fail}")
    print(f"스키마 표현 가능률(등록 언어 기준): {n_pairs}/{n_pairs+n_norm_fail} = "
          f"{n_pairs/(n_pairs+n_norm_fail)*100 if (n_pairs+n_norm_fail) else 0:.1f}%")
    print(f"전체 회수율: {repr_rate:.1f}% (미등록 언어코드 포함)")
    verdict = "PASS" if (n_pairs+n_norm_fail) and n_pairs/(n_pairs+n_norm_fail) >= 0.9 else "REVIEW"
    print(f"판정: {verdict}")
    print(f"출력: poc/results/poc2_pairs.tsv ({n_pairs}쌍), poc2_issues.tsv")


if __name__ == "__main__":
    main()
