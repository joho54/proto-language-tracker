"""POC-5b: 제대로 된 재구기 (핵심 게이트).

조잡한 POC-5(baseline 미달) 개선:
  ① 문맥의존 X(우선 채널은 per-language 유지) + ② 조어 bigram 음소배열 prior + Viterbi 디코딩.
  greedy 칼럼 argmax → Viterbi(emission=자손 채널 likelihood, transition=조어 bigram LM)로
  음소배열적으로 그럴듯한 조어열 선호.

난이도 분리 진단: 얕은(Proto-Germanic ← 게르만 자손) vs 깊은(PIE).
  얕은 데서 baseline 이기면 method OK·PIE는 depth 문제. 얕은 데서도 지면 method 문제.

출력: poc/results/poc5b_<fam>.tsv  (unbuffered)
"""
import sys, re, random, math
from collections import Counter, defaultdict
from pathlib import Path
from poc5_reconstruct import align, fdist, ft
from normalize import normalize_ipa
import kaikki

random.seed(5)
LATIN = re.compile(r"[a-zɑ-ʯæœøðθβɣχʃʒŋɲʔ]")
A = 0.05   # 평활


def clean(w):
    w = (w or "").strip().lstrip("*").replace("H", "h")
    w = w.split(",")[0].split(";")[0].strip()
    if not w or " " in w:
        return None
    L = [c for c in w.lower() if c.isalpha()]
    if not L or sum(bool(LATIN.match(c)) for c in L) / len(L) < 0.7:
        return None
    ipa = normalize_ipa(w)[0]
    return ipa if 2 <= len(ft.ipa_segs(ipa)) <= 12 else None


def get_sets(fam, max_daughters=8):
    sets = []
    for e in kaikki.load(fam):
        proto = clean(e.get("word"))
        if not proto:
            continue
        ds = {}
        for nd in e.get("descendants") or []:
            tmp = []
            kaikki._walk(e.get("word"), [nd], tmp, None)
            for _, w, code in tmp:
                d = clean(w)
                if d and code and code not in ds:
                    ds[code] = d
        if len(ds) >= 3:
            sets.append((proto, dict(list(ds.items())[:max_daughters])))
    return sets


def learn(train):
    fwd = defaultdict(lambda: defaultdict(Counter))   # lang -> proto_seg -> Counter(daughter_seg/<DEL>)
    lm = defaultdict(Counter)                          # proto bigram: prev -> Counter(cur)
    uni = Counter()
    vocab = set()
    for proto, ds in train:
        ps = ft.ipa_segs(proto)
        vocab |= set(ps)
        prev = "<S>"
        for s in ps:
            lm[prev][s] += 1
            uni[s] += 1
            prev = s
        lm[prev]["<E>"] += 1
        for lang, form in ds.items():
            for l, d in align(proto, form):
                if l is None:
                    continue
                fwd[lang][l][d if d is not None else "<DEL>"] += 1
    return fwd, lm, uni, vocab


def emit_logp(col_obs, l, fwd, V):
    s = 0.0
    for lang, o in col_obs.items():
        c = fwd[lang].get(l)
        tot = sum(c.values()) if c else 0
        s += math.log((c[o] if c else 0) + A) - math.log(tot + A * (V + 1))
    return s


def trans_logp(prev, cur, lm, uni, V):
    c = lm[prev]
    tot = sum(c.values())
    # bigram + 유니그램 백오프
    p_bi = (c[cur] + A) / (tot + A * V) if tot else None
    p_uni = (uni[cur] + A) / (sum(uni.values()) + A * V)
    p = 0.7 * (p_bi if p_bi else p_uni) + 0.3 * p_uni
    return math.log(p)


