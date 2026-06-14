---
name: archive-transcript
description: Archive a podcast/talk transcript from a URL into the vault — verbatim body plus a synthesis header — without routing the full text through context or letting a formatting hook corrupt verbatim quotes.
---

# Archive Transcript — Verbatim Capture + Synthesis

You are archiving one or more podcast/talk transcripts into the vault. Each note is the **verbatim transcript** with a short **synthesis header** on top. The user gives you one or more episode URLs (or a person/show whose appearances you find first).

Two principles drive this skill:

1. **Keep the transcript out of your context.** A transcript is ~10–20k words. Fetch and clean it straight to a file and append it to the note via the shell — never read the whole thing into the conversation. You write only the small synthesis header and read at most a few lines to verify boundaries.
2. **A formatting hook will corrupt verbatim quotes unless you bypass it.** This is the general problem in `_shared-rules.md` §14 — read it. The skill-local invariant: **write the header with the editor tool, append the body with the shell, and never `Write`/`Edit` the note again after appending.** The *why*, the precondition (the hook must not intercept shell writes), and the path-exclude alternative all live in §14.

## Phase 0 — Preflight

Confirm the pipeline's tools exist before fetching, so a fresh machine fails fast with a clear message rather than mid-pipe:

```bash
command -v curl pandoc python3 || echo "MISSING a core tool"
python3 -c 'import bs4, lxml' || echo "MISSING python bs4/lxml"
```

If anything is missing, tell the user and stop (or fall back to Phase 2 step 4).

## Phase 1 — Resolve the sources

1. If given direct URLs, use them.
2. If given a show or a person, find the appearances first (web search), confirm each URL, and list them back before fetching.
3. For each episode capture: show, host, guest, publish date, canonical URL.

## Phase 2 — Fetch the verbatim transcript to a file

