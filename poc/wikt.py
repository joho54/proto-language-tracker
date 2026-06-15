"""배치 Wiktionary 페처 — 50페이지/요청으로 극적 속도 개선.

action=parse(1페이지=1요청) → action=query&titles=...(50페이지=1요청).
요청 수 ~40배 감소 → 속도↑ + 429 회피. 디스크 캐시.
"""
import urllib.request, urllib.parse, json, re, time
from pathlib import Path

UA = {"User-Agent": "proto-lang-tracker-poc/0.2 (research; joho0504)"}
API = "https://en.wiktionary.org/w/api.php?"
CACHE = Path(__file__).parent / "results" / "wikt_cache2"
CACHE.mkdir(parents=True, exist_ok=True)


def _get(params):
    # 인내심 있는 백오프: 429면 Retry-After(또는 점증 대기) 만큼 쉬고 재시도, 끈질기게.
    for attempt in range(12):
        try:
            r = urllib.request.urlopen(
                urllib.request.Request(API + urllib.parse.urlencode(params), headers=UA),
                timeout=30)
            time.sleep(0.6)
            return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                ra = e.headers.get("Retry-After")
                wait = int(ra) if (ra and ra.isdigit()) else min(60, 10 * (attempt + 1))
                print(f"  [429] {wait}s 대기 (시도 {attempt+1})", flush=True)
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("429 반복 — 한도 미해제")


def _cf(title):
    return CACHE / (re.sub(r"[^A-Za-z0-9]", "_", title)[:180] + ".txt")


def cat_members(cat, n):
    """카테고리 멤버 (최대 500/요청)."""
    out, cont = [], None
    while len(out) < n:
        q = {"action": "query", "list": "categorymembers", "cmtitle": "Category:" + cat,
             "cmlimit": min(500, n - len(out)), "format": "json"}
        if cont:
            q["cmcontinue"] = cont
        d = _get(q)
        out += [m["title"] for m in d["query"]["categorymembers"]
                if m["title"].startswith("Reconstruction:")]
        cont = d.get("continue", {}).get("cmcontinue")
        if not cont:
            break
    return out[:n]


def fetch_many(titles):
    """title→wikitext. 캐시 우선, 미스는 50개씩 배치."""
    result, misses = {}, []
    for t in titles:
        f = _cf(t)
        if f.exists():
            result[t] = f.read_text(encoding="utf-8")
        else:
            misses.append(t)
    for i in range(0, len(misses), 50):
        batch = misses[i:i + 50]
        d = _get({"action": "query", "prop": "revisions", "rvprop": "content",
                  "rvslots": "main", "titles": "|".join(batch), "format": "json",
                  "formatversion": "2"})
        # formatversion=2: pages는 리스트, content는 rev['slots']['main']['content']
        got = {}
        for p in d.get("query", {}).get("pages", []):
            title = p["title"]
            revs = p.get("revisions")
            content = revs[0]["slots"]["main"].get("content", "") if revs else ""
            got[title] = content
        # 정규화 매핑 (요청 title → 실제 title)
        norm = {n["from"]: n["to"] for n in d.get("query", {}).get("normalized", [])}
        for t in batch:
            actual = norm.get(t, t)
            content = got.get(actual, "")
            _cf(t).write_text(content, encoding="utf-8")
            result[t] = content
    return result
