"""POC-21 step-2 데이터: 삼국사기 권37(지리4) 전체 지명 스크랩 = denominator.

db.history.go.kr 한국 고대 사료 DB. 권37 = 7섹션/34 item, 각 item에 고구려 지명 다수
(old 고구려명 ↔ new 신라 경덕왕명 쌍 + 학자 형태소 글로스). 이게 POC-21의 분자(안 닮은
지명 포함 *전체*) — step-1이 못 채운 것.

CLAUDE.md 1순위 준수:
- 모든 fetch는 디스크 캐시(data/pjaponic/sg37_cache/). 재실행은 캐시 건너뜀 = idempotent·resumable.
- throttle(요청 간 sleep) + 증분 로그 flush. 부분 산출 보존.
- 죽어도 캐시·로그로 어디까지 됐는지 확인·재개 가능.

이 스크립트 = *수집만*(원본 HTML 캐시). 파싱/추출은 poc21b에서(원본 보존이 먼저).
"""
import urllib.request, time, sys
from pathlib import Path

ROOT = Path(__file__).parent
CACHE = ROOT.parent / "data" / "pjaponic" / "sg37_cache"
CACHE.mkdir(parents=True, exist_ok=True)
LOG = ROOT / "results" / "poc21_scrape.log"
UA = {"User-Agent": "proto-lang-tracker-poc/0.2 (research; joho0504)"}
AJAX = "https://db.history.go.kr/ancient/getChildItemLevelListAjax.do?parentId={pid}&level=2&types=r"
PAGE = "https://db.history.go.kr/id/{iid}"
SECTIONS = [f"sg_037r_{s:04d}" for s in range(10, 80, 10)]  # 0010..0070

logf = open(LOG, "a")
def log(*a):
    print(*a, flush=True); print(*a, file=logf, flush=True)

def fetch(url, throttle=0.8):
    for attempt in range(6):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30)
            time.sleep(throttle)
            return r.read().decode("utf-8", "replace")
        except Exception as e:
            wait = min(30, 5 * (attempt + 1))
            log(f"  [retry {attempt+1}] {e} → {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"fail: {url}")

def cached_fetch(url, fname, throttle=0.8):
    """캐시 우선. 없으면 fetch 후 저장."""
    f = CACHE / fname
    if f.exists() and f.stat().st_size > 500:
        return f.read_text(encoding="utf-8")
    txt = fetch(url, throttle)
    f.write_text(txt, encoding="utf-8")
    log(f"  [saved] {fname} ({len(txt)}B)")
    return txt

def main():
    import re
    log("=" * 60)
    log("POC-21 scrape: 삼국사기 권37 전체 지명 → denominator")
    # 1) 섹션별 item id 수집 (ajax, 캐시)
    all_items = []
    for sec in SECTIONS:
        html = cached_fetch(AJAX.format(pid=sec), f"ajax_{sec}.html")
        items = sorted(set(re.findall(rf"{sec}_\d{{4}}", html)))
        log(f"섹션 {sec}: {len(items)} items")
        all_items += items
    log(f"\n총 item {len(all_items)}개 수집 시작…")
    # 2) 각 item 페이지 fetch (캐시·throttle·증분)
    done = 0
    for iid in all_items:
        f = CACHE / f"{iid}.html"
        if f.exists() and f.stat().st_size > 500:
            done += 1
            continue
        cached_fetch(PAGE.format(iid=iid), f"{iid}.html")
        done += 1
        if done % 5 == 0:
            log(f"  진행 {done}/{len(all_items)}")
    log(f"\n[완료] {len(all_items)} item 캐시 (data/pjaponic/sg37_cache/)")
    log("→ 다음: poc21b 파싱(old↔new 지명쌍 + 형태소 글로스 추출)")
    logf.close()

if __name__ == "__main__":
    main()
