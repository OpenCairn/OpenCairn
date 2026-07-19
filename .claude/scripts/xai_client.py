#!/usr/bin/env python3
"""Thin client for xAI's Grok Responses API — panel seat + standalone delegation.

Owns key loading, model choice, reasoning effort, live search, the no-tool guard,
retry/backoff, and cost/latency logging. Import from here so no Grok plumbing is
duplicated. Stdlib only (urllib) — no pip installs, matching ~/.claude/scripts/ convention.

Key: XAI_API_KEY in the process environment. Nothing else is read, and the key is
never logged or printed. Endpoint: POST https://api.x.ai/v1/responses

Usage:
  xai_client.py "prompt"                          smoke test (fast model)
  xai_client.py --panel-review BRIEF --source F   run a panel seat over inlined sources
                [--source F ...] [--dry-run]
  xai_client.py --probe                           report availability without an API call

Options:
  --panel-review FILE   brief file; sources are appended as a delimited manifest+appendix
  --source FILE         a file to inline (repeatable). Total capped at MAX_INLINE_BYTES.
  --dry-run             print the outbound payload (key redacted) and exit; no request
  --effort LEVEL        minimal|low|medium|high|xhigh (default xhigh for panel review)
  --probe               exit 0 if XAI_API_KEY is set, 1 otherwise; prints a one-line status

Import:
  from xai_client import deep, analyze, classify
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger("xai")

API_URL = "https://api.x.ai/v1/responses"
GROKMD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "GROK.md")

# --- models (verify against GET /v1/models) -----------------------------------
FAST = "grok-4.20-0309-non-reasoning"   # hot paths: fastest, zero reasoning tokens
WORKHORSE = "grok-4.3"                  # high-volume analysis, 1M ctx
DEEP = "grok-4.5"                       # best reasoning, 500k ctx

DEFAULT_TIMEOUT = 300.0   # xhigh reasoning can think >90s before the first byte
MAX_RETRIES = 3           # 429 / 5xx only; never retry a 4xx that isn't 429

# Cap the inlined appendix well under the >200k-token tier, where xAI doubles the
# per-token rate. ~400 KB is roughly 100k tokens. Over the cap the seat is DROPPED,
# never silently truncated — a truncated appendix produces confident wrong findings.
MAX_INLINE_BYTES = 400_000

# Reasoning models try to CALL server-side search when uncertain; with no tools on
# the request they emit dead tool-call TOKENS as text instead of answering. Injected
# automatically on tool-less calls.
_NO_TOOL_GUARD = (
    "You have no search or browsing tools available on this call. Do not emit tool "
    "calls. Answer from your own knowledge, or state plainly that you cannot verify "
    "something — do not invent facts, names, numbers, or URLs."
)

_grokmd_cache: str | None = None


class XAIError(RuntimeError):
    """Non-2xx from the API, a transport failure, or a malformed response."""


class InlineTooLarge(XAIError):
    """Sources exceed MAX_INLINE_BYTES. The caller must drop the seat and say so."""


def _load_grokmd() -> str:
    global _grokmd_cache
    if _grokmd_cache is None:
        try:
            with open(GROKMD_FILE, encoding="utf-8") as fh:
                _grokmd_cache = fh.read().strip()
        except FileNotFoundError:
            _grokmd_cache = ""
    return _grokmd_cache


def _load_key() -> str:
    key = os.environ.get("XAI_API_KEY")
    if not key:
        sys.exit(
            "XAI_API_KEY unset. Export it in the environment the caller actually runs in "
            "— a key exported only in ~/.bashrc will NOT reach a non-interactive shell."
        )
    return key


def _extract_text(data: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for c in item.get("content", []):
            if c.get("type") == "output_text":
                parts.append(c.get("text", ""))
    return "".join(parts).strip()


def _build_tools(live: bool, *, x_only: bool = False, web_only: bool = False,
                 allowed_x_handles: list[str] | None = None,
                 from_date: str | None = None, to_date: str | None = None):
    if not live:
        return None
    tools: list[dict[str, Any]] = []
    if not web_only:
        x: dict[str, Any] = {"type": "x_search"}
        if allowed_x_handles:
            x["allowed_x_handles"] = allowed_x_handles[:20]
        if from_date:
            x["from_date"] = from_date
        if to_date:
            x["to_date"] = to_date
        tools.append(x)
    if not x_only:
        tools.append({"type": "web_search"})
    return tools


def _post(body: dict[str, Any], timeout: float) -> dict[str, Any]:
    """POST with retry on 429/5xx. urlopen RAISES on non-2xx — there is no status branch."""
    payload = json.dumps(body).encode("utf-8")
    last_err = ""
    for attempt in range(MAX_RETRIES):
        req = urllib.request.Request(
            API_URL, data=payload, method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {_load_key()}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            if e.code == 429 or e.code >= 500:
                # Retry-After may be seconds or absent; fall back to exponential backoff.
                try:
                    delay = float(e.headers.get("Retry-After", ""))
                except (TypeError, ValueError):
                    delay = 2.0 ** attempt
                last_err = f"HTTP {e.code}: {detail}"
                if attempt < MAX_RETRIES - 1:
                    log.warning("xai %s — retrying in %.0fs", last_err, delay)
                    time.sleep(min(delay, 30.0))
                    continue
            # 401/403/404/400 and any exhausted retry land here. Never log the key.
            raise XAIError(f"HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            last_err = f"transport: {e.reason}"
            if attempt < MAX_RETRIES - 1:
                time.sleep(2.0 ** attempt)
                continue
            raise XAIError(last_err) from e
    raise XAIError(last_err or "exhausted retries")


def respond(prompt: str, *, model: str = DEEP, effort: str | None = None,
            live: bool = False, system: str | None = None, grokmd: bool = False,
            tools: list[dict[str, Any]] | None = None,
            max_output_tokens: int | None = None, timeout: float = DEFAULT_TIMEOUT,
            no_tool_guard: bool = True, response_format: dict[str, Any] | None = None,
            store: bool = False, dry_run: bool = False,
            return_meta: bool = False, **unknown):
    """Call Grok once. Returns answer text, or (text, meta) if return_meta.

    store defaults FALSE — it controls whether the response object is persisted for
    previous_response_id threading. Consequence: threading is unavailable, so multi-round
    review replays prior context rather than resuming. It does NOT affect the separate
    30-day abuse-audit retention, which applies to all API traffic regardless.
    """
    if unknown:
        raise TypeError(
            f"respond() got unexpected keyword argument(s): {', '.join(sorted(unknown))}. "
            "Pass schema-enforced JSON via response_format=, not as a loose kwarg."
        )

    body: dict[str, Any] = {"model": model, "store": store}
    tools = tools if tools is not None else _build_tools(live)

    sys_parts: list[str] = []
    if grokmd:
        g = _load_grokmd()
        if g:
            sys_parts.append(g)
    if no_tool_guard and not tools:
        sys_parts.append(_NO_TOOL_GUARD)
    if system:
        sys_parts.append(system)

    if sys_parts:
        body["input"] = [{"role": "system", "content": "\n\n".join(sys_parts)},
                         {"role": "user", "content": prompt}]
    else:
        body["input"] = prompt

    if effort is not None:
        body["reasoning"] = {"effort": effort}
    if max_output_tokens is not None:
        body["max_output_tokens"] = max_output_tokens
    if tools:
        body["tools"] = tools
    if response_format is not None:
        body["response_format"] = response_format

    if dry_run:
        # The bounded-payload assertion: this is the complete outbound content.
        print(json.dumps(body, indent=2))
        return ("", {"dry_run": True}) if return_meta else ""

    t0 = time.monotonic()
    data = _post(body, timeout)
    latency = time.monotonic() - t0

    if data.get("error"):
        raise XAIError(str(data["error"]))

    usage = data.get("usage", {}) or {}
    detail = usage.get("output_tokens_details", {}) or {}
    meta = {
        "latency_s": round(latency, 3),
        "cost_usd": round(usage.get("cost_in_usd_ticks", 0) / 1e10, 6),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "reasoning_tokens": detail.get("reasoning_tokens"),
        "model": data.get("model", model),
        "tools_used": usage.get("num_server_side_tools_used"),
    }
    log.info("grok %s %.2fs $%.5f in=%s out=%s reason=%s live=%s",
             meta["model"], meta["latency_s"], meta["cost_usd"],
             meta["input_tokens"], meta["output_tokens"],
             meta["reasoning_tokens"], bool(tools))
    text = _extract_text(data)
    return (text, meta) if return_meta else text


# --- convenience tiers --------------------------------------------------------

def classify(instruction: str, text: str | None = None, **kw) -> str:
    """Hot-path classification: fastest model, no reasoning."""
    prompt = f"{instruction}\n\n{text}" if text is not None else instruction
    kw.setdefault("no_tool_guard", False)   # non-reasoning model can't emit stray tool calls
    return respond(prompt, model=FAST, **kw)


def analyze(prompt: str, *, live: bool = False, grokmd: bool = True, **kw) -> str:
    """Mid-tier analysis: grok-4.3, 1M context. Injects GROK.md by default."""
    return respond(prompt, model=WORKHORSE, live=live, grokmd=grokmd, **kw)


def deep(prompt: str, *, effort: str = "xhigh", live: bool = False,
         grokmd: bool = True, **kw) -> str:
    """Heaviest reasoning: grok-4.5, default effort xhigh. Injects GROK.md."""
    return respond(prompt, model=DEEP, effort=effort, live=live, grokmd=grokmd, **kw)


# --- panel seat ---------------------------------------------------------------

def build_appendix(paths: list[str]) -> tuple[str, list[dict[str, Any]]]:
    """Inline sources as a delimited appendix plus a manifest.

    The manifest is this seat's read-list equivalent: it cannot read files, so it must
    account for exactly what it received. Returns (appendix_text, manifest).
    Raises InlineTooLarge if the total exceeds MAX_INLINE_BYTES — caller drops the seat.
    """
    total = 0
    manifest: list[dict[str, Any]] = []
    chunks: list[str] = []
    for p in paths:
        with open(p, "rb") as fh:
            raw = fh.read()
        total += len(raw)
        if total > MAX_INLINE_BYTES:
            raise InlineTooLarge(
                f"inlined sources exceed MAX_INLINE_BYTES ({total} > {MAX_INLINE_BYTES}). "
                "Drop the Grok seat and state the reduced panel — do not truncate."
            )
        manifest.append({"path": os.path.abspath(p), "bytes": len(raw),
                         "sha256": hashlib.sha256(raw).hexdigest()})
        chunks.append(
            f"--- BEGIN INLINED SOURCE: {os.path.abspath(p)} ---\n"
            f"{raw.decode('utf-8', 'replace')}\n"
            f"--- END INLINED SOURCE: {os.path.abspath(p)} ---"
        )

    header = "\n".join(
        f"  {m['path']} | {m['bytes']} bytes | sha256 {m['sha256'][:16]}…" for m in manifest
    )
    appendix = (
        "\n\n## Inlined source appendix\n\n"
        "You have no filesystem access. The files below are the complete set you received;\n"
        "you cannot read anything else. In place of a read-list, report an INLINED-SOURCE\n"
        "MANIFEST reproducing the lines below verbatim, and quote the passages you relied on.\n"
        "If a finding would require reading a file NOT listed here, say so explicitly rather\n"
        "than inferring its contents.\n\n"
        f"{header}\n\n" + "\n\n".join(chunks)
    )
    return appendix, manifest


def panel_review(brief_path: str, source_paths: list[str], *,
                 effort: str = "xhigh", dry_run: bool = False) -> str:
    with open(brief_path, encoding="utf-8") as fh:
        brief = fh.read()
    appendix, manifest = build_appendix(source_paths)
    for m in manifest:
        log.info("inlined %s (%d bytes)", m["path"], m["bytes"])
    return deep(
        brief + appendix,
        effort=effort,
        system="No humour. No throat-clearing. Answer only. "
               "Disagree where warranted; no sycophancy.",
        dry_run=dry_run,
    )


def _main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if "--probe" in argv:
        if os.environ.get("XAI_API_KEY"):
            print("grok seat: available")
            return 0
        # Prereq-verification pattern (per _shared-patterns.md → transcribe): a failed probe
        # emits the specific remediation, not just the diagnosis.
        print("grok seat: unavailable (XAI_API_KEY unset)\n"
              "  setup: create a key at console.x.ai and load credits (no free tier), then export\n"
              "         XAI_API_KEY where a NON-INTERACTIVE shell sees it — ~/.bashrc commonly\n"
              "         exits early for those and won't work.\n"
              "  note:  xAI does not train on API data without explicit opt-in; requests are kept\n"
              "         30 days for abuse auditing. No console toggle to change.")
        return 1

    dry_run = "--dry-run" in argv
    argv = [a for a in argv if a != "--dry-run"]

    effort = "xhigh"
    if "--effort" in argv:
        i = argv.index("--effort")
        effort = argv[i + 1]
        del argv[i:i + 2]

    if "--panel-review" in argv:
        i = argv.index("--panel-review")
        brief = argv[i + 1]
        del argv[i:i + 2]
        sources: list[str] = []
        while "--source" in argv:
            j = argv.index("--source")
            sources.append(argv[j + 1])
            del argv[j:j + 2]
        if not sources:
            sys.exit("--panel-review requires at least one --source FILE")
        try:
            print(panel_review(brief, sources, effort=effort, dry_run=dry_run))
        except InlineTooLarge as e:
            sys.exit(str(e))
        return 0

    q = " ".join(argv) or "Reply with the single word: pong"
    answer, m = classify(q, return_meta=True, dry_run=dry_run)
    print("ANSWER:", answer)
    print("META:  ", m)
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
