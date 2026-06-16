# 훈련 파이프라인 & 데이터 정의 (v0.1)

> 원칙: **데이터 계약(schema)을 먼저 고정**하고 파이프라인을 그 위에 얹는다.
> 삽질의 80%는 데이터 정의 실수에서 나온다 → 스키마가 SPEC의 §6 모델보다 먼저다.
> 관련: [SPEC.md](./SPEC.md) §5(데이터)·§6(모델 3층)·§7(평가).

---

## A. 데이터 계약 (핵심 — 여기가 틀리면 전부 틀림)

모든 레코드는 **출처(source) + 신뢰도(tier) + 시간심도(time_depth)** 를 필수로 가진다.
tier = `gold`(학술 확정) / `scholarly`(학술 가설) / `community`(편찬) / `scraped`(자동수집).
**tier는 절대 섞지 않는다** — gold만 supervision, community/scraped는 prior/noisy로만.

### A.1 `Form` — 모든 것의 원자
```yaml
form_id: str                  # 전역 고유
language: glottocode          # 예: stan1306 (표준한국어)
concept: concepticon_id       # 의미 정렬 키 (cherry-picking 방지)
raw: str                      # 원 표기 (재구표기·관례표기 포함)
ipa: [segment]                # ★정규화된★ panphon 호환 IPA (raw 아님 — POC-1)
prosody: [accent|tone|len]    # 운율 (segment에서 분리 — POC-1)
translit_profile: str         # 적용한 전사 프로파일 id (라링게알 가정 등 추적)
features: [feature_vector]    # segment별 distinctive feature (PanPhon)
morphs: [{form, gloss, type}] # 형태소 분절 (S_morph용; type=root/affix/clitic)
is_reconstructed: bool        # 조어형(*표) vs 실증형
time_depth: {era, year_est}   # 예: {Middle Korean, 1450}
source: citation_key
tier: gold|scholarly|community|scraped
exclude_flags: [loanword|onomatopoeia|nursery|wanderwort]  # §4 필터
```

### A.2 `CognateSet` — 동원어 묶음
```yaml
cogset_id: str
family: str                   # ie | dravidian | koreanic | japonic | control
concept: concepticon_id
members: [form_id]            # 딸언어 실증형들
proto_form_id: form_id|null   # 알려진 조어형 (gold면 supervision)
established_rules: [rule_id]  # 이 셋에 적용된 확립 음법칙 (Phase 0 gold)
```

### A.3 `AlignedPair` — **L1/L2 학습의 단위** (가장 중요)
```yaml
pair_id: str
proto: [segment]              # 조어형 분절
daughter: [segment]           # 딸언어형 분절
language: glottocode
alignment: [[i_proto, j_daughter]]   # segment 정렬 (gap = null)
applied_rules: [rule_id]|null
family: str
time_depth_delta: int         # 조어→딸언어 경과 (시간심도 비대칭 보정용)
tier: gold|...
```

### A.4 `SoundChangeRule` — symbolic layer (L1)
```yaml
rule_id: str
target: feature_bundle        # 변하는 대상 (자질 다발)
result: feature_bundle        # 결과
env_left: feature_regex       # 좌측 환경 (운율 참조 가능 — POC-3 Verner)
env_right: feature_regex      # 우측 환경
env_prosody: str|null         # 강세/위치 의존 (POC-3: Verner는 강세 필요)
scope: lexicon_wide           # 하드 제약: per-word 금지
family: str|universal
stratum: int                  # 상대연대 (POC-3)
mode: simultaneous|sequential # 동시(counterfeeding)/순차 (POC-3 핵심)
order_before: [rule_id]       # feeding/bleeding 부분순서
order_after: [rule_id]
naturalness: float|null       # L2가 채우는 prior 점수
source: citation_key
tier: gold|community
```

### A.5 `Reconstruction` — L3 출력
```yaml
cogset_id: str
posterior: [{proto_form: [segment], log_prob: float}]   # 분포 전체
map_form: [segment]
entropy: float                # 부패 엔트로피 = 엔트로피 역추적 산출
rule_set_posterior: [{rule_ids, prob}]
```

### A.6 `IsomorphismTest` — §6.4 입력
```yaml
system_A: {proto_forms: [Reconstruction], corr_table}
system_B: {proto_forms: [Reconstruction], corr_table}
concept_aligned: [[cogset_A, cogset_B]]
# → S_phon(MI), S_morph, S_dist(Mantel) 산출
```

---

## B. 훈련 파이프라인 (스테이지별 데이터 계약)

각 스테이지는 **무엇을 먹고 무엇을 뱉는지**가 고정 — 스테이지는 독립 교체 가능.

```
S0 Ingest/Normalize   raw 사전·wordlist ─▶ [Form]            (IPA화, tier·flag 태깅)
S1 Cognate Assembly   [Form]            ─▶ [CognateSet]      (concept+family 묶기, gold proto 부착)
S2 Alignment          [CognateSet]      ─▶ [AlignedPair]     (segment 정렬)
S3 Rule Acquisition   확립 음법칙+typology DB ─▶ [SoundChangeRule]  (gold 코딩 + 귀납 + prior)
S4 Corruption Sim     [proto]+[Rule]    ─▶ [AlignedPair(synthetic)]  (noising 증강)
S5 L2 Prior Train     [AlignedPair real+synth] ─▶ naturalness scorer
S6 L3 Reconstruct     [CognateSet(자료빈약)]+L2 ─▶ [Reconstruction]  (베이지안 역추론)
S7 L1 Verify Gate     [Reconstruction]+[Rule] ─▶ 검증된 재구만   (규칙성 하드 게이트)
S8 Isomorphism/Stats  [Reconstruction A,B] ─▶ S + p + 게이트 판정
```

데이터 흐름의 핵심 분기:
- **Phase 0/1 (정답 어족)**: S0→S1→S2→S3→S4→S5 + (S6→S7로 정답 재현 검증).
- **Phase 2 (자료빈약)**: 학습된 L2 prior를 들고 S6→S7→S8.

---

## C. 필요 데이터 리스트 (조달 방법별)

### C.1 즉시 확보 (다운로드/라이브러리)
- [ ] **PanPhon** — IPA→feature 벡터 (S0 필수)
- [ ] **CLTS** (List) — IPA 표준화, Lexibank 연동 (S0)
- [ ] **PHOIBLE** — 음소 인벤토리 (S0 보조)
- [ ] **Lexibank** (CLDF) — 다어족 표준 wordlist (S1)
- [ ] **Concepticon** — concept id 정규화 (S1)
- [ ] **DEDR** (UChicago 디지털판) — Dravidian (S1)
- [ ] **ABVD** — Austronesian (Phase 0 추가 어족)
- [ ] **NorthEuraLex** — Uralic 등 (Phase 0 추가)

### C.2 직접 구축 (스크래핑/파싱)
- [ ] **Wiktionary 재구 namespace + descendants 트리** → AlignedPair 주 소스 (S2)
- [ ] **Pokorny / LIV²** 파싱 → PIE 어근↔딸언어 (S1/S2)
- [ ] **국립국어원** 세종·역사·방언 자료 → Koreanic (S1)
- [ ] **上代 일본어 + 류큐 사전** → Japonic (S1)
- [ ] 대조군: **Basque** 어휘, **Sumerian** ePSD2 (S1)

### C.3 직접 코딩/큐레이션
- [ ] **확립 음법칙** (Grimm/Verner/Grassmann/satem; Krishnamurti Dravidian) → SoundChangeRule gold (S3)
- [ ] **typology DB**(Index Diachronica/DiACL/P-base) → naturalness prior (S3, **community tier**)

⚠️ **tier 오염 금지**: StarLing 장거리·Index Diachronica는 gold 절대 금지. 스키마 `tier` 필드로 강제.

---

## D. POC 리스트 (각 POC = 한 가정 de-risk)

규모 키우기 전에 **핵심 가정 6개**를 작은 실험으로 검증. 순서대로.

