"""정규화/전사 변환 레이어 (POC-1 발견의 대응).

raw 재구표기/관례표기 → panphon 호환 IPA + 분리된 운율(prosody).
스키마 A.1: ipa = normalize_ipa(raw) 의 결과를 저장.

3종 처리:
  1) 운율 부호: macron(길이)→ː,  accent(강세)→prosody로 분리 저장
  2) 추상 재구기호: 라링게알 h₁h₂h₃ → 학설상 음가 (h, ħ, ʕ) [문서화된 선택]
  3) 표기 관례: 구개음 ḱǵ → kʲ ɡʲ, 한국어 경음 k͈ → kˀ
"""
import unicodedata

ACUTE = "́"   # 강세/구개 acute
MACRON = "̄"  # 장음
DVL = "͈"     # COMBINING DOUBLE VERTICAL LINE BELOW (한국어 경음)

# 라링게알: 학설상 음가 매핑 (h₁=h, h₂=ħ, h₃=ʕ) — 문서화된 가정
LARYNGEAL = {"h₁": "h", "h₂": "ħ", "h₃": "ʕ"}

# 구개음(자음+acute) → 구개화 표기
PALATAL = {"k": "kʲ", "g": "ɡʲ", "ǵ": "ɡʲ", "ḱ": "kʲ"}


def normalize_ipa(raw: str):
    """반환: (ipa_panphon호환, prosody_marks)"""
    s = unicodedata.normalize("NFD", raw)
    # ASCII↔IPA 함정: g(U+0067)→ɡ(U+0261), :→ː
    s = s.replace("g", "ɡ").replace(":", "ː")
    prosody = []

    # 1) 라링게알 (아래첨자) 먼저 — 합성형에서 처리
    for k, v in LARYNGEAL.items():
        kn = unicodedata.normalize("NFD", k)
        s = s.replace(kn, v)

    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        nxt = s[i + 1] if i + 1 < len(s) else ""
        if ch == MACRON:
            out.append("ː")                 # 길이 → ː
        elif ch == ACUTE:
            # 자음 뒤 acute = 구개음, 모음 뒤 = 강세
            base = out[-1] if out else ""
            if base in ("k", "ɡ", "g"):
                out[-1] = base.replace("g", "ɡ") + "ʲ"
            else:
                prosody.append("accent")    # 강세는 분리 저장
        elif ch == DVL:
            out.append("ˀ")                 # 경음 → ˀ (근사)
        else:
            out.append(ch)
        i += 1

    return "".join(out), prosody


if __name__ == "__main__":
    for raw in ["dwóh₁", "ph₂tḗr", "ḱḗr", "h₁éḱwos", "bʰrātar", "agní", "k͈a"]:
        ipa, pros = normalize_ipa(raw)
        print(f"{raw!r:14} -> {ipa!r:14} prosody={pros}")
