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