| POC | 검증 가정 | 최소 실험 | 성공 기준 |
|---|---|---|---|
| **POC-1** | IPA/자질 정규화가 우리 문자(한글·중세국어·산스크리트)에 통하나 | 어족별 50단어를 PanPhon/CLTS로 분절·자질화 | 깨지는 분절 < 10%, 실패 케이스 목록화 |
| **POC-2** | Wiktionary에서 AlignedPair를 뽑을 수 있나 (스키마 A.3 검증) | PIE→Latin/Sanskrit 100쌍 스크래핑 + 수작업 검수 | 정렬 스키마로 90%+ 표현 가능 |
| **POC-3** | SoundChangeRule 표현이 실제 음법칙을 담나 (A.4 검증) | Grimm 등 IE 법칙 5~10개 코딩 → PIE형에 정방향 적용 | 실증 딸언어형 재현율 측정 |
| **POC-4** | 부패 시뮬→역전(증강) 아이디어가 성립하나 | 조어형에 규칙 샘플 적용해 noising → 간단 모델로 denoise | 역전 정확도 > baseline |
| **POC-5** | 베이지안 재구가 정답 케이스를 맞추나 (Phase 0 미니) | Romance 3~4개로 proto-Romance 재구 → Latin과 비교 | 음소 편집거리 baseline 대비 개선 |
| **POC-6** | 통계 게이트가 sane 한가 (§7 검증) | 동계쌍 vs 무관쌍에 순열검정 | 동계=유의, 무관=무유의 |

POC-1·2가 **데이터 정의 검증의 핵심** — 여기서 스키마 A.1/A.3을 깨보고 고친 뒤 나머지로.

---

## POC-1 결과 (완료, PASS)

raw 표기를 panphon에 직접 넣으면 깨짐 14.8%(PIE 100%, 산스크리트 60%). 원인 3종:
1. **운율 부호**(강세 ´, 장음 ¯) 드롭 → macron→ː 변환, accent→`prosody`로 분리.
2. **추상 재구기호**(라링게알 h₁h₂h₃ 등 IPA 아님) → 전사 프로파일로 음가 가정
   (h₁=h, h₂=ħ, h₃=ʕ). ⚠️ **결과에 영향 주는 학설적 선택** → `translit_profile`로 추적·교체 가능하게.
3. **표기 관례 충돌**(구개음 ḱǵ의 acute, 한국어 경음 k͈, ASCII g≠IPA ɡ) → 변환표.

→ **정규화 레이어(`poc/normalize.py`)를 S0 앞단에 필수 배치.** 적용 후 7개 어족 깨짐 **0%**.
스키마 영향: `Form.ipa`는 정규화 결과만, `prosody`·`translit_profile` 필드 추가.

## POC-2 결과 (완료, PASS)

Wiktionary API에서 PIE 어근 10/12 페이지 추출, descendant 143개 중 등록 언어 81쌍 →
스키마 A.3 표현률 **100%**(정규화 실패 0). 발견:
1. **descendants는 계층 트리**(PIE→중간조어 cel-pro/itc-pro/iir-pro→실증어). 각 단계가
   AlignedPair → **다중 시간심도 supervision** 확보. S2는 재귀 트리 순회로 설계.
2. **실증어는 native script로 옴**(예: Armenian հայր) — IPA 아님. `{{desc|code|form|tr=...}}`의
   `tr=` 로마자전사 캡처 또는 epitran 필요. **중간 조어형은 이미 IPA식 라틴 → 더 깨끗한 supervision.**
3. 표기 cover 기호 다양: 라링게알 `h₂`(PIE) vs `H`(iir-pro 미지) 혼재 → translit_profile로 정규화.
4. 언어코드 매핑 확장 필요: hit(히타이트), ine-toc-pro, sqj-pro 등 추가 시 회수율 ↑.

스키마 영향: AlignedPair에 `script`/`translit_source` 추적 권장. 정렬(alignment) 컬럼 계산은
S2/POC-3 영역(추출 단계에선 미산출).

## POC-3 결과 (완료, PASS)

Grimm 법칙+라링게알+모음+부분 Verner를 SoundChangeRule(A.4)로 코딩, PIE→Proto-Germanic
8쌍에 정방향 적용. 평균 자질거리 0.78→0.53(**32%↓**), tooth 완전 재현. 발견:

1. **★ 규칙 엔진 의미론이 표현력의 일부.** Grimm은 **counterfeeding=동시 적용**.
   순차 rewrite 엔진은 출력이 후속 규칙에 먹혀 과적용(`ɡʲombʰos→homfos` 오류).
   좌→우 1-pass 동시 적용(각 입력 1회 변환)으로 수정 → `kombos`(정상), tooth 완전 재현.
   → SoundChangeRule에 **strata(상대연대) + 적용모드(동시/순차)** 필드 필요.
2. **Verner는 강세 위치 필요.** 어중 `θ→d`(father/mother) 미해결 잔차 = 강세 의존 규칙.
   → POC-1에서 prosody를 버리지 않은 결정이 옳았고, **prosody는 위치까지 보존**해야 함
   (단순 플래그 불가). SoundChangeRule.env 가 운율 참조 가능해야.
3. **모음 대응은 별도 규칙군 필요**(three의 ey→iː 등). 자음 골격은 규칙으로 강하게 재현되나
   모음은 추가 규칙 다수 필요 — Phase 1에서 데이터 귀납 비중 큼.
4. 측정 도구로 **panphon feature_edit_distance**가 Phase 0 평가(SPEC §7)에 적합함 확인.

스키마 영향: SoundChangeRule(A.4)에 `stratum:int`, `mode:simultaneous|sequential` 추가.

## POC-4 결과 (완료, PASS)

부패 정방향 시뮬(병합 포함 규칙 캐스케이드) → 역전(denoising) 학습. 세 가정 입증:
1. **denoising > identity** (seg 0.810 > 0.737): 정방향 부패는 학습으로 역전 가능 = **증강 전제 성립**.
2. **단일 daughter는 병합으로 완전복원 불가** (word-exact 0.35, 평균 엔트로피 0.386):
   정보 손실이 **엔트로피로 정량화**됨 (= 엔트로피 역추적 목표의 작동 증명).
3. **자매어↑ → 복원↑·엔트로피↓ 단조** (1→3개: acc 0.81→1.00, H 0.386→0.001, word-exact 0.35→1.00):
   comparative method가 병합을 해소. **"방언을 자매어로 동원"(R2) 결정의 정량 근거.**

★ 핵심: **엔트로피 = 병합 모호성 = 복원불가능성**, 자매어로 0 수렴. SPEC §6.3 엔트로피 기권과 직결.

⚠️ 한계(이상화된 시뮬): 치환전용(정렬 1-1), gold cognate set 가정, 문맥무관 역대응, 깨끗한 규칙.
실제는 삽입/삭제(정렬 난해)·미지 동원성·차용/유추 노이즈·적은 자매어 → 성능 저하 예상.
→ POC는 **논리**를 검증; 실제 난이도는 POC-5(실데이터 베이지안 재구)에서 측정.

## POC-7 결과 (완료, PASS — 하중 가정 첫 실데이터 지지)

질문: IE에서 배운 음변화 prior가 다른 어족에 전이되나? (프로젝트 하중 가정)
방법: 5개 유전 독립 어족(IE/Uralic/Austronesian/Japonic/Turkic) Wiktionary 중첩 트리의
parent→child 엣지(어족당 366~1306) → **자질-변화 토큰**(변경된 feature 이름 집합, 인벤토리 독립)
→ LOFO. 올바른 null = others 빈도형태 보존+유형라벨 셔플("흔한 건 어디서나 흔하다" 통제).

결과: **5어족 전부 "도움"**. 타어족 prior가 null보다 유의 우월(perm_p=0.003 전부), Spearman
전부 양수(0.16~0.35). **단 LL_자기 > LL_타 → 전이는 부분적**(prior로 유용하나 자기데이터 대체 불가).

