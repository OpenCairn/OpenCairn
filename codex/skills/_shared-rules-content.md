# Shared Rules — Content

Read only the numbered sections needed for the current operation. Core rules and the global section directory are in [_shared-rules.md](_shared-rules.md), in this same directory. Section numbers retain their original meaning; resolve a cross-file `§N` there and read its procedure before using it. These are instructions shared by skills, not an independently invoked workflow.

---

## 14. Verbatim External Text vs In-Place Formatting Hooks

When a skill writes **verbatim external text** to the vault — a transcript, a quoted source passage, an interview excerpt, anything whose exact wording must survive — an automatic in-place formatting hook can silently corrupt it. The Claude Code side of this vault runs such a hook (a spelling normaliser that fires on that harness's editor-tool writes to `.md` files and de-Americanises text in place, e.g. `color`→`colour`); **no equivalent hook is currently wired into Codex**, so a write from Codex cannot fire it — but the files a Codex skill writes remain reachable by the other harness, and if a Codex hook replacement lands (Codex hooks are beta), this section binds again in full. The word-level ignore files cannot help either way — you can't enumerate every foreign-spelled word a speaker might use.

**Rules that stay live under Codex:**

1. **Never let a hooked harness re-edit a verbatim note.** Write the synthesis header however you like, but the verbatim body is appended via the shell (`printf '\n' >> "$dest"; cat "$body_file" >> "$dest"`) and the note is never rewritten wholesale afterwards — any full-file rewrite by a hooked harness re-fires that harness's hook on the whole body.
2. **Path-level exclude is the robust defence.** If a formatting hook reads an exclude list (`exclude_paths` in a `config.local.json`-style file), the verbatim-output folder belongs on it — that holds regardless of which harness writes, and it is the only defence that survives collateral edits (adding wikilinks to a note that itself holds verbatim quotes).
3. **Inline identifiers and bare URLs.** In normalised prose, wrap stray foreign-spelled tokens and every bare URL in an inline code span (backticks) — a normaliser matches inside a URL's path segments, silently turning a correct citation into a 404 that reads to a later reader as fabricated. After writing any note carrying citations, extract its URLs (`grep -o 'https\?://[^ )`]*' <file>`) and confirm each still matches the source — verify after the write, not before.
4. **A hook's actual matcher is established empirically, never assumed.** Before relying on any bypass (shell append vs editor write), write a control file containing a known-rewritable token via each write route, re-read it, and record the result in the project's own reference doc.

---

## 15. Published-Transcript Extraction (fetch a verbatim body to a file)

The canonical procedure for pulling an **already-published** transcript (a podcast/show page, Substack, an official transcript page) off the web as a clean verbatim markdown body **in a file, never through context**. Single source of truth: `$archive-transcript` (its core job) and the published-transcript fast-path in `$transcribe` (Phase 0), `$transcribecloud` (Phase 1.5), and `$podcast-digest` (Tier 1a) all use this — point here rather than re-describing extraction in the skill. Each caller keeps its own *whether-to-use-it* framing (the cost/fidelity choice, dedup, the header it writes); this section owns only the fetch-and-extract mechanism. (Validated against Ghost sites and the Complex Systems `c-content` template; `curl`+`bs4`+`pandoc` beats reader APIs such as jina, which manufacture phantom pagination on static pages.)

**Prereqs** — confirm before fetching, so a fresh machine fails fast with a clear message rather than mid-pipe:
```bash
command -v curl pandoc python3 || echo "MISSING a core tool"
python3 -c 'import bs4, lxml' || echo "MISSING python bs4/lxml"
```
If a tool is missing, stop and tell the user (or fall back to machine transcription — see the fallback note below).

**Code blocks below sit at column 0 deliberately** — the Python heredoc is indentation-sensitive, so copy it flush-left, not indented under a list item.

**Confirm static HTML:** `curl -sL "<URL>" | wc -c` — a large byte count is necessary but not sufficient (a JS shell can be large too); the real gate is the word count below.

**Extract → clean → markdown.** The intermediate paths are a **deterministic function of the `<URL>`**, so they survive across tool-call boundaries with nothing to remember: a later step re-derives the same `$BODY` from the same `<URL>`, or just reuses the `BODY=` path the block prints (`<BODY_FILE>` in callers). This is the cross-tool-call hazard from `_shared-patterns.md` (shell vars don't persist), solved by making the path *reconstructable* rather than carried — no random `mktemp` name to lose. Where no stable per-item input exists, `mktemp` once, print and record the path, and derive sibling paths from it; scratch created and removed inside one tool call is out of scope. A multi-page batch never collides because the slug is per-URL:

```bash
TMP="${TMPDIR:-/tmp}"   # TMPDIR is often unset on Linux; /tmp is the reliable fallback
# deterministic per-URL slug (lowercase host+path prefix + cksum of the full URL) → reconstructable path, no random temp name
SLUG="$(printf '%s' "<URL>" | tr '[:upper:]' '[:lower:]' | sed -E 's#^https?://##; s#[^a-z0-9]+#-#g; s#(^-|-$)##g' | cut -c1-30)-$(printf '%s' "<URL>" | cksum | cut -d' ' -f1)"
HTML="$TMP/transcript_$SLUG.html"
BODY="$TMP/transcript_$SLUG.md"
echo "BODY=$BODY"   # the body path (<BODY_FILE> in callers); reconstruct it by re-deriving TMP+SLUG from <URL> in any later tool call
curl -sL "<URL>" -o "$HTML"
python3 - "$HTML" > "$BODY" <<'PY'
import sys, re, subprocess
from bs4 import BeautifulSoup
soup = BeautifulSoup(open(sys.argv[1], encoding='utf-8').read(), 'lxml')
# most-specific content container by PRIORITY (not densest — densest grabs the outer page wrapper)
node = None
for sel in ('section.gh-content', '.post-content', '.gh-content', '.c-content', 'article.post', 'article', 'main'):
    node = soup.select_one(sel)
    if node:
        break
node = node or soup.body
for t in node.select('script, style, nav, footer, form, button, iframe, figure, .kg-card, img, svg, audio, video'):
    t.decompose()
for h in node.find_all(re.compile(r'^h[1-6]$')):          # strip in-heading timestamp/permalink links, KEEP heading text
    for a in h.find_all('a'):
        atext = a.get_text().strip()
        if not atext or re.fullmatch(r'[\d:apm.\s()]+', atext, flags=re.I):
            a.decompose()                                 # empty or bare-timestamp anchor → drop it
        else:
            a.unwrap()                                    # anchor wraps real heading text → keep the text, drop the tag
    txt = re.sub(r'\s*\(\s*[\d:apm.\s]*\)\s*$', '', h.get_text(), flags=re.I).strip()
    if not txt:
        h.decompose()                                     # heading was nothing but a timestamp link → drop the empty heading
    else:
        h.clear(); h.append(txt)
for t in node.find_all(['div', 'span']):                  # flatten residual wrappers pandoc would emit as raw HTML
    t.unwrap()
md = subprocess.run(['pandoc', '-f', 'html', '-t', 'gfm', '--wrap=none'],
                    input=node.decode_contents(), text=True, capture_output=True).stdout
md = re.sub(r'\n{3,}', '\n\n', md)
md = '\n'.join(l for l in md.split('\n')
               if 'An error occurred' not in l and 'Unable to execute JavaScript' not in l)
print(md.strip())
PY
echo "body words: $(wc -w < "$BODY")"
grep -cE '<div|</div|<span|base64' "$BODY" || true   # leak check — expect 0 (grep exits 1 on no match; that's fine)
```

**Gate on the word count + leak count**, not byte count: a body far below a real transcript (say < 800 words) means the selector missed the container — inspect structure (`grep -oE '<(article|main|section|div)[^>]*class="[^"]*"' "$HTML" | sort -u | head`) and add the right selector to the priority list. A non-zero leak count means raw HTML survived — widen the `decompose`/`unwrap` set. Spot-check `head`/`tail` of `$BODY` (a few lines) to confirm it starts/ends in transcript content.

**Metadata for the header, without reading the body** — published description (covers Ghost's `og:`/`twitter:` variants) and the section outline:

```bash
python3 - "$HTML" <<'PY'
import sys
from bs4 import BeautifulSoup
soup = BeautifulSoup(open(sys.argv[1], encoding='utf-8').read(), 'lxml')
for sel in ('meta[name=description]', 'meta[property="og:description"]', 'meta[name="twitter:description"]'):
    m = soup.select_one(sel)
    if m and m.get('content'):
        print('DESC:', m['content']); break
PY
grep -E '^#{2,3} ' "$BODY"      # section outline, for the cruxes
```

**Names and speakers: the page's human-written text outranks the transcript body — per field.** The body wins on prose; it does **not** win on identity. A *published* transcript is frequently the publisher's own ASR, which garbles names phonetically and assigns speaker labels by voice-clustering guess: turns come out as `Unknown`, or get handed to whoever spoke last. The show notes, chapter list, resource links and pull-quotes on that same page are typed by a person. Each check below states the command **and** the observation that separates pass from fail — without the second half every one of them returns something plausible under both hypotheses and manufactures confidence.

**First, split `$BODY` into its two halves.** The extractor concatenates the human-written page text and the transcript body into one file, so "prefer A over B" is unusable until you know where A ends. Locate the boundary; everything below is scoped to one side or the other:
```bash
BOUND=$(grep -nE '^#{1,3} *(Transcript|Full [Tt]ranscript|Episode [Tt]ranscript)' "$BODY" | head -1 | cut -d: -f1)
if [ -z "$BOUND" ] || [ "$BOUND" -lt 3 ]; then echo "SPLIT FAILED (${BOUND:-no heading})"; else echo "boundary line: $BOUND"; fi
```
**⛔ `SPLIT FAILED` aborts the two checks below — do not run them.** This guard is the point: with `$BOUND` empty the slice commands error, but the errors are swallowed by their pipes and each check still emits a *plausible* result — an empty name set (which the rule reads as "the page never names them") and an empty timestamp scan (read as "no usable segment map"). A broken split therefore disguises itself as a legitimate finding *about the page*, which is the same confirmatory-only defect one level up. `BOUND < 3` catches the other direction: a nav link or a heading on line 1 matched first, which leaves the "human-written half" as a single heading line — and a degenerate range like `1,0p` may be accepted silently rather than erroring, so the guard cannot rely on the slice itself failing loudly (see the portability note above: `sed` behaviour here is implementation-dependent). On `SPLIT FAILED`, say the halves are unseparated and **flag** names rather than resolving them.

- **Provenance defaults to unverified, and only positive evidence upgrades it.** Absence of a disclaimer is not evidence of human editing — it is equally consistent with a differently-worded disclaimer, or one outside the selected container. So the header value starts at `published transcript (provenance unverified)` and moves to `(source-provided, auto-generated)` on a match, or to `(human-edited)` only where the page positively claims editing:
  ```bash
  sed -n "1,$((BOUND+8))p" "$BODY" | grep -niE 'automatically generated|auto-generated|AI-generated|machine.generated|may contain errors|transcribed by'
  ```
  **Scope it to the boundary region, not the whole body** — a disclaimer sits within a few lines of the transcript heading, whereas on an AI-topic episode those same phrases appear in the transcript as *subject matter* and would downgrade provenance on topical content. **Fail observation: zero matches ⇒ `provenance unverified`, never `human-edited`.** Never let the null select the stronger claim.
- **Names — compare the matched tokens, not the match count.** A stem grep is non-empty whether the two halves agree or diverge, so hit-count cannot detect garbling. Extract and diff the actual tokens, one side at a time:
  ```bash
  sed -n "1,$((BOUND-1))p" "$BODY" | rg -oi '<stem>[a-z]*' | tr 'A-Z' 'a-z' | sort -u   # human-written half
  sed -n "$BOUND,\$p"      "$BODY" | rg -oi '<stem>[a-z]*' | tr 'A-Z' 'a-z' | sort -u   # transcript half
  ```
  Use a **stem** (whole-surname matching fails — the garbling is phonetic). The `tr` is load-bearing: `rg -oi` matches case-insensitively but prints the *original* case, so without it a name styled all-caps on one side and title-case on the other reads as divergence, and the runner "corrects" a spelling that was already right. Chapter lists and pull-quote attributions are commonly styled in caps, so this is the ordinary case, not an edge one. **Fail observation: the two lowercased token sets differ ⇒ the human-written half's spelling wins** (take its original-case form from the un-`tr`'d output). Identical sets means agreement, not that you skipped the check; an empty human-written set means the page never names them — then correct from your own knowledge or flag, never invent, and never report a name unresolvable that this comparison would have settled.
- **Speakers — find the timestamped chapter list, which is usually *not* headings.** The section outline the metadata block extracts is often navigational (`Show Notes`, `Resources`, `Transcript`), naming no participant and carrying no time; a page's real segment map is frequently bold prose or a plain list. Scan the human-written half for leading timestamps:
  ```bash
  # rg, not grep, deliberately. rg's -E is --encoding, so -n alone (extended syntax is rg's default).
  sed -n "1,$((BOUND-1))p" "$BODY" | rg -n '^[^a-z0-9]*\(?\**\[?[0-9]{1,2}:[0-9]{2}(:[0-9]{2})?'
  ```
  The leading class is deliberately unbounded (`*`, not a `{0,4}` cap): a bullet-and-bold prefix like `- **(0:01)**` already spends four characters, so any capped bound is calibrated to one page's exact decoration and an indented or slightly heavier list silently stops matching.
  A turn whose timestamp falls inside a segment naming one participant is that participant, and the show-notes prose says who argued what. **Fail observation: no line carrying a leading timestamp ⇒ there is no usable segment map — fall back to conversational cues, and attribute nothing you cannot place.** A non-empty *outline* is not a usable map; the map must carry times.
- **Never edit the verbatim body to match** (per §14) — correct the header/synthesis and report the divergence.

⚠️ The word/leak gate above tests a fixed tag set, so inline tags outside it survive into `$BODY` — which matters here in a way it doesn't for verbatim appending, because a surviving tag run buries the divergence mid-line inside multi-thousand-character prose. Pipe through `sed -E 's/<[^>]+>//g'` when resolving identity, and count what actually survived — `grep -coE '<[a-z][^>]*>' "$BODY"` — since the gate itself can only ever report on the tags it enumerates. A non-zero count is the reason to widen that set for the next run.

**Fallback (no published transcript / JS-rendered):** machine-transcribe the audio/video instead — the WhisperX path (`$transcribe` locally, `$transcribecloud` on a cloud GPU). Much heavier; tell the user before launching a batch.

---

## 24. Driving the Obsidian CLI (link-healing moves, batches, verification)

Canonical rule and **single source of truth** for every skill that moves, renames, or deletes vault files through the `obsidian` CLI — `quarterly-hygiene` Step 6, `complete-project` Step 4, `inbox-processor` Step 4. Those skills point here and carry no copy to drift. The procedure below was last exercised end-to-end against **Obsidian 1.13.4** (link-healing move, async settle, verify-by-result); the older behaviour notes date from **1.12.7** and not every one has been re-tested since. Treat the version stamp as a staleness marker, not a guarantee, and re-verify rather than trusting it indefinitely.

**The durable rule, independent of any tool version.** A path-qualified wikilink (`[[folder/note]]`) does not survive the file moving unless something rewrites it. Vault-note moves therefore go through `locked-edit.sh <source> --move <destination> <expected-source-sha256>`. That wrapper creates a missing destination directory, holds both canonical endpoint locks, checks the source snapshot and destination collision, delegates to the live Obsidian CLI, and verifies the final paths, content hash and old path-qualified links. Raw `mv` is never a fallback. If the wrapper refuses, **move nothing else and defer**.

Obsidian link-target healing applies to non-hidden Markdown notes throughout the vault, including `06 Archive/`. Archive immutability protects the record's prose, decisions, formatting and timestamps from deliberate editing; it does not preserve stale navigational link targets in those notes. If the historical path itself is evidence, record it as plain text or code rather than as a navigational link. Move receipts let `$park` verify these automatic rewrites as mechanical without rereading archived records semantically.

The caller reads and hashes the source before invoking the wrapper. A source or destination may be absolute or vault-relative, and both must resolve inside `VAULT_PATH`. Exit 2 is a stale snapshot or a path that changed while waiting for locks. Exit 1 is a precondition, CLI or result-verification failure. Neither is permission to retry blindly or move the file directly.

**Do not rely on basename fallback to cover a raw `mv`.** Two independent reasons, and the second holds regardless of resolver behaviour: a path-qualified link is a path, not a name; and vault filenames are far less unique than they look — date-keyed conventions (`YYYY-MM-DD.md`) collide exactly across folders, so a bare-name resolution can bind a different note entirely. Any skill claiming a "globally unique basename" exception is asserting something the vault's own naming conventions contradict.

**Current CLI behaviour (the volatile half — this is the only place it is stated).** The wrapper owns these mechanics; skills invoke the wrapper rather than recreating them.

- It drives the **already-running app**; it does not boot an instance per call. So a batch is fine, and it is fast. It also heals inbound wikilinks including `#heading` anchors.
- **It requires the app to be running.** With no app, calls silently do nothing and every item appears to fail. Probe before writing anything (`obsidian version`), and treat a whole-batch failure as the app being down rather than a per-file problem.
- **It reads stdin.** Inside a `while read` loop it swallows the loop's input, so only the first item is processed while the run still looks successful. Pass `</dev/null` on every call.
- **⛔ Derive the invocation form before the first write call of a batch — from the CLI's own help subcommand, never from memory.** Argument *style* is version-volatile (positional vs named), and getting it wrong is not a loud failure: a mis-formed call can print a usage string, change nothing, and still exit 0. Ask the tool: `<cli> help <subcommand>` returns the parameter list. Two traps to avoid on the way there — the `--help` **flag** is not the same route and a subcommand may ignore it and simply execute; and **never probe syntax by running the bare or deliberately-incomplete command**, because a destructive subcommand with no explicit target may default to one (the active file, the current directory) and act on it. Then confirm the form against your vault's CLI-reliability reference (below) rather than assuming it matches the last version you used.
- **Operations apply asynchronously and the exit status is unreliable in both directions.** It can be non-zero on success; it is also **zero when the call did nothing at all**. So a skill keying on exit codes can report a clean batch having moved not one file. Verify by **result** — the file's presence at source *and* destination — after a settle delay of a couple of seconds. Never key on the exit code or an immediate `test`. Re-verify an apparent failure after a further delay before retrying.
- **Run the first item of a structural batch as a canary.** Verify it by result before issuing the rest. This is what converts a version-drift surprise from a half-applied batch into one failed call, and it is the only cheap defence against the exit-0-did-nothing mode above.
- **The per-subcommand specifics — which subcommands work, their current argument style, their known silent failures — live in your vault's CLI-reliability reference, not here.** That table is versioned and rechecked per subcommand; this section carries only the durable procedure. Read it before a structural batch, and add a dated row when you learn something new. Same reasoning as the backlinks rule below: what a given CLI version does changes under you, so it needs one canonical, updatable home rather than a copy inside every skill.
- **Graph queries (`unresolved`, `backlinks`) return empty or stale while the app reindexes. Empty is not zero** — re-query once the index settles rather than reading a blank result as a pass.
- **⛔ Before gating a destructive action on a backlinks result, check that the route is one your vault's search-routing doc marks reliable.** A settled index is not sufficient: a subcommand can return false *negatives* — a confident "no inbound links" for a file that has them — in which case waiting for the index changes nothing. **Treat a nil from an unverified route as *unknown*, not as zero**, and never let it authorise a raw `mv` or a delete. This is the specific failure this section exists to prevent, and it is the reason the reliability verdict lives in the routing doc rather than here: which route is trustworthy changes with the app and plugin versions, so it must have one canonical, updatable home.
- **Link healing writes the copies of a duplicated file non-atomically.** If a batch is resolving duplicate pairs and each move heals links inside files *later* in the batch, a byte-compare of a still-unresolved pair can catch one copy mid-rewrite and report a difference that is not real. So **re-verify a refusal or skip after a delay before treating it as genuine**, exactly as for an apparent failure. A compare-before-delete guard is still correct: its failure mode is a false skip, never a false delete.

**Verification, and it must produce numbers.** Take the vault's unresolved-link count before the batch and again after; a link-preserving move must not increase it. Then confirm no moved item appears as an unresolved target. A skill that reports no numbers has verified nothing.

**Structural moves need the sync client ON.** Moves made while a vault's sync client is off never reach the remote, so the remote keeps the pre-move tree; the next merge-on-reconnect pushes it back down and **resurrects a copy of everything just moved**. The resurrection is silent, and because the resurrected copies absorb the inbound links, nothing looks broken while duplication accumulates. This is not shell-checkable — confirm with the user before a structural batch, and record which way it went.

**Checkable:** no skill executes raw `mv` or direct `obsidian move` on a linked vault note; every structural move uses `locked-edit.sh --move`, and every structural batch reports a before/after unresolved-link count. A skill restating this section's CLI behaviour instead of pointing at it is the drift this section exists to prevent.

---

## 26. Web-Fetch Fallback Ladder (getting a page body)

Canonical fetch order for any skill that needs a web page's content from a known URL. Ordered so the free, exact-bytes route comes first and credit-metered scrapers last — a metered scraper as the default rung burns quota on pages plain `curl` handles, and its quota exhaustion then breaks every skill that leads with it.

1. **§15 static extractor** (`curl` + `bs4` + `pandoc`) — first rung for any article/transcript-shaped page. Free, and it leaves the exact source bytes on disk, which quote-fidelity checks require. Its word-count gate is the self-diagnosis: a body far short of the visible article means a JS-rendered page — climb to rung 2 rather than iterating selectors indefinitely.
2. **Configured fetch MCPs** — whichever reader/scraper servers are registered with the harness (check `codex mcp list`). ⛔ **A credits/quota/plan-limit error is unavailability, not failure:** move down the ladder without retrying, stalling the run, or asking the user to top up mid-task. Reader APIs can manufacture phantom pagination on static pages (§15) — that is why this is rung 2, not 1. Anti-bot-blocked pages (403/429/Cloudflare) are the one case to *start* here: rung 1's plain `curl` is refused identically.
3. **Harness-native web tooling** — last rung. Codex's `web_search` tool serves search-shaped needs and gist; it never returns a verbatim page body, so a skill with a fidelity requirement that ends up here records the gap instead of quoting.

Search-shaped needs (no known URL) are a different tool class — the harness's web-search tool or a configured search MCP — with the same quota-is-unavailability rule for metered ones. Where a skill records provenance for the fetched body, name the rung that produced it.
