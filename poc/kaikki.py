"""kaikki.org (wiktextract) 데이터 레이어 — rate-limit 없는 오프라인 백본.

Wiktionary를 이미 파싱한 JSONL. 각 엔트리에 구조화된 descendants 트리 포함.
한 번 받아 data/kaikki/ 에 영구 캐시 (CLAUDE.md 1순위: 영속·재개 가능).
정규식 wikitext 파싱(wikt.py) 대체.

URL 패턴: path=lang(공백→하이픈), file=lang에서 비영숫자 제거.
  Proto-Indo-European → .../Proto-Indo-European/kaikki.org-dictionary-ProtoIndoEuropean.jsonl
"""
import re, json, urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "kaikki"
DATA.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "proto-lang-tracker/0.3 (research; joho0504)"}


def url_for(lang):
    path = lang.replace(" ", "-")
    fname = re.sub(r"[^A-Za-z0-9]", "", lang)
    return f"https://kaikki.org/dictionary/{path}/kaikki.org-dictionary-{fname}.jsonl"


def download(lang, slug=None):
    """언어 JSONL을 캐시. 반환: 로컬 경로 (없으면 받음, 있으면 스킵)."""
    slug = slug or re.sub(r"[^A-Za-z0-9]", "", lang).lower()
    dest = DATA / f"{slug}.jsonl"
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    url = url_for(lang)
    print(f"  [kaikki] 다운로드 {lang} ...", flush=True)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    print(f"  [kaikki] 완료 {dest} ({dest.stat().st_size//1024}KB)", flush=True)
    return dest


def load(lang, slug=None):
    """엔트리(dict) 제너레이터."""
    slug = slug or re.sub(r"[^A-Za-z0-9]", "", lang).lower()
    path = DATA / f"{slug}.jsonl"
    if not path.exists():
        download(lang, slug)
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _walk(parent_word, nodes, edges, target_codes=None):
    """descendants 트리를 재귀 순회 → (parent_word, child_word, child_code) 엣지."""
    for nd in nodes or []:
        w = nd.get("word")
        code = nd.get("lang_code", "")
        if w and parent_word and w != parent_word:
            if target_codes is None or code in target_codes:
                edges.append((parent_word, w, code))
        # 중첩 자손: 현재 노드가 부모
        sub = nd.get("descendants")
        if sub:
            _walk(w or parent_word, sub, edges, target_codes)


def edges_of(entry, target_codes=None):
    """엔트리의 proto word → 모든 자손 엣지 (트리 전체)."""
    root = entry.get("word")
    edges = []
    _walk(root, entry.get("descendants"), edges, target_codes)
    return edges


def cognate_sets(lang, slug=None, target_codes=None, min_daughters=1):
    """proto word → {lang_code: daughter_word} (1차 자손 기준)."""
    sets = []
    for e in load(lang, slug):
        root = e.get("word")
        if not root:
            continue
        daughters = {}
        for nd in e.get("descendants") or []:
            # 1차 자손 트리에서 target 언어 찾기 (중첩 포함)
            tmp = []
            _walk(root, [nd], tmp, target_codes)
            for _, w, code in tmp:
                if code not in daughters:
                    daughters[code] = w
        if len(daughters) >= min_daughters:
            sets.append((root, daughters))
    return sets


if __name__ == "__main__":
    # 작은 proto 파일들로 오프라인 데이터셋 구축 + 엣지 통계
    FAMS = ["Proto-Indo-European", "Proto-Japonic", "Proto-Turkic",
            "Proto-Uralic", "Proto-Austronesian"]
    for fam in FAMS:
        try:
            n_entry = n_edge = 0
            for e in load(fam):
                n_entry += 1
                n_edge += len(edges_of(e))
            print(f"{fam:<24} 엔트리={n_entry:>6} 엣지={n_edge:>7}")
        except Exception as ex:
            print(f"{fam:<24} ERR {type(ex).__name__}: {ex}")