★ 결론: 전이 실재하되 부분적 = PIE prior가 한국어에 **도움은 되나 한국어 방언 데이터를 대체 못 함**.
POC-4(자매어 필요)와 일치. 최악(해악) 아님 → 하중 가정 첫 지지.

⚠️ 한계: (1) 변화표현이 거침(방향·값 무시) → 이 grain에서의 전이; 세밀하면 약해질 수 있음.
(2) 엣지에 proto→proto 얕은 변화 포함, 정렬(panphon NW)·라틴정자법≈음소 가정의 노이즈.
(3) Japonic 토큰 적음(261). (4) 노이즈는 전이를 약화시킬 뿐 위조하진 않음(보수적).
엔지니어링: batch 페처(50p/요청)로 ~1000페이지를 ~20요청에 수집(wikt.py).

## POC-7 v3 결과 (kaikki 재실행 — 전이 결론 강화)

데이터 10~30배(IE 토큰 1.6k→11.8k)로 재실행. **5개 독립 어족(IE/Uralic/Turkic/Japonic/Sino-Tibetan)
전부 "도움"**, perm_p=0.003. **Spearman 상관 상승**(IE 0.16→0.26, Turkic 0.35→0.44) = 데이터↑에
신호↑ = 아티팩트 아님. **중국티베트어(IE와 최원거리·성조·고립어)도 전이 성립**(Spearman 0.28) →
보편성 강화. 단 여전히 LL_자기 > LL_타 = 전이는 부분적(일관). 미해결: Dravidian/Austronesian/Semitic
등은 kaikki 제목 상이(404)로 추가 필요.

## POC-5 결과 (완료 — 정직한 음성 결과: 실데이터 갭 큼)

kaikki PIE 1127 동원어셋(자손→PIE 재구, gold=Wiktionary PIE). forward-channel 베이지안(단순화).
- **재구(거리 2.05) > baseline(1.20)** = "가장 보수적 자손 그대로"가 우리 재구보다 나음. 완전복원 6%.
- **엔트로피는 자매어↑에 하락(2.56→0.48)** = 정보이론 스토리(POC-4) 성립하나, **확신이 정확도로 안 이어짐.**
- POC-4 완벽복원이 실데이터(PIE 심층·라링게알·ablaut)에서 무너짐 = **이상화↔실데이터 갭 큼.**

원인/한계: 재구기 조잡(문맥무관 채널, anchor-프레임 정렬이 indel에 취약, argmax smoothing) — SPEC §6
제대로 된 베이지안 모델 아님. PIE는 최난도(얕은 Romance→Latin은 더 쉬울 것, 미실행). gold가 재구형이라
거리 과대. ★교훈: **알려진 universal 확인(POC-7)은 쉬웠으나 실제 재구는 어렵다 — trivial baseline에도 미달.**
난이도·위험은 재구/Phase2에 집중. 다음: 문맥의존 채널·다중정렬·얕은 케이스(Romance→Latin)로 재시도.

## POC-5b 결과 (개선 재구기 — 심층 의존성 진단)

조잡한 재구(POC-5) 개선: **Viterbi + 조어 bigram 음소배열 LM**(greedy argmax 대신).
난이도 분리(같은 method, 얕음 vs 깊음):
- **Proto-Germanic(얕음): 재구 1.207 < baseline 1.778** (Δ+0.57) → **method 건전, baseline 이김.**
- **PIE(깊음): 재구 2.050 > baseline 1.134** (Δ−0.92) → 심층에서 baseline 미달(채널 흐려짐→LM이 그럴듯하나 틀린 조어 생성).

★ **재구 품질은 depth에 강하게 의존** = 얕으면 됨, 깊으면 벽. 한국어 표적(Koreanic↔Japonic↔Dravidian)은
깊은 관계 → Phase2 직접 위협. POC-4/5/7과 수렴: 얕으면 되고 깊은 데가 벽.

⚠️ PIE 깊은 테스트는 교란: 자손이 attested 아닌 분기조어(재구-위-재구), anchor가 거의-정답(1.13).
데이터 품질: 게르만 anchor가 urj-fin-pro(핀란드어 **차용어**) — SPEC §4 차용 배제 강제 필요.
다음(확정용): **PIE를 attested 자손(라틴·산스크리트·그리스)에서 다중정렬로 재구** → depth가 진짜 벽인지 확정.

## POC-5c 결과 (단계적 재구 — 쉬운 길 실패)

가설: 깊은 재구를 얕은 단계 연쇄로 분해(현대어→중간조어→PGmc)하면 직접보다 낫다.
결과: **단계적(1.716) ≈ 직접(1.666), 오히려 약간 나쁨.** 쉬운 길 실패.
원인: **오차 누적** — 각 단계가 오차 추가, 얕은 이점 상쇄. 특히 (1) 중간조어를 MAP 점추정으로
위로 흘려 **불확실성 소실**(진짜 비교재구법은 분포를 트리에 전파하며 동시추론), (2) step2 채널을
gold로 학습했으나 테스트는 재구형(노이즈) 입력 → train/test 불일치.
부수 확인: **depth penalty 실재** — PGmc를 현대어서 재구 1.67 vs 고대어서 1.21(POC-5b).

★ 결론: "깊은 재구 가능하게"의 쉬운 답(단순 chaining) 닫힘. 필요한 것 = (a) 불확실성 트리 전파
동시추론(Bouchard-Côté류), (b) 형태론·직교 자매어·전이 prior 등 추가 정보원 — 전부 미검증.
**깊은 재구 가능성은 여전히 미해결, 난이도 재확인.**

## POC-9 결과 (형태론 레버 1부 — 깊은 절반 못 구함)

가설: 닫힌 부류(문법형태소·대명사·수사)가 깊이서 더 보존 → 음운 막혀도 형태론으로 Phase2.
결과(PIE 트리, 정규화 자질거리):
- **얕음(d1-2): 닫힘 0.215 < 열림 0.314** ✓ (닫힌 부류 더 보존)
- **중간(d3-4): 역전** 닫힘 0.377 > 열림 0.346, bound형태소 0.435 더 나쁨
- **깊음(d5+): 닫힌 부류 n=0** (문법형태소가 깊은 자손까지 추적 안 됨)

원인/타격: (1) 형태론적 갱신=문법형태소는 보존되거나 통째 교체→깊이서 소실(n→0), (2) bound는
1~2분절이라 정규화거리 취약, (3) Wiktionary/kaikki가 문법형태소 descendants 미추적(n=0은 데이터 부재).
★ 결정적 단서: 측정한 건 형태소 **음운보존**이지 **패러다임 구조/(형태,기능) 대응 생존**이 아님 —
진짜 레버는 단어 descendant 트리로 **측정 불가**, 패러다임표·문법기술 등 다른 데이터 필요.
결론: 형태론 레버도 깊은 절반을 쉽게 구하지 못함. 진짜(구조) 버전은 미검증·데이터 의존.

## POC-6 결과 (통계 게이트 ✓ + 탐지 지평 정량화) — A 트랙 핵심 deliverable

게이트 sanity: 무관 p=0.917(기각✓), 관련 p=0.003(탐지✓) — 순열검정이 관련/무관 정확히 판별.
탐지 지평(동원어 생존율↓, depth=6 고정): 생존율 100~15%는 탐지✓(p=0.003), **8%에서 붕괴**(p=0.213).
★ 지평을 좌우하는 건 음변화 깊이가 아니라 **동원어 생존율**.

현실 연결: 기초어휘 보존 ~14%/천년(글로토크로놀로지, 논쟁적이나 규모감). 한-일본/드라비다 심도(~5천년+)
면 보존율이 한자릿수% 밑 → 측정 지평(~8-15%) 너머 → 모델이 "판정 불가"로 예측(학계 회의론과 일치).
→ 재범위화 deliverable 작동: 프로젝트="관계 증명기"가 아니라 "**판정가능 깊이를 재는 기계**".

## POC-10 결과 (이산 vs 연속 — 한계는 정보지 표현 아님)

