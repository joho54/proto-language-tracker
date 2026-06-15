# proto-language-tracker — 작업 지침

PIE 등 잘 연구된 어족에서 음변화 prior를 학습해, 조어 연구가 부진한 언어(한국어 등)의
조어를 재구하고, 독립 재구된 가상 조어들의 **형태론적 동형성이 우연을 유의하게 초과하는지**
검정하는 교차언어 프로젝트.

- **종합 요약(먼저 읽기): `docs/SUMMARY.md`** — 13개 POC·3-tier·신규 방법론·입증경계·다음단계
- 설계/명세: `docs/SPEC.md` (모델=단일 베이지안 생성모델, 검증=모델비교+순열)
- 데이터 계약·파이프라인·POC 결과: `docs/PIPELINE.md`
- POC 코드: `poc/`, 가상환경: `.venv/` (`.venv/bin/python`)
- **데이터 소스: kaikki.org(wiktextract) 덤프** (`poc/kaikki.py` → `data/kaikki/`). 오프라인·rate-limit 없음·
  구조화 descendants 트리. Wikimedia API 직접 스크래핑(`poc/wikt.py`)은 429 throttle 심해 **폴백**으로만.

---

## 엔지니어링 원칙

### 1순위 — 캐시·로그 영속성 (NON-NEGOTIABLE)

시간이 오래 걸리는 작업은 **프로세스가 중간에 죽어도 캐시·로그가 남아 진행 상황 확인과
재개가 가능해야 한다.** 방금 POC-5에서 stdout 버퍼링 때문에 kill 시 출력 전량 유실 → 이 규칙의 근거.

**필수 규칙:**
- **모든 외부 fetch는 디스크 캐시.** 페이지/응답을 받는 즉시 파일로 저장(예: `poc/results/wikt_cache2/`).
  재실행은 캐시를 건너뛰어 **idempotent·resumable** 해야 한다. (참고: `poc/wikt.py`의 `fetch_many`)
- **로그는 파일에 증분 기록 + 즉시 flush.** stdout 버퍼링에 의존 금지.
  - 파이썬: `python -u` 또는 `print(..., flush=True)`, 또는 `logging`을 파일 핸들러로.
  - 긴 루프는 **중간 결과를 주기적으로 디스크에 append**(끝에 한 번에 쓰지 말 것).
- **부분 산출물 보존.** 결과 TSV/JSON을 단계별로 흘려 써서, 도중 죽어도 거기까지는 남게.
- **로그는 raw 그대로 stdout 파이프라이닝. `grep` 등 필터 절대 금지.** 필터는 실패 모드·정보를
  숨긴다. 전체 로그를 그대로 흘리고, 확인은 파일 전체를 읽어서(`cat`/Read) 한다. Monitor의
  grep-필터 스트리밍 패턴도 로그 내용에는 쓰지 않는다(완료 감지용 조건도 가급적 비-grep).
- **장시간 작업은 background로 돌리되**, 위 캐시·로그가 있어야 죽었을 때 복구 가능.
- 외부 API는 **throttle + 429 백오프**(요청 합치기 batching 우선 — `wikt.py`가 50p/요청).

체크: "지금 이 프로세스가 즉시 죽으면, 캐시·로그만으로 어디까지 됐는지 알고 이어서 돌릴 수 있는가?"
답이 No면 그 작업은 규칙 위반.

### 그 외
- 데이터는 출처(source)·신뢰도(tier)·시간심도를 항상 기록. **tier 혼합 금지**(gold만 supervision).
- 표현은 **이산 단위 + 연속 점수** (변화유형·규칙은 이산, 거리·확률은 연속). 이산성은 셈·검정·설명·전이의 토대.
- POC는 가정을 하나씩 깨는 de-risk. 실패해도 원인 진단 후 `docs/PIPELINE.md`에 기록.
