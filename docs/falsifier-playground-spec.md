# Falsifier Playground: 대화형 시각화 데모 Spec

> **Status:** Draft
> **Date:** 2026-06-16
> **Author:** (auto-generated)
> **목적:** falsifier(계보 검정) 추론 과정을 단계별로 시각화하는 교육용 웹 데모. 연구 신규성 아님 — *학습/포트폴리오*.

---

## 1. Background

### 1.1 현재 상태
- 이 프로젝트의 falsifier 코어는 **결정론적 파이프라인**이다: 개념정렬 → 분절정렬(NW) → 대응표 P(x,y) → MI(스칼라) → 순열 null → 판정(p / 지평).
- 이미 검증된 구현체가 있다: `poc/poc17c_korjap.py`(한–일 감사), `poc/poc17e_ladder.py`(검정력 사다리). 둘 다 `mutual_info` + `perm_p` + `align`을 공유.
- 추론이 *기계적*이라 단계마다 그릴 게 명확 → 시각화 데모로 적합. 한–일 floor·유형론 함정·체리피킹 함정을 *남이 직접 만지게* 하는 게 교육 가치.

### 1.2 Out of Scope
| 항목 | 이유 |
|---|---|
| 임의 단어 라이브 입력(사용자가 아무 두 단어 타이핑) | `align()`이 panphon(파이썬) 의존 → JS 포팅은 stretch. MVP는 **사전 계산된(baked) 프리셋 trace**만 |
| 새 연구 결과/신규 방법 | 데모는 *기존* 파이프라인 시각화일 뿐. (B_TRACK_SCOUT: 방법 자체는 PARTIAL 신규) |
| 백엔드 서버 / DB / 인증 | 정적 사이트(GitHub Pages). 서버 없음 |
| 거대 kaikki 덤프 번들 | 데모는 프리셋당 ~40쌍 작은 JSON만. 덤프는 build-time 입력(gitignored) |
| 모바일 네이티브 | 반응형 웹으로 충분 |

### 1.3 기존 코드 정리 대상
- 없음(신규 산출물). 단 `mutual_info`/`perm_p`가 `poc17c`·`poc17e`에 **중복 정의**돼 있음 → 데모 export 스크립트는 한쪽을 import해 재사용(중복 유발 금지).

---

## 2. 현재 플로우 / 시스템 도식

**falsifier 파이프라인 (기존, 파이썬):**
```
wordlist A, wordlist B
   │  norm_gloss로 개념정렬          (poc17c:52)
   ▼
[(coarse_phon_a, coarse_phon_b), ...]   hangul_phon/pj_phon/clean (poc17c:30/46, poc17e:22)
   │  align() per pair  = Needleman-Wunsch over panphon segs   (poc5_reconstruct:61)
   ▼
joint/marginal counts → MI = Σ p(x,y)·log(p(x,y)/p(x)p(y))     (poc17c:83)
   │  perm_p: shuffle B ×N, MI_null 분포, p=(#≥obs +1)/(N+1)    (poc17c:99)
   ▼
verdict: MI, p, N(vs 지평~15–20), DETECTED/FLOOR/TRAP
```

**데모 아키텍처 (신규):**
```
[build-time] poc/export_demo_data.py
   ─ 기존 파이프라인을 프리셋에 실행 → 전 단계 trace를 JSON으로 bake
        │  (panphon·kaikki 등 무거운 의존은 여기서만)
        ▼
   web/data/presets/*.json   (작음, committable, §3 계약 준수)
        │
[runtime] web/index.html + web/app.js (vanilla JS + SVG)
   ─ baked trace를 로드해 6단계 애니메이션 + 프리셋 토글 대조
   ─ 서버 없음. panphon 포팅 없음. 정적 배포(GitHub Pages)
```

---

## 3. Data Contract & Inventory