가설 H-표현(연속/블랙박스가 약한 분산 신호를 건져 지평을 민다) vs H-정보(신호 파괴가 한계).
같은 동원어-손실 지평에 이산(분절 MI)·연속(자질벡터 회귀 R²) 나란히, 둘 다 순열검정 게이트:
- 둘 다 생존율 15·10%에서 탐지(p≈0.005~0.01), **8% 이하에서 *함께* 붕괴.**
→ **연속이 지평을 못 밂 = H-정보 지지.** 깊이의 한계는 표현이 아니라 정보(동원어 생존율). 블랙박스도
  파괴된 정보는 복원 못 함. + falsifiability는 null 검정이 지킴(표현 무관).
B-scout와 수렴: morphology도 탈출구 아님(Georg: 더 우연충돌), 방어책=null/우연 모델(표현 무관).

## POC-11 결과 (안정어 타겟팅 + 순환논증 함정)

사용자 아이디어: 전부 말고 깊이서 살아남는 안정 부분집합만 타겟. = 핵심어휘 비교(역사언어학 표준).
이질적 생존율(안정 0.93~0.99/불안정 0.5~0.7), (a)전체 vs (b)안정어 상위K(독립기준) 탐지 비교.
- (a)(b) 모두 깊이 8~60서 탐지(p≤0.01), **전체가 생존율 0.06서도 탐지** → 타겟팅 이점 없음(wash).
- ★이유: 검출은 동원어 *비율* 아니라 **절대 개수**에 의존(전체 300×0.06≈18 ≈ 안정80×0.21≈17).
  타겟팅은 비율↑·N↓로 개수 그대로. + **제대로 된 null 있으면 타겟팅 불필요**(순열검정이 노이즈희석 처리,
  진짜 동원어 ~15-20개면 탐지). 타겟팅은 null 없는 아마추어에게나 필요.
- ★순환논증 함정 실증: 무관 데이터 300쌍 중 **142개가 '그럴듯한 lookalike'**(fuku/paxu 등) — 결과 보고
  표본 고르면 무관 언어로도 가짜 '증거' 양산. 독립기준+null 필수.

종합(POC-9/10/11+B정찰 수렴): 한계=복원가능 동원어 **개수(정보)**, 어떤 표현·형태론·선택도 못 넘음.
유일 방어자산=**null 모델 기반 판정가능성 지평 측정**.

## POC-12/13 결과 (교체 유형화 — 계보 vs 접촉, 실데이터 검증)

POC-12(합성): A·B에 공유 차용층(출처 S) 심고, naive vs 차용유형화(typed) 검정.
- naive는 S1(관련)·S2(무관) **둘 다 유의**(차용이 가짜 계보 신호) = Georg 함정.
- typed(차용 제거)는 S1 p=0.005(계보✓)/S2 p=0.617(계보 기각) → **계보 vs 접촉 정확 구별**, 차용 117개 precision 1.0 복원.
- 교훈: 차용 탐지는 분절 *동일성* 거리(Levenshtein) — 자질거리는 무관어도 작아 못 씀.

POC-13(★실데이터, Tier-2): Maltese kaikki(IPA+gold 어원). 형태(IPA n-gram) NB로 차용(로망스/영어)
vs 계승(아랍) 분류 → gold 대조. **정확도 0.910(baseline 0.581), 차용 F1 0.921.**
→ 합성↔실데이터 간극 닫힘: **일탈(차용)이 실데이터서 형태 서명으로 추적 가능**(ground truth 확인).
한계: Maltese는 두 층이 음운적으로 뚜렷한 쉬운 케이스(상한급), 지도학습(라벨 필요-깊은 미지 케이스엔 없음),
gold 자체 노이즈(film→오라벨). 미지 케이스는 비지도 출처비교/문서화 차용 부트스트랩 필요.

검증 3-tier: Tier-1 합성(논리)✓, Tier-2 실데이터+정답(계측기)✓, Tier-3 실데이터+미지(한국어)=보조데이터·지평이 게이트.

## POC-14 결과 (2-모드 혼합 EM — 유형은 발견·판정된다)

"일탈 유형을 손으로 일일이 추가해야 하나?"의 답. 비지도 char-bigram 혼합 LM(K=2) EM (라벨 미사용):
- EM이 셈층/로망스층 **스스로 발견**: cluster→gold 76% 일치(baseline 58%), 차용 F1 0.764.
- **MDL/BIC: 2-모드(806,783) < 1-모드(816,508)** → 파라미터 페널티 내고도 분리가 데이터 더 압축 =
  **유형이 제값을 한다고 데이터가 승인**(가짜면 1-모드 택함=에피사이클 차단 작동).
→ 결론: 유형은 **EM이 발견 + MDL이 판정**. 손코딩 불요. 사용자 "일일이 추가" 불안 해소.
한계: 비지도 76%<지도 91%(POC-13), recall 0.67(토착화 차용 놓침); 이건 phonotactic 혼합(단순화)이지
카탈로그 끌림 전체모델 아님(출처데이터 넣으면 정밀도·접촉신호↑ 다음단계); EM은 *최강* 분리를 찾아 사후해석 필요.

## POC-15 결과 (카탈로그 끌림 모델 — 탐지/귀속 분리 + M1 출처귀속)

POC-14의 phonotactic 혼합("막연히 로망스 같다")을 *특정 출처 단어로의 끌림* `P_adapt(w|s)`
(학습된 noisy-channel)로 격상. 카탈로그 C = Maltese gold donor form 합집합(4081개, 이탈/시칠리아
어휘 프록시; 추가 다운로드 불요). 후보 가지치기 = char-bigram Jaccard 상위 40 (prefilter 천장 0.94).

★ **핵심 설계 발견 — 탐지(borrowed인가?)와 귀속(어느 출처?)은 다른 통계가 필요.**
- 카탈로그-조회 차용 채널은 *특정 출처에 조건부*라 확률 집중(per-char≈-2.3), 정규화 phonotactic
  bigram LM은 본질적 고엔트로피(per-char≈-5). → **raw 우도서 차용채널이 7394/7394(100%) 단어를
  이김 → 혼합 EM은 all-borrowed로 붕괴**(warm-start·항등 prior·logsumexp 다 시도해도 붕괴).
  어휘-밀도 이점은 길이 정규화로도 상쇄 안 됨(엔트로피 격차 실재); 토착층의 경쟁 저엔트로피
  모델(아랍 카탈로그)이 없으면 카탈로그 우도 단독으론 탐지 불가.
- 따라서 **탐지** = 길이정규화 적응비용 ⊕ phonotactic 판별의 비지도 결합 혼합,
  **귀속** = 카탈로그 끌림 argmax_s — 분리. (탐지 게이트로 차용 단어만 채널 정련 → 적응 sharpen.)

결과(Maltese, gold 어원 대조, 비지도):
- **탐지 F1 0.864 > POC-14 0.764** ✓ (acc 0.853, P 0.937, R 0.801). 카탈로그 비용(표면유사 명백차용
  =고정밀)과 phonotactic(토착화 차용=재현율)이 상보적 → 결합이 둘 다 초과.
- **출처식별 0.861** ✓ (3440/3996, 천장 0.94) — *어느* 이탈/시칠리아 단어에서 왔는지 복원.
  POC-14엔 없던 신규 능력(M1). 채널 정련이 v→b, o→u 등 체계적 적응 학습.
- 카탈로그 비용 *단독* 탐지는 F1 0.68(P0.92/R0.54, 토착화 차용 놓침) → phonotactic 결합 필수.

★ M1 프레이밍 갱신: SUMMARY §2.1은 "단일 P_adapt 우도 + MDL 게이트"가 유형을 발견·판정한다고
봤으나, POC-15는 **카탈로그 우도는 탐지를 못 한다(붕괴)**를 입증 — 탐지는 판별통계, 귀속은
생성 우도. 카탈로그 끌림의 진짜 기여는 *접촉 신호(출처 식별)*이지 탐지 자체가 아님.
한계: Maltese는 두 층 음운대비 뚜렷(상한급); donor가 라틴문자라 철자 정렬 가능(IPA 미사용);
출처귀속은 gold donor가 카탈로그+prefilter에 살아남은 경우만(천장 0.94). 코드 `poc/poc15_catalog.py`.