def reconstruct(daughters, fwd, lm, uni, vocab, anchor):
    if anchor not in daughters:
        anchor = next(iter(daughters))
    Aform = daughters[anchor]
    segsA = ft.ipa_segs(Aform)
    obs = [{anchor: s} for s in segsA]
    for lang, form in daughters.items():
        if lang == anchor:
            continue
        ai = 0
        for a, d in align(Aform, form):
            if a is None:
                continue
            if ai < len(segsA):
                obs[ai][lang] = d if d is not None else "<DEL>"
            ai += 1
    cands = list(vocab)
    V = len(vocab)
    # Viterbi
    dp = [{}, {}]
    bp = []
    prev = "<S>"
    col0 = {}
    back0 = {}
    for l in cands:
        col0[l] = trans_logp("<S>", l, lm, uni, V) + emit_logp(obs[0], l, fwd, V)
        back0[l] = "<S>"
    dp = col0
    bp.append(back0)
    for c in range(1, len(obs)):
        cur = {}
        back = {}
        for l in cands:
            e = emit_logp(obs[c], l, fwd, V)
            best, bl = -1e18, None
            for pl in cands:
                sc = dp[pl] + trans_logp(pl, l, lm, uni, V) + e
                if sc > best:
                    best, bl = sc, pl
            cur[l] = best
            back[l] = bl
        dp = cur
        bp.append(back)
    # 종료 + 역추적
    last = max(cands, key=lambda l: dp[l] + trans_logp(l, "<E>", lm, uni, V))
    seq = [last]
    for c in range(len(obs) - 1, 0, -1):
        last = bp[c][last]
        seq.append(last)
    seq.reverse()
    # 엔트로피(마지막 칼럼 사후 근사)
    return tuple(seq), 0.0


def main():
    fam = sys.argv[1] if len(sys.argv) > 1 else "Proto-Germanic"
    out = Path(__file__).parent / "results"
    print("=" * 64, flush=True)
    print(f"POC-5b: 개선 재구기 (Viterbi+조어LM) — {fam}", flush=True)
    print("=" * 64, flush=True)
    sets = get_sets(fam)
    random.shuffle(sets)
    sp = int(len(sets) * 0.7)
    train, test = sets[:sp], sets[sp:]
    if len(test) > 400:
        test = test[:400]
    print(f"셋: {len(sets)} (train {len(train)} / test {len(test)})", flush=True)

    fwd, lm, uni, vocab = learn(train)
    cov = Counter(c for _, ds in train for c in ds)
    sc = {}
    for code in cov:
        pr = [(p, d[code]) for p, d in train if code in d][:300]
        if len(pr) >= 20:
            sc[code] = sum(fdist(ft.ipa_segs(p), ft.ipa_segs(x)) for p, x in pr) / len(pr)
    anchor = min(sc, key=sc.get)
    print(f"anchor(최보수)={anchor} (평균거리 {sc[anchor]:.2f}), 조어vocab={len(vocab)}", flush=True)

    base = [fdist(ft.ipa_segs(ds[anchor]), ft.ipa_segs(p)) for p, ds in test if anchor in ds]
    base_mean = sum(base) / len(base)
    # 개선 재구
    rt = ex = nt = 0.0
    for proto, ds in test:
        rec, _ = reconstruct(ds, fwd, lm, uni, vocab, anchor)
        rt += fdist(rec, ft.ipa_segs(proto))
        ex += (rec == tuple(ft.ipa_segs(proto)))
        nt += 1
    rec_mean = rt / nt
    print("-" * 64, flush=True)
    print(f"baseline (anchor 그대로):   거리 {base_mean:.3f}", flush=True)
    print(f"개선 재구 (Viterbi+조어LM): 거리 {rec_mean:.3f}  완전복원 {ex/nt:.2f}", flush=True)
    verdict = "재구 우월 ✓ (method OK)" if rec_mean < base_mean else "baseline 미달 (method 부족)"
    print(f"판정: {verdict}  (Δ={base_mean-rec_mean:+.3f})", flush=True)
    (out / f"poc5b_{fam}.tsv").write_text(
        f"fam\tbaseline\trecon\texact\n{fam}\t{base_mean:.4f}\t{rec_mean:.4f}\t{ex/nt:.4f}",
        encoding="utf-8")


if __name__ == "__main__":
    main()