이 데모엔 HTTP API가 없다. 대신 **BE(파이썬 export)↔FE(JS 데모)의 인터페이스 = 프리셋 trace JSON 스키마**다. 이 스키마를 §3.2에서 **동결**하면 FE는 mock trace로 먼저 개발(MSW 대응 = 손으로 만든 mock JSON 1개)하고, BE export 완료를 기다리지 않는다 = 진짜 병렬.

### 3.1 산출물 목록

| 산출물 | 경로 | 설명 | 상태 | 계약 |
|---|---|---|---|---|
| 프리셋 trace | `web/data/presets/{id}.json` | 한 프리셋의 전 단계 baked trace | 신규 | §3.2-a (동결) |
| 프리셋 인덱스 | `web/data/presets/index.json` | 프리셋 목록·메타 | 신규 | §3.2-b (동결) |
| mock trace | `web/data/presets/_mock.json` | FE 선개발용 손작성 1개 | 신규 | §3.2-a 준수 |

### 3.2 계약 (동결)

#### 3.2-a 프리셋 trace 스키마 `{id}.json`
```
{
  "id": "kor-jpn-native",
  "label": "한국어 ↔ 일본어 (고유어)",
  "kind": "claim" | "confirmed" | "control" | "cherry",   // 프리셋 성격(UI 색/아이콘)
  "langA": "Korean", "langB": "proto-Japonic",
  "nperm": 2000,
  "horizon": 18,                       // 탐지 지평(쌍 개수); POC-6/11
  "pairs": [                           // 개념정렬된 쌍 (coarse phon + 원형)
    { "concept": "water", "a_raw": "물", "b_raw": "*mi", "a": "mul", "b": "mi" }
  ],
  "alignments": [                      // pairs[i]에 1:1 대응
    { "i": 0, "cells": [ ["m","m"], ["u",null], ["l",null] ] }   // null = gap
  ],
  "matrix": {                          // 대응표 P(x,y) 시각화용
    "rows": ["m","u","l", ...],        // A측 분절(빈도순)
    "cols": ["m","i", ...],            // B측 분절
    "counts": [[3,0,...],[...]]        // rows×cols joint count
  },
  "mi": 0.519,                         // 관측 MI
  "null": { "values": [0.41,0.50,...], "bins": 40 },  // 순열 MI 표본(히스토그램용; 길이=nperm 또는 다운샘플 ≤500)
  "p": 0.051,
  "verdict": "FLOOR",                  // "DETECTED"(p<.05 & N≥horizon) | "FLOOR" | "BELOW_HORIZON"(N<horizon) | "TRAP"(cherry/control 주석)
  "note": "무관 Uralic 대조군과 동급(0.053) → 유형론 gradient지 계보 아님"  // 교육 설명(프리셋별)
}
```
- **에러/엣지:** `pairs` 빈 배열 → FE는 "데이터 없음" 카드. `null.values` 다운샘플 시 `nperm`은 원본 유지(표시는 표본).
- **예시 payload:** 위 `kor-jpn-native` 골격 그대로. confirmed 예: `mi:1.68, p:0.0005, verdict:"DETECTED"`(Germanic en↔de, poc17e). cherry 예: 같은 무관쌍에서 lookalike만 추린 trace + `kind:"cherry"`.
- **MSW 대응:** FE는 `_mock.json`(이 스키마 준수, 손작성 ~6쌍)으로 전 화면을 먼저 구현. BE export가 실 데이터를 채우면 교체.

#### 3.2-b 프리셋 인덱스 `index.json`
```
{ "presets": [ { "id":"confirmed-gmc", "label":"...", "kind":"confirmed", "file":"confirmed-gmc.json" }, ... ] }
```

### 3.3 MVP 프리셋 4종 (kind)
| id | 내용 | kind | 소스 파이프라인 |
|---|---|---|---|
| `confirmed-gmc` | 게르만 자매(en↔de 등) 확정 동계어 | confirmed | `poc17e_ladder.py` (cognate_sets) |
| `kor-jpn-native` | 한–일 고유어(한자어 제거) | claim | `poc17c_korjap.py` (typed Japonic) |
| `unrelated-uralic` | 무관·유형론매칭(한국어↔proto-Uralic) | control | `poc17c_korjap.py` (Uralic 대조군) |
| `cherry-lookalike` | 무관쌍에서 lookalike만 체리픽 | cherry | poc11 함정 재현(무관 데이터 + 사후선별) |