## POC-15b 결과 (용량 청구만으론 붕괴 못 푼다 — 척도통일 경로 확정)

SPEC §6.5의 원리적 코어 검증: 판별 융합(POC-15) 없이, **용량 청구(NML 취지 = 채널을 *무작위
데이터*에 대한 적합으로 정규화)** 만으로 raw 생성 혼합의 all-borrowed 붕괴가 풀리나? null 단어 =
전역 char-bigram Markov 생성(음소배열 그럴듯·의미 무작위), 채널별 per-char floor(zbor=-2.78,
zinh=-6.46)를 빼 "초과분"만 비교.

★ **결정적(분석+실증)**: `d_charged ≡ d_raw + 상수`(전 단어 동일 shift, distinct=1) →
**분리도(AUC) 완전 불변**(d_raw=d_charged). 용량 청구(상수 floor 정규화)는 **순수 임계값 이동**일
뿐 순위를 못 바꾼다 — borrowed 비율은 100%→89%로 움직이나 **F1·AUC는 그대로**. 이는 §6.5에서
정정한 *공유 UBM-LLR이 이항서 소거*되는 것과 **같은 구조**(상수/공통 정규화는 head-to-head에서 무력).
- 부수 발견: **nsim(카탈로그 비용) 단독 AUC 0.868 ≫ d_raw**(단일 전역 계승 LM은 AUC≈0.43으로 거의
  무용 → 빼면 신호 악화). POC-15 융합이 통한 건 *strata별 부트스트랩 LM 로그비*라는 진짜 **판별
  feature** 덕이지 생성 LM 차이가 아니었음.

→ **척도통일 기본 경로 = 판별 융합(채널별 보정/strata LM 로그비) 확정.** 순위를 바꾸는 판별
feature가 있어야 탐지가 됨; 상수 용량 청구·공유 배경은 임계만 옮긴다. 남은 *생성적* 대안 =
토착층에 동등 용량 카탈로그를 줘 대칭화(미검증, 보조데이터 필요 — §6.5/§11). 코드 `poc/poc15b_capacity.py`.
한계: NML을 상수 per-char floor로 근사(length-linear); 정확 NML(단어별 확률복잡도)은 더 비싸나
구조적 결론(상수 정규화=임계이동)은 불변. null은 전역 bigram이라 약간 로망스-편향.

## POC-17(a) 결과 (한자어층 분리 — 실데이터 VALIDATION, ≠발견)

목적: SUMMARY §7 (a) — 한자어(Sino-Korean)는 *문서화된 접촉층*(정답 있음)이므로 **발견이 아니라
validation**. Maltese(POC-13/15)를 한국어로 한 번 더 = 형태(IPA)만으로 한자어층을 분리할 수 있나 +
**비지도 분리 ≈ gold 분리인가** = 라벨 없는 논쟁 케이스에서 "진짜 동원어를 차용으로 오제거" 반격을
막는 *반증도구 신뢰성 보증*. gold = kaikki 어원템플릿 `ko-etym-sino`(한자어=접촉) vs `ko-etym-native`(고유어).
데이터: Korean kaikki 덤프(192MB, `data/kaikki/korean.jsonl`). homograph(양쪽 라벨) 203단어 제거,
unique 15706 (sino 12986 / native 2720, **불균형 83/17**). 코드 `poc/poc17_sino.py`.

결과:
1. **지도 NB(형태 신호 상한): acc 0.921, sino F1 0.951** (P 0.967 R 0.936). = Maltese(0.910)와 동급
   → **한자어층은 형태(IPA n-gram)만으로 강하게 분리가능.** 신호 실재 확정.
2. **비지도 naive 2-모드 EM: 붕괴** (acc 0.827=다수, 전부-sino R=1.0). MDL은 2-모드 채택하나 그 분리축이
   sino/native 아님 = **자연 불균형(83/17)서 majority mode로 흡수.**
3. **균형 subsample EM: acc 0.779, sino F1 0.783** (클러스터 {native,sino} 정확분리) ≈ Maltese 비지도(0.76).
   → ★ **붕괴 원인 = 대비 약함 아니라 불균형.** 균형 맞추면 비지도도 sino/native 축 복원.

★ 결론: 한자어층은 (지도) 깨끗이 분리되고 (비지도) *대비도 충분*하나, **실데이터 자연 불균형서 naive EM은
무용** → 라벨 없는 배치엔 **불균형 보정(π prior/class-weight) 또는 카탈로그 끌림(M1, 한자 음가 카탈로그)**이
필수. POC-15의 "phonotactic 단독 혼합은 약하다 → 카탈로그/판별 필요"가 한국어서 재확인.
한계: 이건 validation(정답 有) — 새 언어학 사실 0건. **discovery는 이 검증된 분리기를 *명명된 양성주장*
(Robbeets Koreanic↔Japonic 대응집합, 한-타밀 lookalike)에 걸어 차용·우연 제거 후 잔여를 null 지평에
대고 반증/제약하는 다음 수**(SUMMARY §7 (b)). 출력 `poc/results/poc17.tsv`·`poc17.log`.

## POC-17(a)-fix 결과 (M1 카탈로그로 불균형서 한자어 탐지 — 배치가능 분리기)

POC-17(a)서 naive 비지도 EM은 자연 불균형(83/17)서 majority-sino로 붕괴. POC-15의 M1(카탈로그
끌림)을 적용: **Sino 음절 카탈로그**(단일 한자 엔트리의 음 = `ko-hanja` head_template 마지막 인자,
465개) — ★어원라벨(`ko-etym-*`)과 **독립인 사전 사실** → 라벨 없는 discovery서도 외부자원만으로 재사용.
신호 = sino_frac(단어 음절 중 카탈로그 멤버 비율). 코드 `poc/poc17b_catalog.py`.

결과(자연 불균형, balancing 없음):
- **'전음절 Sino' 규칙: F1 0.936** (P 0.923 R 0.950) ≈ 지도 NB(0.951). naive EM이 붕괴한 조건서 작동.
- 융합(frac ⊕ 부트스트랩 phonotactic LLR): AUC 0.904, F1 0.938.
★ 결론: **카탈로그 M1이 불균형 보정 도구로 확정** — phonotactic 단독 비지도 혼합은 불균형서 무용이나
카탈로그가 구원. POC-15("탐지엔 판별/카탈로그 필요")가 한국어 실데이터서 재확인. 여전히 validation.

## POC-17(b) 결과 (Koreanic↔Japonic 고유어 — 명명된 주장 감사 = 첫 DISCOVERY, 정직한 음성)

검증된 분리기(17a/b)를 *명명된 양성주장*(Robbeets류 Koreanic↔Japonic 계보)에 건 **첫 discovery**.
proto-Japonic glossed(527개) ↔ Korean(한글, 영어 gloss 정렬), 개념 415 공유. 한글→coarse 음소,
분절 MI + 순열 null(nperm=2000). **naive(전체) vs typed(한자어 카탈로그 제거)** + **음성 대조군**
(Turkic=Transeurasian 공동주장, Uralic·IndoEuro=Koreanic 관계주장 없음). 코드 `poc/poc17c_korjap.py`.

| source | typed N | typed MI | typed p | naive p |
|---|---|---|---|---|
| **Japonic(주장)** | 287 | 0.519 | **0.051** | 0.375 |
| Turkic(공동주장) | 522 | 0.457 | 0.750 | 0.432 |
| **Uralic(무관)** | 309 | 0.496 | **0.053** | **0.023** |
| IndoEuro(무관) | 594 | 0.317 | 0.424 | 0.493 |

