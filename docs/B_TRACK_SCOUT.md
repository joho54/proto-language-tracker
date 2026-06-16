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

---

# 정찰 2 — null/검정력 축 신규성 (deep-research, 2026-06-16)

> 102 에이전트 / 20 소스 / 25 주장 검증(23 확인). POC-17 방법론 3주장의 선행연구 판정.
> **결론: 세 주장 다 PARTIAL(부분신규) — 구성요소는 선행 있으나 *통합+적대적 시연*은 미선점.**

## 주장별 판정

**CLAIM 1 — 유형론-교란 null = PARTIAL (적대적 시연은 신규)**
- 표준 macro-comparison null은 *실제로* 쌍/개념 셔플 순열(LexStat: List/Greenhill/Gray 2017; LDND: Wichmann et al. 2010; Kessler 2001; Oswalt; Turchin). ✓ 우리 가정 맞음.
- **유형론/인벤토리 교란은 *인지*되고 *부분교정*됨**: LDND가 mismatched-concept 분모로 "공유 음구조 유사성"을 중화하려 설계. Kassian 2023은 Swadesh 안정성 가중+음성대조 보정. **단 휴리스틱이지 false-positive 통제 입증 아님.**
- **★공백**: *유형론 유사 무관쌍이 관련쌍과 동급의 가짜 유의를 낸다*를 명시 시연한 선행 = 못 찾음. 우리 Uralic≈Japonic 적대적 시연이 신규.

**CLAIM 2 — 확정 동계어 검정력 사다리 = PARTIAL (사다리 프로토콜은 신규)**
- **단발 양성통제는 선행**: Ringe 1999가 IE(16/24 매치, off-the-chart)를 양성통제로, Amerind를 음성으로. *단 단일 케이스, 등급 사다리 아님.*
- ~6000–10000년 비교법 지평은 확립(Nichols; Pellard/Vovin). 기지-연대 보정은 *연대측정*엔 표준(Rama/Holman 2013, 52점 r=0.77) — **검정력엔 아님.**
- **★공백**: *깊이를 올려가며 검정력을 보정해 음성을 정당화*하는 명명된 프로토콜 = 없음. 우리 사다리(Germanic 1.5ky→IE 5.5ky)가 신규.

**CLAIM 3 — 문서화 차용층 분해+null = PARTIAL (통합 파이프라인은 신규)**
- 자동 차용탐지·"차용을 먼저 배제" 교리는 확립(List & Forkel 2021, F=0.87). 단 *미지* 차용 탐지·접촉연구 목적.
- **★Tian/Wichmann/List 2022 (bioRxiv) — 우리와 가장 가까운 선행**: Sino-Korean 차용 1개 제외 → **Robbeets 3166 동원어셋이 17개로 붕괴**. 단 *item-level 비판*이지 null-결합 파이프라인 아님. (Robbeets 반박 bioRxiv 2022.10.05.510045 = 활발한 논쟁.)
- Miller et al. 2020: 단일언어 wordlist 차용탐지(SVM/RNN) — 실데이터 저조 → **외부 문서 카탈로그(한자 음가)가 메우는 공백.**
- **★공백**: *문서화 카탈로그 차용제거를 chance null 앞 전처리로 통합*한 파이프라인 = 없음.

## 통합 판정 (핵심)
**네 통제(차용제거+chance null+검정력보정+유형론통제)를 한 도구로 묶은 선행 = 없음.** 각 조각은 다른 논문에 흩어짐. **방어가능 신규성 = ① 통합 ② 유형론-교란 적대적 시연 ③ 깊이 검정력 사다리를 묶은 *음성결과 프로토콜*.** 한-일 적용(native층이 무관 Uralic과 구별불가, 유형론 추적)은 주류 회의론(Vovin/Pellard)과 *일치하나 방법론적으로 구별됨*.

## ★전략 시사 (중요)
1. **선점 위험 = Tian/Wichmann/List 2022.** 우리가 "한-일 반증"만 내세우면 그들과 겹침(그들은 이미 Nature Robbeets를 17개로 붕괴시킴). → **우리 차별점은 *반증 자체*가 아니라 *방법(통합 falsifier+검정력 사다리+유형론 적대시연)*.** 한-일은 시연 케이스.
2. **가장 인용가능한 단일 신규 = 유형론-교란 적대적 시연**(무관 Uralic이 Japonic 동급). 이건 표준 null의 결함을 *수치로* 박는 것 — Claim 1 공백 정조준.
3. **논문 프레임**: "매크로비교 음성주장을 위한 검정력보정·유형론통제·차용분해 falsifier" (방법) + 한-일 시연. Tian과 충돌 아닌 *상위 일반화*.

## 미해결 (정찰이 남긴 것)
- 2024–2026 최신에 유형론-유사 무관쌍 가짜유의 시연이 나왔나? (Claim 1 선점 여부)
- Oswalt shift test·Turchin의 정확한 null이 인벤토리/유형론 통제를 이미 품었나?
- 한-일 음성이 Robbeets의 "동원어수 vs 연대"·"적은 딸언어" 반론에 견고한가?
- Tian 2022 vs Robbeets 반박(2022.10.05.510045) 논쟁의 현 상태?