Most podcast/show sites publish the full transcript in **server-rendered HTML** (Ghost and similar). The extractor below picks the content container with a parser, strips chrome, and converts to markdown — **no fragile line-marker slicing, no regex div-stripping**. The body never enters your context. (Validated against Ghost sites and Complex Systems' `c-content` template.)

**Code blocks below sit at column 0 deliberately** — the Python heredoc is indentation-sensitive, so copy it flush-left, not indented under a list item.

**Confirm static HTML:** `curl -sL "<URL>" | wc -c` — a large byte count is necessary but not sufficient (a JS shell can be large too); the real gate is the word count below.

**Extract → clean → markdown, per episode in its own temp dir** (so a multi-episode batch never collides on intermediates):

```bash
WORK=$(mktemp -d)
curl -sL "<URL>" -o "$WORK/ep.html"
python3 - "$WORK/ep.html" > "$WORK/body.md" <<'PY'
import sys, re, subprocess
from bs4 import BeautifulSoup
soup = BeautifulSoup(open(sys.argv[1], encoding='utf-8').read(), 'lxml')
# most-specific content container by PRIORITY (not densest — densest grabs the outer page wrapper)
node = None
for sel in ('section.gh-content', '.post-content', '.gh-content', '.c-content', 'article', 'main'):
    node = soup.select_one(sel)
    if node:
        break
node = node or soup.body
for t in node.select('script, style, nav, footer, form, button, iframe, figure, .kg-card, img, svg, audio, video'):
    t.decompose()
for h in node.find_all(re.compile(r'^h[1-6]$')):          # drop in-heading timestamp links, keep heading text
    for a in h.find_all('a'):
        a.decompose()
    txt = re.sub(r'\s*\(\s*[\d:apm.\s]*\)\s*$', '', h.get_text(), flags=re.I).strip()
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
echo "body words: $(wc -w < "$WORK/body.md")"
grep -cE '<div|</div|<span|base64' "$WORK/body.md"   # leak check — expect 0
```

**Gate on the word count + leak count**, not byte count: a body far below a real transcript (say < 800 words) means the selector missed the container — inspect structure (`grep -oE '<(article|main|section|div)[^>]*class="[^"]*"' "$WORK/ep.html" | sort -u | head`) and add the right selector to the priority list. A non-zero leak count means raw HTML survived — widen the `decompose`/`unwrap` set. Spot-check `head`/`tail` of `body.md` (a few lines) to confirm it starts/ends in transcript content.

**Metadata for the header, without reading the body** — published description (covers Ghost's `og:`/`twitter:` variants) and the section outline:

```bash
python3 - "$WORK/ep.html" <<'PY'
import sys
from bs4 import BeautifulSoup
soup = BeautifulSoup(open(sys.argv[1], encoding='utf-8').read(), 'lxml')
for sel in ('meta[name=description]', 'meta[property="og:description"]', 'meta[name="twitter:description"]'):
    m = soup.select_one(sel)
    if m and m.get('content'):
        print('DESC:', m['content']); break
PY
grep -E '^#{2,3} ' "$WORK/body.md"      # section outline, for the cruxes
```

**Fallback (no published transcript / JS-rendered):** use the vault's transcription path (a WhisperX/transcribe skill) on the audio or video. Much heavier — tell the user before launching a batch.

## Phase 3 — Write the note (header via editor, body via shell)

Per `_shared-rules.md` §14:

1. **Dedupe first**, keyed on the canonical source URL (catches retitled/renamed notes that a filename check misses), then title/date:
   ```bash
   grep -rl --fixed-strings "<canonical_url>" "<transcript-folder>" || echo "no existing note"
   ```
   If it exists, report it and ask whether to update or skip — don't write a duplicate.

2. **Match existing conventions.** Inspect one existing transcript note in the folder for its frontmatter schema and filename pattern; reuse them. Only if none exists, fall back to: filename `<Speaker> - <Title> (<Show>, <Year>).md`; frontmatter `title, show, host, guest, date, source, captured, type: podcast-transcript`.

3. **Write only the header** with the editor tool: frontmatter + synthesis.
   - The synthesis is **explicitly derived from the published description + section headings only** — say so in the note (e.g. a one-line provenance caveat). Do **not** present an authoritative "bottom line" you can't support without reading the body: give a *topic summary* + the section-derived **cruxes**, and flag relevance to the user's purpose. This respects "don't invent claims the page doesn't support."
   - End the header with a `## Full transcript` heading and a one-line provenance note (verbatim; source; that timestamp links were stripped from headings).

4. **Append the verbatim body via the shell** (bypasses the hook — §14):
   ```bash
   printf '\n' >> "<DESTINATION_NOTE>.md"      # guarantee a newline boundary
   cat "$WORK/body.md" >> "<DESTINATION_NOTE>.md"
   ```

5. **Never `Write`/`Edit` the note again after appending** — it re-fires the hook on the whole file, body included. Fix the header *before* appending, or re-append a fresh body.

## Phase 4 — Integrate, verify, report

1. **Link** the new transcript from the relevant person/dossier or topic hub. ⚠️ These are `Edit`s on *other* `.md` notes and fire the same formatting hook on them (§14 "collateral edits"): short edits to already-normalised hub prose are safe, but if a target note itself holds verbatim quotes, exclude it or append rather than `Edit`.
2. **Verify the append landed** — shell only, no context bloat:
   ```bash
   wc -w "$WORK/body.md" "<DESTINATION_NOTE>.md"   # destination should exceed body
   tail -n 5 "<DESTINATION_NOTE>.md"               # confirm it ends in transcript, intact
   ```
3. **Report:** file paths, final word counts, any episodes that fell back to transcription, and any fidelity caveats.

## Guidelines

- **Verbatim means verbatim.** Don't summarise, fix grammar, or let a hook rewrite the body. Synthesis lives in the header only.
- **Synthesis from structure, not from a full read.** Build the topic summary + cruxes from the published description and section headings; don't pull 15k words into context to write 8 bullets, and don't assert a thesis the metadata doesn't support.
- **Locale of the header follows the vault; locale of the body follows the speaker.** Your synthesis can be the vault's English; the transcript stays as published.
- **Match the vault's transcript conventions** (folder, filename, frontmatter) — inspect an existing note before inventing a layout.