★ **결정적(음성)**: ① 첫 단발 실행은 typed Japonic p=0.043(nperm=300)이었으나 nperm=2000서 **p=0.051로
무유의** = 경계 노이즈. ② **무관 대조군 Uralic이 Japonic과 동급**(typed 0.053, naive 0.023로 *더* 강함)
→ Japonic의 경계신호는 **계보 특이적이 아님**. ③ MI가 **유형론 gradient**를 따름: 교착어 CV구조
(Japonic·Uralic·Korean 모두) 0.44~0.52 ≫ 굴절·자음군 IE 0.29. = 신호는 **유형론/areal 유사성이지 계보 아님.**

→ **판정: 이 증거 해상도서 Koreanic↔Japonic 계보는 우연·유형론과 구별 불가 = Robbeets류 주장의 제약/반증.**
Georg의 "노이즈와 구별불가"를 **대조군으로 *수치* 재현.** 무가치한 '판정불가 자체'가 아니라 명명된
주장에 대한 정직한 음성 결과. **★방법론 교훈(신규)**: 순열-쌍셔플 null은 *쌍짓기*만 통제하지 **유형론/areal
baseline은 통제 못 함** → proper null은 *유형론-매칭 대조군* 필요(POC-6/11 null 프레임 보강). 또 POC-11의
체리피킹 함정 실증: 대조군 없었다면 첫 p=0.043을 '발견'으로 오보할 뻔.

한계: ① coarse 한글→음소 매핑은 유형론-편향(자음군 손실) ② gloss 개념정렬 다의성(예: 'arm'→무장시키다=武裝)
③ proto-Japonic 작음(415개), **모던 일본어(한어 포함→공유-Sino 함정 극적)는 미실행**(355MB 다운로드 필요)
④ 개념당 최단어 1개(큐레이션 동원어셋 아님) ⑤ 순열 null은 유형론 baseline 미통제(위 교훈). 출력
`poc/results/poc17c.tsv`·`poc17c.log`.

## POC-17(d) 결과 (공유-Sino 함정 시연 — 모던 한-일, 정직한 역설)

목적: 모던 Korean↔Japanese에서 한자어(Sino-K)·한어(Sino-J)가 *둘 다 중국어 차용* → 공유 차용이
가짜 계보 신호를 내는 함정을 시연하고, typed 분해(양쪽 Sino 제거)가 제거하는지(양성통제). 3 조건,
기초어휘 근사(단일토큰 gloss) 개념정렬, 쌍 상한 700, nperm 1000. 코드 `poc/poc17d_korjap_modern.py`.

결과(전부 p=0.001 유의):
| 조건 | MI |
|---|---|
| naive(전체) | 0.92 |
| sino-only(양쪽 한어) | 0.76 |
| native-only(typed) | **1.02 (최강)** |

★ **역설(예상 실패가 더 중요한 발견)**: typed가 *가장 강함* — 함정 제거 실패. 원인: native-only가
**공유 서양 외래어(gairaigo)·고유명사**로 포화(acacia→아카시아/akashia, action→액션, Aaron→아론/Aron).
한자 카탈로그엔 안 잡히나(고유어 아님) 둘 다 영어/라틴 차용이라 음운 거의 동일. + 단일토큰 gloss 필터가
국제·기술 어휘(외래어)를 *선택*해버림.
→ **결론**: ① 모던 한-일 어휘는 **다층 공유차용(한자어+서양외래어+고유명사)으로 포화** → naive MI 0.92는
전부 차용. ② **단일 유형(한자어) 제거론 모던 데이터 정화 불가** — typed 분해는 유형이 *여럿* 필요(POC-16
정당화). ③ **모던어는 계보 검정에 부적합 → proto-level(17b)이 올바른 장소** (proto-Japonic은 차용 이전
재구 고유어층이라 깨끗). 역사언어학이 모던어 아닌 조어형/고대표기를 쓰는 이유를 *수치로* 재현.
한계: 기초어휘를 단일토큰 gloss로 근사(외래어 혼입) → 진짜 Swadesh 리스트·외래어 카탈로그 필요. 출력
`poc/results/poc17d.tsv`·`poc17d.log`.

## POC-17(e) 결과 (확정 동계어 깊이 사다리 — blind 반박, 17b의 키스톤)

17b 공백: 한-일이 무관 대조(Uralic)와 구별불가 → "신호 0"인지 "도구가 0만 본다(blind)"인지 미상.
닫는 법: *같은 파이프라인*(분절 MI + 순열 null)에 **깊이별 확정(gold) 동계어**를 통과시켜 검정력 측정.
확정 동계어 = kaikki proto 트리의 같은 어원 공유 자매(gold). 표기 전부 로마자라 동일 파이프라인.
코드 `poc/poc17e_ladder.py`. 참조 floor = 17b 한-일 typed/무관 Uralic MI≈0.50, p≈0.05.

| 칸 | 깊이 | N | MI | p | 셋업 |
|---|---|---|---|---|---|
| Germanic en↔de | ~1.5ky | 700 | 1.68 | .001 | 자매↔자매 |
| Germanic ang↔goh | ~1.5ky | 700 | 1.92 | .001 | 자매↔자매 |
| **IE itc-pro↔gem-pro** | **~5ky** | 590 | **1.30** | .001 | 자매↔자매(재구) |
| **IE iir-pro↔grk-pro** | **~5.5ky** | 499 | **1.22** | .001 | 자매↔자매(재구) |
| **IE itc-pro↔iir-pro** | **~5.5ky** | 591 | **1.30** | .001 | 자매↔자매(재구) |
| PGmc root↔en | ~2ky | 700 | 1.49 | .001 | **attested↔proto** |
| **PIE root↔la(라틴)** | **~5.5ky** | 700 | **1.04** | .001 | **★attested↔proto = 한-일 매칭** |

★ **결정적(blind 반박 성립)**: 도구는 ~5–5.5ky(=한-일 주장 깊이) 확정 IE 관계를 **MI 1.0–1.3, p=0.001로
명확히 탐지** — 한-일 floor(0.52)의 2–2.5배. 핵심 caveat(깊은 IE 칸은 proto↔proto라 쉬울 수 있음)도
**PIE root↔라틴**(한쪽 실증·한쪽 깊은재구 = 한-일과 *동일한 비대칭 셋업*)이 MI 1.04로 닫음 → proto↔proto
이점 아님. **결론: 도구는 한-일 깊이·셋업서 검정력이 있다 → 한-일이 floor에 붙은 건 도구 탓 아니라 대상 탓
= 17b 음성은 진짜 음성(blind 아님).**

→ 17b+17e 결합 = **검정력 보정된(calibrated) 음성 결과**. "한-일 어휘 신호는 ~5.5ky 확정 관계 수준에
미달하고 무관 유형론 대조와 구별불가"를 *검정력 증거와 함께* 주장 가능 = 신뢰가능한 음성 발견의 요건 충족.
한계: ja↔ryu·grc는 비라틴문자/희소로 스킵(코드·전사 이슈); 사다리는 IE·Germanic 위주(전사 용이). 출력
`poc/results/poc17e.tsv`·`poc17e.log`.

## POC-18 결과 (방향 A de-risk: Transeurasian 유사성 = 접촉? — 지리 감쇠 서명)

전환: 음성 falsifier(계보 반증) → **양성 발견**(접촉 탐지, 도구의 검증된 강점). 첫 de-risk =
"Transeurasian 유사성이 계보면 어족내 규칙적·어족간 지리무관, 접촉이면 어족간이 지리근접에 집중(감쇠)".
데이터 ASJP(글로벌, 100 기초개념, 좌표). 어휘유사=평균(1-LDN), 어족-간 쌍만 유사도~(-거리) Spearman +
Mantel 순열 + 다어족 대조지역(Africa 54어족). 코드 `poc/poc18_contact.py`.

| 지역 | 어족-간 N | ρ(유사~근접) | p | <1000km | >6000km |
|---|---|---|---|---|---|
| **Transeurasian-zone** | 22579 | **0.097** | .001 | **0.110** | 0.093 |
| 대조 Africa | 24411 | 0.011 | .047 | 0.098 | 0.098(평평) |