---

## 4. 구현 설계

### 4.1 페이지 구조 (단일 페이지)
- **상단**: 프리셋 선택 바(4 버튼, kind별 색/아이콘) + "단계 진행" 컨트롤(◀ ▶ / ▶재생).
- **중앙 6 스테이지**(스크롤 또는 스텝):
  1. **개념정렬 쌍** — 두 열 단어 리스트(`pairs[].a_raw/b_raw` + concept)
  2. **분절 정렬** — 선택 쌍의 `alignments[].cells`를 칸으로(gap=빈칸)
  3. **대응표 히트맵** — `matrix` SVG 히트맵, 쌍 처리하며 셀이 채워지는 애니메이션
  4. **MI** — `mi` 스칼라 + 공식, "대응표를 한 숫자로 collapse"
  5. **순열 null** — `null.values` 히스토그램이 자라고, `mi`가 빨간 세로선, p값 카운트업
  6. **판정 카드** — MI / p / N vs horizon / `verdict` 배지 + `note`
- **하단 대조 패널(킬러 기능)**: 4 프리셋의 판정 카드를 *나란히* → 한–일(FLOOR)과 Uralic(control)이 *구별 안 됨*을 직접 보게. cherry는 "p 떨어졌다 → proper null 켜면 사라짐" 토글.

### 4.2 기술 스택
- **vanilla JS + SVG**(무의존). 차트는 손작성 SVG 헬퍼(기존 `poc22_report.py`의 SVG 패턴 재사용 가능).
- 빌드 없음. `web/index.html` + `web/app.js` + `web/style.css` + `web/data/`.
- 배포: GitHub Pages(정적). 

### 4.3 export 스크립트 설계 (`poc/export_demo_data.py`)
- `poc17c`·`poc17e`에서 `mutual_info`·`perm_p`·`align`·`load_proto`·`hangul_phon` 등을 **import**(재구현 금지).
- 각 프리셋: 쌍 구성 → align trace 수집 → joint matrix → MI → perm_p(단, **null 표본을 반환하도록 perm_p를 감싸거나 인라인** — 현 `perm_p`는 p만 반환하므로 null 분포 수집용 thin wrapper 필요) → JSON dump.
- 쌍 수 cap(프리셋당 ~40, 가독성). null.values는 ≤500 다운샘플.

---

## 5. 구현 단계 (Tracks)

```
                 ┌─── Track A: export 스크립트 (파이썬, BE)
시작 ─ §3 계약동결 ┤
                 ├─── Track B: JS 데모 UI (FE, mock으로 선개발)
                 │
                 └─── Track C: 프리셋 데이터 큐레이션 (A에 입력)
   (A 완료) ───── Track D: 통합·배포(GitHub Pages)
```

**트랙 간 의존성:**
- **§3 계약 동결이 선행** — 동결되면 A(real JSON 생성)와 B(mock JSON으로 UI)는 *진짜 병렬*.
- C(프리셋 선정·gloss 큐레이션)는 A의 입력 → A 시작 전 또는 A-1과 병렬.
- D(통합)는 A·B 완료 후. B의 mock→real 교체는 A 완료 시.
- Track 경계: A=`poc/`(파이썬), B=`web/`(JS) → **다른 파일·다른 언어 = 충돌 없음.**

**인원별 배분:**
| 인원 | 추천 배분 |
|---|---|
| 1명 | §3 동결 → B(mock UI 먼저, 화면 확정) → A(real export) → 교체 → D. *UI를 먼저 해야 trace 스키마 niggle이 드러남* |
| 2명 | 동결 후 [A+C: 파이썬] ∥ [B: JS]. 합류 시 D |
| 3명 | A / B / C 각 1명, 동결 회의 후 분기, D는 B 담당 |
| 4명+ | 과분할. 3명 + 1명 프리셋 확장(추가 어족·라이브 모드 R&D) |

