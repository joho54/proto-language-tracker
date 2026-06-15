# B 트랙 정찰 — 패러다임 동형성 재구 실현가능성 (deep-research, 2026-06-15)

> 106 에이전트 / 24 소스 / 25 주장 검증(21 확인·4 기각). 결론: **막다른 길 아님, 신규지만
> 미해결(signal vs noise) 문제를 떠안음.**

## 데이터 (form+function)
- **UniMorph**(170+ 언어), **MorphyNet**(15) — 셀 단위 (lemma, form, feature) ✓. 단 조어 패러다임·
  완전 패러다임 표 없음, 어족 커버리지 부족. https://unimorph.github.io/ , github.com/kbatsuren/MorphyNet
- **Grambank**(195 자질, 2467 변종)/WALS/AUTOTYP — 유형론 유무값, **형태 없음**. grambank.clld.org
- **Parabank (Glottobank)** — 패러다임 syncretism을 관계 신호로 쓰는 목적 설계. **개발 중·미공개.** glottobank.org
- 공개 재구 조어-패러다임 **gold standard 없음**(평가셋 부재). Wiktextract 굴절표는 미검증(gap).

## 선행연구
- 자동 재구는 **음운/어휘만** 입증: Bouchard-Côté 2013 PNAS(Austronesian, 85%+/1자). pnas.org/doi/10.1073/pnas.1204678110
- 정량 관계탐지: Akavarapu & Bhattacharya NAACL 2024 **likelihood-ratio test** — wordlist 기반. aclanthology.org/2024.naacl-long.141
- **패러다임-동형성 계산화 선행연구 = 없음 → 진정한 gap.**

## 이론 (양날)
- 최강 증거론: Meillet, Vovin(2005), Dybo & Starostin(2008) — 패러다임 형태론은 심층 관계의 최선 증거.
  단 비교법을 **보완**하지 대체 못 함(공통기원 입증 조건부).
- **한계(Robbeets)**: 패러다임 천년에 절반 붕괴(라틴 동사), Transeurasian은 IE보다 오래됨 →
  완전 패러다임 재구 "기대 불가". 대안=**copying-resistant 어간근접 형태소(상·태)+결합패턴**.
  blogs.uni-mainz.de/.../9-07Robbeets_neu.pdf
- **★Georg(2017) 반론 — 우리 케이스 정조준**: 형태소 모양 공간이 작아 **어휘보다 더 우연 충돌**,
  Transeurasian 접사가 무관 드라비다에 재현="노이즈와 구별 불가". (2-1 검증, 비합의·활발한 논쟁)
  academia.edu/34528557

## 시사점 (프로젝트)
1. **"형태론이 깊은 절반을 구한다"는 보장 없음** — Georg는 형태론이 *더* 위험할 수 있다고. 옵션 1 재고.
2. **방어 가능 설계**: ① Robbeets식 copying-resistant 형태소+결합패턴(완전 패러다임 말고) ② **명시적
   null/우연 모델**(LRT를 패러다임 셀에)로 Georg 격파. → ②는 우리 POC-6(순열검정·탐지 지평)과 동일.
3. **A의 null/지평 프레임워크가 B의 생사 도구.** 표현(이산/연속) 무관하게 null이 falsifiability 떠받침.

## 미해결(정찰이 남긴 것)
- Wiktextract 굴절표가 cross-family form+function 기질로 충분한가?
- 공개 재구 조어-패러다임 gold standard 존재하는가? (현재 없음으로 보임)
- 패러다임 셀 null 모델이 Georg의 소-인벤토리 우연충돌을 한-일본-드라비다에서 정량 격파 가능한가?
- ~5000년 심도에 형태론 신호가 우연 초과로 남아있나? (Robbeets 붕괴 + POC-6 지평 = 회의적)