★ **결과(약하나 zone-특이적 양성)**: Transeurasian 어족-간 유사도가 지리근접에 집중(감쇠), 아프리카
대조는 **평평**(ρ 0.097 vs 0.011 ≈ 9배) → **접촉 성분 실재 = 방향 A에 맥박 있음.**
⚠️ **정직한 한계(중요)**: ① 신호 *약함*(ρ 0.097, 어족간 유사 ~0.10 = ASJP 우연 floor 근처 — 기초어휘
차용저항 예측대로) ② **유형론 교란 미분리**(우리 자신의 발견!): 근접 무관어의 areal *음운/음절구조* 수렴이
LDN을 부풀릴 수 있어 — *차용된 단어*인지 *닮은 음운*인지 평균 LDN으론 구별 못 함 ③ 근접 bin n=473 작음
④ Turkic(78언어) 편중 가능 — 한 어족쌍이 끌 수 있음(미점검).
→ **판정: 맥박은 있으나 smoking gun 아님.** 양성 발견엔 (a) *문화어휘* 풍부 데이터(NorthEuraLex, 차용이
실제 사는 곳; ASJP 기초어휘론 얇음) (b) 평균유사 아닌 *공유 어휘항목(Wanderwörter)* 격리(유형론 수렴 배제)
(c) 방향성·연대 (d) aDNA/고고학 삼각측량 = 큰 프로그램. 출력 `poc/results/poc18.tsv`·`poc18.log`.

## POC-20 명세 + 결과 (삼각측량 정합검정 — 양성 방향, §4.1⑤ operationalize)

> ⚠️ POC-18까지가 §4.1(정보이론 바닥)로 수렴한 *닫힌* 로드맵. POC-20은 그 **밖의 신규 노드** —
> "양성 모델 밀기"가 아니라 *남의 양성 시나리오에 정직한 CI 달기*. 넓은 CI·floor도 산출물.

### 명세
- **목적**: 음성-결과 도구(유형론통제 null·검정력 사다리·탐지지평)를 *양성 시나리오 감사*에 적용.
  깊은 proto 분기(~5ky)는 엔트로피 벽(17b/e 음성)이나, **~3ky Yayoi 도래 노드**는 aDNA가 연대·방향을
  주고(Cooke 2021류 반도→일본 유입 ~BCE900) 재구봉투 *안*(17e 사다리상 검정력권) = 양성 가능 유일 자리.
- **방법**: 반도 Japonic form 증인(Tier-A 검정셋) ↔ Old Japanese 비교항 사이 분절 대응(MI)을 chance-null +
  **유형론-매칭 대조군**으로 검정. 산출 = "관계 증명"❌ → **신호 = X ± CI**(Robbeets가 빠뜨린 오차범위).
- **성공기준**: 정직한 CI 반환 자체가 성공. 넓은 CI/floor = 단정의 반례로 유효.
- **데이터 계약**: 검정셋은 *학자별* 재구를 *경쟁가설*로 병렬 적재(tier=scholarly). 판독 합의 없음을
  숨기지 않고 CI가 span. 코드 `poc/poc20*.py`, 캐시 `data/pjaponic/`.

### Tier-A 결과 (검정셋 확보 = POC-20 분자)
- **20(Set A, Baxter MC)**: 삼국사기37 glosses(Wikipedia/Lee&Ramsey/Itabashi 통합) → 30행/24 distinct,
  **Japonic 8 / Koreanic 14 / Tungusic 2**. 같은 코퍼스가 세 어족에 분산 = 논쟁을 데이터가 자백. `poc20_pjaponic.py`.
- **20b(머지, 두 독립 재구)**: Set A(Baxter) ⊕ Set B(Ulman/Pulleyblank EMC, openreview PDF, 21 Japonic).
  - **A∩B 견고 핵심 = 7**(three·five·seven·ten·water·valley·rabbit) → 지평(~15–20) **밑**.
  - **A∪B 최대주의 = 22** → 지평 **위**.
  - ★ **정직한 CI = [견고 7 … 최대 22]**. 점추정 불가 = 지평 통과 여부가 *재구 가정에 의존* = 측정된 오차범위.
  - 구조적 발견: 견고 7은 전부 Swadesh = Georg 우연충돌 최고위험; 진단력 문화어(곰·버들 14)는 재구-취약.
    **살아남는 건 우연에 약하고 진단력 있는 건 재구에 약함** = 한-일 난이도의 정량 초상. `poc20b_ulman_merge.py`.

### step-1 결과 (chance-null, CI 양 끝) — ★ denominator 필요를 수치로 입증
같은 MI·순열 기계(poc17c) 재사용. 반도재구↔OJ coarse 음소쌍, nperm=5000:

| set | N | MI | p |
|---|---|---|---|
| robust(A∩B) | 7 | **1.65** | .0008 |
| max(A∪B) | 22 | **1.57** | .0002 |

★ **함정 실증(핵심)**: 양 끝 다 '유의'(p<.001)인데 **MI 1.6 > POC-17e 확정 ~5.5ky IE 동계어(1.0–1.3).**
진짜 5천년 관계가 확정 IE보다 깨끗할 수 없다 → 이 부풀림 = **사전선별 편향**. 검정셋은 *학자가 닮은 것만
골라낸* 목록이라 쌍-셔플 null이 "자기 짝에 특이적인가"만 봐서 *너무 쉽다* = **POC-11 체리피킹 함정의
실데이터 재현**(이번엔 진짜 Koguryo 데이터로). 즉 **사전선별 cognate 목록은 검정 대상이 될 수 없다.**
→ **판정**: '유의'는 관계 확정 ❌. 정직한 검정 = **130 지명 denominator**(안 닮은 ~64 포함 → null에 기각후보
포함) + **유형론-매칭 대조군**(17b 교훈). step-1 = 하니스 가동 + denominator 요구 입증. `poc20c_chance.py`.

### 다음 (step-2)
- Ulman 130 지명 *전체* 전사 확보(현재 매칭 부분집합만 추출됨) → coverage rate(반도 지명 중 J-매칭 비율)
  vs chance baseline(무작위 EMC 음절↔OJ 기초어휘 우연 매칭률). + 유형론-매칭 무관 대조군.
- Beckwith 2004 80셋 backfill(견고 핵심이 7→? 커지는지, 세 번째 독립 재구) — Brill 유료/altaica 미러.
- aDNA Yayoi 노드 연대(~3ky)에 신호 CI를 묶어 *삼각측량 정합* 보고(§4.1⑤).

## POC-21 사전등록 (denominator + 유형론 대조군) — ⚠️ 돌리기 *전*에 고정

> step-1(POC-20c)이 입증: 사후에 보면 사전선별 셋은 무조건 부풀려진다(MI 1.6 > 확정 IE).
> ∴ POC-21은 **설계·예측·임계를 결과 보기 전에 못 박는다.** 이 블록 수정은 데이터 본 *뒤* 금지.

### 검정 설계 (고정)
- **분자(denominator)**: Ulman 130 지명 *전체*(매칭 부분집합 아님 — 안 닮은 ~64 포함). coverage =
  지명 중 "OJ 비교항에 매칭되는 형태소 ≥1개" 비율. Ulman 보고치 ≈ 강 26/130, 강+약 66/130.
- **매칭기준(고정)**: 형태소의 coarse 음소형이 *같은 개념*의 OJ 단어와 정규화 편집유사도 ≥ 0.5.
  (coarse 매핑·align은 poc20c와 동일. 임계 0.5는 사전고정 — 결과 보고 조정 금지.)
- **null #1 (의미-순열)**: OJ 단어의 *의미 라벨* 셔플 → "맞는 의미"에 닮는 게 "아무 의미"보다 초과인가.
  OJ는 작은 (C)V 인벤토리라 짧은 단어가 우연 매칭 多 → 이 null이 진짜 baseline.
- **null #2 (유형론-매칭 대조군, 고정)**: OJ 워드리스트를 *무관 CV 언어*로 교체해 같은 coverage 측정.
  대조군 = **proto-Uralic + proto-Turkic**(캐시됨; 17b서 Uralic이 Japonic과 동급 = 적대적 대조군 검증됨).