### Track A: export 스크립트 (파이썬)
**의존:** §3 계약 동결 후. C(프리셋 정의)와 병렬 가능
**내부 순서:** A-1 → A-2 → A-3
**작업량:** 중간. 가장 복잡: null 분포 수집(현 `perm_p`는 p만 반환 → wrapper)

| ID | 파일 | 내용 |
|---|---|---|
| A-1 | `poc/export_demo_data.py` | `poc17c`/`poc17e`에서 코어 import, 프리셋별 쌍 구성 |
| A-2 | `poc/export_demo_data.py` | align trace + joint matrix + MI 수집, `perm_p` 감싸 **null.values 반환** |
| A-3 | `web/data/presets/*.json` | §3.2 스키마로 dump + `index.json` |

### Track B: JS 데모 UI (FE)
**의존:** §3 계약 동결 후(= `_mock.json`). A 완료 불요
**내부 순서:** B-1 → (B-2 ∥ B-3 ∥ B-4) → B-5
**작업량:** 큼. 가장 복잡: 순열 null 히스토그램 애니메이션(B-4)

| ID | 파일 | 내용 |
|---|---|---|
| B-1 | `web/index.html`, `web/style.css`, `web/app.js` | 골격 + `_mock.json` 로더 + 프리셋 바 + 스텝 컨트롤 |
| B-2 | `web/app.js` | 스테이지 1–2(개념정렬·분절정렬 칸) |
| B-3 | `web/app.js` | 스테이지 3–4(대응표 히트맵 SVG·MI) |
| B-4 | `web/app.js` | 스테이지 5(순열 null 히스토그램 애니메이션 + p 카운트업) |
| B-5 | `web/app.js` | 스테이지 6 판정 카드 + 하단 4-프리셋 대조 패널(킬러) + cherry 토글 |

### Track C: 프리셋 데이터 큐레이션
**의존:** 없음(A의 입력). 동결과 병렬
**작업량:** 작음~중간. gloss 다의성 정제가 까다로움

| ID | 파일 | 내용 |
|---|---|---|
| C-1 | (스크립트 인자/상수) | 4 프리셋의 소스·언어·개념셋·cap 확정 |
| C-2 | (검수) | cherry-lookalike 선정 기준(무관쌍 중 표면유사 상위) 명시 — 함정 *재현*이 목적 |

### Track D: 통합·배포
**의존:** A·B 완료
**작업량:** 작음

| ID | 파일 | 내용 |
|---|---|---|
| D-1 | `web/` | mock→real JSON 교체, 전 프리셋 점검 |
| D-2 | `.github/workflows/` 또는 Pages 설정 | 정적 배포 |

### (Stretch) Track E: 라이브 임의입력 모드
**의존:** MVP(D) 후. **Out of Scope(1.2)지만 R&D 가치**
- panphon 자질표를 JS로 포팅하거나, **coarse 알파벳 한정 간이 NW**(char-level, 자질 hand-table)로 align 근사 → 라이브 MI/perm. ⚠️ 실 파이프라인과 *발산* 가능 → "근사 모드" 라벨 필수.

---

## 6. 확인 완료 사항 (코드 검증)

