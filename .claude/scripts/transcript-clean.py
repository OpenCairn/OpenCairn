#!/usr/bin/env python3
"""Clean a formatted transcript body outside the calling session, chunk by chunk.

Usage:
  transcript-clean.py --in BODY.md --out CLEAN.md [--context NOTES.txt] [--model opus]
                      [--chunk-words 3000] [--jobs 4] [--check-only RAW.md]

BODY.md holds paragraphs separated by blank lines, each starting with a timestamp
("[MM:SS]" or "[H:MM:SS]"), optionally followed by a bold speaker label
("**Speaker 1:**"), as /transcribe Phase 3 step 2 formats them.

Each chunk goes to a hermetic `claude -p` (no tools, no MCP servers, no user/project
settings or hooks, no session persistence, neutral cwd) with /transcribe's cleanup
rules. --context adds human-written page text (show notes, divergence list) that
outranks the machine transcript on names.

Every chunk must pass three checks, else nothing is written and the exit is 2:
  retention  output keeps at least 90% of the chunk's words (the rules keep fillers)
  tail       at least half of the chunk's last six long words appear near the output end
  structure  the sequence of timestamp + speaker-label prefixes is identical

--check-only RAW.md runs the checks on an existing cleaned file (--in) against RAW.md
without calling a model. Output: CLEAN.md is written only when every check passes;
a JSON report goes to stdout; progress goes to stderr. Exit 0 pass, 1 usage or model
failure, 2 a check failed, 3 the `claude` CLI is not on PATH. Callers fall back to
their in-session cleanup on 1 or 3; 2 means the model's output was unsafe to keep.
"""
import argparse, concurrent.futures, json, os, re, shutil, subprocess, sys, tempfile


class Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse exits 2, which callers read as a failed check
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")

RULES = """You clean a machine transcript chunk. Fix transcription errors only:
- Fix non-words to their most likely intended word (e.g. "seduptresses" -> "seductresses").
- Fix obvious grammar/punctuation errors introduced by the transcription model (not the speaker's actual grammar: ESL patterns, filler words, etc. stay).
- Mark genuinely unclear sections as [inaudible] rather than guessing.
- Preserve the speaker's actual words and meaning; do not rewrite, paraphrase, summarise or "improve".
- Preserve every paragraph, its timestamp and its speaker label exactly, in the same order.
- Do not fix the speaker's actual speech patterns (um, uh, repeated words, broken sentences). A model hallucination loop (a short token or phrase repeated many times, unlike the surrounding speech) is not speech: use the caption reading for that span if the context gives one, else mark it [inaudible].
- The context below may hold human-written page text (show notes, description, chapter list) and a list of words where two machine transcripts disagree. Page text outranks both machine readings on names and terms. Where two machine readings disagree and neither is clearly right, keep the more plausible one and append [?].
Output only the cleaned chunk, same paragraph layout, no preamble or commentary."""

PREFIX = re.compile(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(\*\*[^*\n]+?:\*\*)?", re.M)


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def paragraphs(text):
    return [p.strip("\n") for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]


def chunk(paras, limit):
    out, cur, n = [], [], 0
    for p in paras:
        cur.append(p)
        n += len(p.split())
        if n >= limit:
            out.append(cur); cur, n = [], 0
    if cur:
        out.append(cur)
    return ["\n\n".join(c) for c in out]


def checks(src, got):
    sw, gw = len(src.split()), len(got.split())
    last = re.findall(r"[a-z']{5,}", src.lower())[-6:]
    tail = got.lower()[-1500:]
    hits = sum(w in tail for w in last)
    sp, gp = PREFIX.findall(src), PREFIX.findall(got)
    first_diff = next((i for i, (a, b) in enumerate(zip(sp, gp)) if a != b), None)
    if first_diff is None and len(sp) != len(gp):
        first_diff = min(len(sp), len(gp))
    return {
        "words_in": sw, "words_out": gw, "retention": round(gw / max(sw, 1), 3),
        "retention_ok": gw >= 0.9 * sw,
        "tail_hits": f"{hits}/{len(last)}", "tail_ok": not last or hits >= len(last) / 2,
        "prefixes_in": len(sp), "prefixes_out": len(gp), "structure_ok": first_diff is None,
        "first_prefix_mismatch": None if first_diff is None else
            {"index": first_diff, "in": sp[first_diff] if first_diff < len(sp) else None,
             "out": gp[first_diff] if first_diff < len(gp) else None},
    }


def claude(prompt, model, cwd):
    cmd = ["claude", "-p", "--model", model, "--tools", "", "--strict-mcp-config",
           "--setting-sources", "", "--no-session-persistence", "--output-format", "json",
           "--system-prompt", "You are a careful transcript editor."]
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=cwd, timeout=900)
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        d = {}
    if r.returncode != 0 or d.get("is_error") or not (d.get("result") or "").strip():
        raise RuntimeError((d.get("result") or r.stderr or "no output").strip()[:400])
    return d["result"].strip(), d.get("usage", {}), list((d.get("modelUsage") or {}).keys())


def main():
    ap = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out")
    ap.add_argument("--context")
    ap.add_argument("--model", default="opus")
    ap.add_argument("--chunk-words", type=int, default=3000)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--check-only", metavar="RAW")
    a = ap.parse_args()

    if a.check_only:
        res = checks(open(a.check_only).read(), open(a.inp).read())
        ok = res["retention_ok"] and res["tail_ok"] and res["structure_ok"]
        print(json.dumps({"ok": ok, "whole_file": res}, indent=2))
        sys.exit(0 if ok else 2)
    if not a.out:
        ap.error("--out is required unless --check-only")
    if os.path.exists(a.out):
        ap.error(f"{a.out} exists; refusing to overwrite")
    if shutil.which("claude") is None:
        log("error: `claude` CLI not on PATH; run the cleanup in-session instead")
        sys.exit(3)

    chunks = chunk(paragraphs(open(a.inp).read()), a.chunk_words)
    context = open(a.context).read()[:6000] if a.context else ""
    cwd_dir = tempfile.TemporaryDirectory(prefix="transcript-clean-")
    cwd = cwd_dir.name
    log(f"{len(chunks)} chunk(s), model {a.model}, cwd {cwd}")

    def one(i):
        pos = f"This is chunk {i + 1} of {len(chunks)}; clean it from its first line through its last."
        prompt = f"{RULES}\n\n" + (f"Context:\n{context}\n\n" if context else "") + \
                 f"{pos}\n\nChunk:\n{chunks[i]}"
        out, usage, models = claude(prompt, a.model, cwd)
        res = checks(chunks[i], out)
        log(f"chunk {i + 1}: {res['words_in']} -> {res['words_out']} words ({res['retention']:.0%}), "
            f"tail {res['tail_hits']}, prefixes {res['prefixes_in']}/{res['prefixes_out']}")
        return out, {"chunk": i + 1, **res, "usage": usage, "models": models}

    try:
        with concurrent.futures.ThreadPoolExecutor(a.jobs) as ex:
            results = list(ex.map(one, range(len(chunks))))
    except Exception as e:  # model or CLI failure: nothing written
        log(f"error: {e}")
        sys.exit(1)
    finally:
        cwd_dir.cleanup()
    report = [r for _, r in results]
    ok = all(r["retention_ok"] and r["tail_ok"] and r["structure_ok"] for r in report)
    if ok:
        with open(a.out, "x") as f:
            f.write("\n\n".join(o for o, _ in results) + "\n")
    print(json.dumps({"ok": ok, "out": a.out if ok else None, "chunks": report}, indent=2))
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
