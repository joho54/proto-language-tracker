"""POC-1: IPA/자질 정규화 검증 (PIPELINE.md §D)

검증 가정: PanPhon 자질표가 우리 AlignedPair.ipa 에 들어갈 IPA 분절을 커버하는가?
위험 케이스: PIE 재구표기(라링게알·음절성 공명음·구개수음), 산스크리트 유기음/권설음,
중세국어 특수자모(ㅸ/β z ɸ, ㆍ/ʌ), 라틴, 타밀.

성공 기준: 깨지는 분절 < 10%, 실패 케이스 목록화.
출력: 콘솔 요약 + poc/results/poc1_failures.tsv
"""
import unicodedata
from collections import Counter
from pathlib import Path
import panphon
from normalize import normalize_ipa

ft = panphon.FeatureTable()
NORMALIZE = True   # POC-1 발견 대응: 정규화 레이어 on/off 비교

# (family, gloss, ipa) — 의도적으로 어려운 케이스 포함
TESTS = [
    # --- PIE 재구표기 (표준 IPA 아님 — 핵심 위험) ---
    ("pie", "two",    "dwóh₁"),
    ("pie", "father", "ph₂tḗr"),
    ("pie", "heart",  "ḱḗr"),
    ("pie", "wolf",   "wĺ̥kʷos"),     # 음절성 l + labiovelar
    ("pie", "night",  "nókʷts"),
    ("pie", "horse",  "h₁éḱwos"),
    # --- Sanskrit (유기음·권설음) ---
    ("sanskrit", "brother", "bʰrātar"),
    ("sanskrit", "tooth",   "dant"),
    ("sanskrit", "fire",    "agní"),
    ("sanskrit", "snake",   "sarpá"),
    ("sanskrit", "retro",   "ʈʰa"),       # 권설 유기
    # --- Latin ---
    ("latin", "father", "pater"),
    ("latin", "night",  "noks"),
    ("latin", "king",   "reːks"),         # 장모음
    # --- Tamil/Dravidian ---
    ("tamil", "house",  "viːɖu"),
    ("tamil", "water",  "taɳɳiːr"),       # 권설 비음·장모음
    ("tamil", "eye",    "kaɳ"),
    # --- Korean (표준) ---
    ("korean", "water",  "mul"),
    ("korean", "father", "appa"),         # 경음
    ("korean", "star",   "pjʌl"),
    ("korean", "tense",  "k͈a"),           # 경음 표기(이중 부착)
    # --- Middle Korean (특수자모 — 핵심 위험) ---
    ("mk", "arae_a",   "hʌnʌl"),          # ㆍ /ʌ/
    ("mk", "bansiot",  "zəm"),            # ㅿ /z/
    ("mk", "sungewi",  "βi"),             # ㅸ /β/
    # --- Japonic ---
    ("japonic", "rain", "ame"),
    ("japonic", "mountain", "jama"),
]

COMBINING = {"́", "̄", "̀", "̂", "̃",  # accents/macron
             "̱", "̥", "̰"}  # syllabic/voiceless marks


def analyze(ipa: str):
    """반환: (validated, segs, dropped_chars)"""
    if NORMALIZE:
        ipa, _prosody = normalize_ipa(ipa)
    w = unicodedata.normalize("NFD", ipa)
    segs = ft.ipa_segs(w)
    recognized = Counter("".join(segs))
    allc = Counter(w)
    dropped = allc - recognized
    # 결합 부호 단독 드롭은 무해할 수 있으나 일단 모두 기록
    dropped_chars = [c for c in dropped.elements()]
    validated = ft.validate_word(w)
    return validated, segs, dropped_chars


def main():
    out = Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    fail_rows = ["family\tgloss\tipa\tvalidated\tn_segs\tdropped\tdropped_names"]

    per_family = {}
    total_segments = 0
    broken_segments = 0
    n_forms = 0
    n_forms_broken = 0

    for fam, gloss, ipa in TESTS:
        validated, segs, dropped = analyze(ipa)
        n_forms += 1
        total_segments += len(segs) + len(dropped)
        broken_segments += len(dropped)
        per_family.setdefault(fam, [0, 0])  # [forms, broken_forms]
        per_family[fam][0] += 1
        if dropped or not validated:
            n_forms_broken += 1
            per_family[fam][1] += 1
            names = "; ".join(
                f"{repr(c)}={unicodedata.name(c, '?')}" for c in dropped)
            fail_rows.append(
                f"{fam}\t{gloss}\t{ipa}\t{validated}\t{len(segs)}\t"
                f"{''.join(dropped)}\t{names}")

    (out / "poc1_failures.tsv").write_text("\n".join(fail_rows), encoding="utf-8")

    # ---- 요약 ----
    seg_break_rate = broken_segments / total_segments * 100 if total_segments else 0
    form_break_rate = n_forms_broken / n_forms * 100 if n_forms else 0
    print("=" * 60)
    print("POC-1: IPA/자질 정규화 검증 결과")
    print("=" * 60)
    print(f"폼: {n_forms}개 / 분절(추정): {total_segments}개")
    print(f"깨진 분절률: {seg_break_rate:.1f}%  (성공 기준 <10%)")
    print(f"문제 있는 폼: {n_forms_broken}/{n_forms} ({form_break_rate:.1f}%)")
    print("-" * 60)
    print(f"{'family':<10}{'forms':>7}{'broken':>8}{'rate':>8}")
    for fam, (f, b) in sorted(per_family.items()):
        print(f"{fam:<10}{f:>7}{b:>8}{b/f*100:>7.0f}%")
    print("-" * 60)
    verdict = "PASS" if seg_break_rate < 10 else "FAIL"
    print(f"판정: {verdict}  (분절 깨짐 {seg_break_rate:.1f}%)")
    print(f"실패 케이스: poc/results/poc1_failures.tsv ({len(fail_rows)-1}건)")

    # 자질 벡터 샘플 (작동 확인)
    print("-" * 60)
    sample = "pater"
    vecs = ft.word_to_vector_list(sample, numeric=True)
    print(f"자질벡터 예시 '{sample}': {len(vecs)} segs x {len(vecs[0])} features")


if __name__ == "__main__":
    main()