- **`align()` = Needleman-Wunsch + panphon 의존** — `poc/poc5_reconstruct.py:61-92`. `ft.ipa_segs`로 분절, `ft.word_to_vector_list`로 자질벡터, sub cost = 자질 Hamming/len, GAP=0.8. → **JS 직접 포팅 불가(panphon)** 이므로 baked-trace 방식 채택의 근거.
- **`mutual_info(pairs)`** — `poc/poc17c_korjap.py:83-96` (동일본 `poc17e_ladder.py:33-47`). joint/marginal count → Σ p(x,y)log(p(x,y)/p(x)p(y)). 결정론적.
- **`perm_p(pairs, nperm)`** — `poc/poc17c_korjap.py:99-107`. obs MI, B 셔플 ×N, p=(ge+1)/(N+1). **현재 p만 반환** → null 분포 시각화엔 wrapper 필요(A-2).
- **coarse 매핑** — `hangul_phon` `poc17c:30-43`, `pj_phon` `poc17c:46-49`, `clean`(romanize) `poc17e:22-29`. 데모 `a`/`b` 필드 = 이 함수 출력.
- **개념정렬** — `norm_gloss` `poc17c:52-57`; Korean concept→words `poc17c:135-147`; proto `load_proto` `poc17c:110-122`.
- **프리셋 소스 데이터** — `data/kaikki/korean.jsonl`, `protojaponic.jsonl`, `protouralic.jsonl`, `prototurkic.jsonl`(poc17c SOURCES `poc17c:151-156`); 확정 동계어 = `kaikki.cognate_sets`(poc17e:18). **모두 gitignored 대용량** → export는 build-time, 산출 JSON만 commit.
- **지평·기준** — 탐지 지평 ~15–20쌍(POC-6/11, SUMMARY §4); 확정 IE ~5.5ky MI 1.0–1.3(poc17e 결과표); 한–일 floor MI 0.52·p≈0.05(poc17b).

### 6.x 미확인 항목
| # | 항목 | 확인 방법 |
|---|---|---|
| 6.1 | `kaikki.cognate_sets` 시그니처/반환형 | `poc/kaikki.py` 해당 함수 Read |
| 6.2 | 게르만 프리셋의 실제 쌍 수(cap 40서 N≥horizon 유지되나) | export 시제 실행 |
| 6.3 | null.values 500 다운샘플이 히스토그램 형태 보존하나 | A-2서 시각 점검 |
| 6.4 | 베이크된 wordlist 재배포 라이선스(Wiktionary CC BY-SA) | 프리셋에 출처·라이선스 표기 필요 여부 확인 |
| 6.5 | GitHub Pages 경로(`web/` 서브디렉토리 vs `/docs`) | repo Pages 설정 |

---

## 7. Risk

| Risk | Impact | Mitigation |
|---|---|---|
| panphon JS 포팅 난이도 | 라이브 모드 불가 | **MVP는 baked-trace로 회피**(§1.2). 라이브는 Stretch(E)서 간이 NW 근사 |
| baked 데이터가 "라이브"처럼 오해됨 | 교육적 오도 | UI에 "사전 계산된 실제 파이프라인 출력" 명시. Stretch 라이브는 "근사 모드" 라벨 |
| 순열 null 애니메이션 성능(2000 표본) | 버벅임 | null.values를 ≤500 다운샘플(§3.2), requestAnimationFrame 배치 |
| cherry-lookalike가 "진짜 신호"로 오해됨 | 함정 교훈 역효과 | cherry 토글에 "proper null 켜면 사라짐" 명시 + kind 색경고 |
| Wiktionary 파생 wordlist 재배포 라이선스 | 배포 차단 | 프리셋 JSON에 출처·CC BY-SA 표기(6.4) |
| `mutual_info`/`perm_p` 중복정의 분기 | 결과 불일치 | export는 한 모듈(poc17c)만 import, 다른 곳 수정 금지 |

---

## 8. 한눈에 — 무엇을 만드나

> **백엔드 없는 단일 정적 페이지.** 파이썬이 *진짜* falsifier를 4 프리셋에 돌려 전 단계 trace를 JSON으로 굽고(Track A),
> JS가 그걸 6단계로 애니메이션(Track B). 킬러 = 한–일(FLOOR)·무관 Uralic(control)·체리픽을 *나란히* 띄워
> "구별 안 됨"을 눈으로 때리는 대조 패널. 계약(§3.2 trace 스키마)을 동결하면 A·B는 진짜 병렬.