- **OJ 워드리스트(고정)**: `data/kaikki/protojaponic.jsonl`(527 glossed, 17c와 동일 소스). 재현성 위해 잠금.
- **핵심 측정값**: `Δ = coverage(Japonic) − coverage(대조군)`, 그리고 의미-순열 null 대비 p.

### 사전등록 예측 (결과 판정 규칙 — 미리)
- **① floor/무판정** (가장 유력, 17b 정합): Japonic coverage ≈ 대조군 → "이 해상도서 지명 증거는
  우연·유형론과 구별불가". Beckwith 최대주의 제약, 회의론 일치. **넓은 CI.** ← step-1 MI 부풀림이 통제 후 소멸 시.
- **② 약한 *구조화* 양성** (실재 가능, 가장 방어가능한 양성): coverage가 대조군 초과하되 **남부(한강
  유역 漢州) 집중·북부 floor** = Vovin 지리 gradient. → "Peninsular Japonic=남부 substrate"만 지지,
  "Koguryo=Japonic"(Beckwith)·"심층 한-일 계보"(Robbeets)는 **아님.** *지리 분할 자체가 진단 신호.*
- **③ 깨끗한 강한 양성** (안 나와야 정상): 어디서나 대조군 ≫ → 17b/Tian과 모순. **매칭기준 과대·OJ
  워드리스트 과관대를 먼저 의심·배제하기 전엔 양성으로 안 침.** (step-1 함정 재발 방지 — 미리 회의 약속.)

### 성공기준
- 양성이 아니라 **교정된 CI**가 성공: `Δ = X ± CI` 산출 + ①/②/③ 판정. 부호 무관, 대조군 대비 정직한 구간이면 OK.
- ②/③ 구분 규칙(고정): 신호가 남부>북부 gradient면 ②(substrate), 균일/북부편중이면 ③(아티팩트 의심).

### 선결 데이터 [step-2 완료]
- **denominator 확보**: 삼국사기 권37 전체 34 item 스크랩·캐시(`data/pjaponic/sg37_cache/`, idempotent,
  `poc/poc21_scrape.py`) → **286 old↔new 지명쌍**(고구려 漢州·朔州·溟州 + 백제). Ulman 130 ≫.
  의미 = old 음차명 ↔ new 의역명 정렬로 도출(買忽→水城 ⇒ 買=water). 섹션이 지역별 = ②/③ 지리 gradient 검정 직결.
- **poc21b 실행 결과 (a·b·c) — ★정직한 방법론 발견(아티팩트, floor 아님)**:
  - (a) 음가 = Baxter-Sagart MC 4056자(`data/pjaponic/baxtersagart.tsv`) + 한국한자음 폴백 3963자 ✓.
  - (b) old↔new **위치정렬 무효**: 파싱된 쌍 대부분이 *번역이 아닌 757 경덕왕 개명*(南川→黃武, 乃買→旌善)
    → 의미 오주입(南=yellow 식). 음차↔의역 대응이 아님.
  - (c) coverage Jap 0.00 / Ur 0.00 / Tk 0.01 (`poc21b.tsv`). **이 ≈0은 floor가 아니라 (b) 오류의 산물** —
    스크립트의 "① floor" 자동판정은 **무효**(깨진 파이프라인의 거짓 음성; floor로 보고 금지).
  - ★ **발견**: denominator를 *기계적으로 의미-태깅 불가*. 의미원천은 (i) 異名(一云/…로도 일컬었다, **104쌍**
    추출됨; 의역↔음차 예: 獐項↔古斯也忽次, 童子↔仇斯, 牛岑↔首) 또는 (ii) Ulman/Beckwith 수작업셋뿐.
    異名조차 형태소 정렬이 비위치적(3자↔5자) → **형태소 매핑에 scholarly 판단 환원불가 = 손-큐레이션 셋이
    존재하는 이유.** 프로젝트 핵심명제(증인=손-큐레이션, 계산이 못 만듦)를 지명 데이터서 재확인.
### poc21c 결과 (異名 기반 유효 검정) — ★ 첫 *유효* 교정 음성 (① floor)
의미원천을 異名(一云/…로도 일컬었다)으로 교체 → 21b 아티팩트 해소. 장소단위(의역 글자 의미 ↔ 음차
글자 음가 교차) coverage, 다임계(0.4/0.5/0.6) + Uralic/Turkic 대조 + 의미순열 null. 코드 `poc21c_alternation.py`.

| 임계 | Jap | Ur | Tk | Δ=Jap−maxCtrl |
|---|---|---|---|---|
| 0.4 | 0.154 | 0.115 | 0.173 | −0.019 |
| 0.5 | 0.077 | 0.038 | 0.154 | −0.077 |
| 0.6 | 0.058 | 0.000 | 0.000 | +0.058 |

- **Δ 구간 = [−0.077 … +0.058], 0 포함.** Turkic 대조군이 Japonic 이상 매칭(0.4·0.5).
- **의미순열 null: obs 4, null평균 4.8, p=0.685** → Japonic이 우연 못 넘음. (thr0.6 +0.058=3/52 소수노이즈; perm p가 결정 → ①.)
- **판정: ① floor — 반도 Japonic 지명신호 = 유형론 대조군·우연과 구별불가.** 17b·Vovin/Tian 정합.
  ★21b와 달리 의미가 異名 실데이터 = **유효한 floor**. Robbeets가 못 단 오차범위를 단 첫 *유효* 결과(§4.1⑤).
- **정직한 한계(약한 음성, 결정적 아님)**: ① sim≥0.5 하드임계 과엄(짧은 형태소; step-1 MI가 더 적합) —
  진짜 cognate(古斯/deer, 仇/child)도 탈락 가능. ② 개념풀링이 음차측 가짜글로스 섞어 큰사전(Turkic)
  유리 — 단 perm p=0.69라 고쳐도 신호 無, ① robust. ③ N=52 + 異名이 0020섹션 집중 → ②/③ 지리검정
  미작동(전체 신호 없어 지역화 불요). ④ Beckwith 80셋 교차 미실행.
- **다음(선택)**: 검정통계를 coverage→MI(step-1식)로 교체해 임계 과엄 제거 후 재확인; 異名 패턴 확장
  (一云/一名/或云)으로 N·지역 확대; Beckwith 80셋 교차. 단 ① 결론은 다축(대조군·null·다임계)서 일관.

## 데이터 레이어 전환 (kaikki.org / wiktextract) — 캐노니컬

Wikimedia Action API 직접 스크래핑(`wikt.py`)은 **429 하드 throttle**(Retry-After 48s 강제)로
대량 수집 비현실적. → **kaikki.org(wiktextract) JSONL 덤프**로 전환 (`poc/kaikki.py`).
- **완전 오프라인·rate-limit 없음**: 한 번 받아 `data/kaikki/` 영구 캐시 (CLAUDE.md 1순위 부합).
- **구조화된 descendants 트리** 제공 → 정규식 wikitext 파싱 불필요.
- **데이터 10~30배**: PIE 36.8k 엣지(이전 wikitext ~631), Turkic 27.9k, Japonic 8.8k, Uralic 4.4k.
- proto 언어 파일은 작음(1~12MB). 일반어(예: Latin)는 1.2GB → 필요 시 스트리밍 필터.
- 미해결: Proto-Austronesian은 kaikki 제목 상이(404) → 정확 명칭 확인 필요.

→ POC-7(전이) 등 데이터 굶주린 실험을 이 레이어로 **오프라인 재실행** 가능. `wikt.py`는 폴백.

## E. 미해결 (데이터 정의 관련)
- [ ] glottocode vs 자체 언어 ID 체계 — Lexibank 호환 위해 glottocode 권장.
- [ ] 형태소 분절(morphs) 자동화 vs 수작업 — Koreanic은 수작업 불가피.
- [ ] 중세국어/上代 표기의 IPA 변환 신뢰도 (POC-1에서 판정).
- [ ] synthetic 비율 (real:synth) — POC-4 후 결정.
