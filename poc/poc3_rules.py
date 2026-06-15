"""POC-3: SoundChangeRule 표현력 검증 (PIPELINE.md §D)

검증 가정: SoundChangeRule(A.4)이 실제 음법칙을 담고, 순서대로 적용 시 딸언어형을 재현하나?
케이스: PIE → Proto-Germanic (Grimm 법칙 + 라링게알/모음 + 부분 Verner).
정답지: POC-2가 추출한 Germanic 쌍.
측정: 규칙 적용 전/후 panphon 자질 편집거리. 규칙이 거리를 줄이면 성공(Phase 0 미니).

★ 핵심 검증: 규칙 순서(feeding/bleeding). aspirate→voiced→voiceless→fricative 순서가
  틀리면 bʰ→b→p→f 로 과적용됨. order가 표현력의 일부임을 보인다.
"""
from pathlib import Path
from panphon.distance import Distance

dist = Distance()

# ── 규칙을 strata(상대연대)로 분리 ──
# 핵심 교훈: Grimm 3군은 counterfeeding = 동시 적용. 출력이 후속 규칙에 먹히면 안 됨.
# → Grimm은 하나의 strata로 묶어 좌→우 1-pass 동시 적용(각 입력 1회 변환).

LARYNGEAL = [  # stratum A: 순차 OK (Grimm 이전)
    ("eħ", "aː"), ("oʕ", "oː"), ("ħ", "a"), ("h", ""), ("ʕ", ""),
]
GRIMM = {  # stratum B: 동시 적용 (longest-match transducer)
    "bʰ": "b", "dʰ": "d", "gʰ": "g",          # 1군 유성유기→유성
    "ɡʲ": "k", "ɡ": "k", "b": "p", "d": "t",  # 2군 유성→무성
    "kʷ": "h", "kʲ": "h", "p": "f", "t": "θ", "k": "h",  # 3군 무성→마찰
}
VERNER = [  # stratum C: 어말 마찰음 유성화 (강세 근사 — 한계는 발견으로 기록)
    ("s$", "z"), ("θ$", "d"),
]
VOWEL = [  # stratum D
    ("o", "a"), ("aː", "oː"),
]

# 정답지 (POC-2 추출, proto_ipa → attested) — 자음 골격 명확한 것 위주
PAIRS = [
    ("pħteːr",  "fadeːr", "father"),
    ("meħteːr", "moːdeːr","mother"),
    ("treyes",  "θriːz",  "three"),   # þ=θ 로 표기 통일
    ("nokʷts",  "nahts",  "night"),
    ("kʲeːr",   "hert",   "heart"),   # 어미 -ô 제외(파생)
    ("poːds",   "foːts",  "foot"),
    ("ɡʲombʰos","kambaz", "tooth"),
    ("swekʲs",  "sehs",   "six"),
]


def _seq(s, rules):
    for tgt, res in rules:
        s = s.replace(tgt, res)
    return s


def _simul_grimm(s):
    """좌→우 1-pass 동시 적용: 각 입력 분절을 정확히 1회 변환(counterfeeding)."""
    keys = sorted(GRIMM, key=len, reverse=True)  # longest-match
    out, i = [], 0
    while i < len(s):
        for k in keys:
            if s.startswith(k, i):
                out.append(GRIMM[k])   # 출력은 다시 매칭되지 않음
                i += len(k)
                break
        else:
            out.append(s[i]); i += 1
    return "".join(out)


def _verner(s):
    for pat, res in VERNER:
        if pat.endswith("$") and s.endswith(pat[:-1]):
            s = s[:-len(pat[:-1])] + res
    return s


def apply_rules(form: str, trace=False):
    s = _seq(form, LARYNGEAL)      # A
    s = _simul_grimm(s)            # B (동시)
    s = _verner(s)                 # C
    s = _seq(s, VOWEL)            # D
    return (s, []) if trace else s


def main():
    out = Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    rows = ["gloss\tPIE\trule_applied\tattested\td_before\td_after\tfired"]
    tot_before = tot_after = 0.0
    exact = 0

    print("=" * 72)
    print("POC-3: SoundChangeRule 정방향 적용 (PIE→Proto-Germanic)")
    print("=" * 72)
    print(f"{'gloss':<8}{'PIE':<10}{'→규칙적용':<12}{'실증':<10}{'전':>6}{'후':>6}")
    print("-" * 72)
    for pie, att, gloss in PAIRS:
        applied, fired = apply_rules(pie, trace=True)
        db = dist.feature_edit_distance(pie, att)
        da = dist.feature_edit_distance(applied, att)
        tot_before += db
        tot_after += da
        if da == 0:
            exact += 1
        mark = "✓" if da == 0 else ("↓" if da < db else "·")
        print(f"{gloss:<8}{pie:<10}{applied:<12}{att:<10}{db:>6.2f}{da:>6.2f} {mark}")
        rows.append(f"{gloss}\t{pie}\t{applied}\t{att}\t{db:.3f}\t{da:.3f}\t{','.join(fired)}")

    (out / "poc3_results.tsv").write_text("\n".join(rows), encoding="utf-8")
    n = len(PAIRS)
    print("-" * 72)
    print(f"평균 자질거리: {tot_before/n:.2f} (규칙 전) → {tot_after/n:.2f} (규칙 후)")
    print(f"완전 재현: {exact}/{n}")
    improved = tot_after < tot_before
    print(f"판정: {'PASS' if improved else 'FAIL'} "
          f"(규칙이 거리를 {(1-tot_after/tot_before)*100:.0f}% 감소)" )

    # counterfeeding 검증: 동시 vs 순차
    print("-" * 72)
    print("counterfeeding 검증 (Grimm은 동시 적용이어야 함):")
    demo = "ɡʲombʰos"  # tooth → kambaz
    seq_bad = _seq(demo, [(k, GRIMM[k]) for k in sorted(GRIMM, key=len, reverse=True)])
    print(f"  순차(틀림): {demo} → {seq_bad}  (출력 k,b가 재차 먹혀 과적용)")
    print(f"  동시(맞음): {demo} → {_simul_grimm(demo)}  (목표 자음골격 k_mb)")


if __name__ == "__main__":
    main()
