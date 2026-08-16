---
name: archive-article
description: Archive an article (research paper, clinical study, technical piece, or news report) into the vault as a structured reference note — synthesis, citation, and wikilinks
---

# Archive Article — Structured Knowledge Capture

You are archiving an article into the vault as a structured reference note. The user has shared an article (URL, pasted text, or both). It may be from any domain — a research paper, clinical study, technical write-up, essay, or news report. The Phase 5 template spine is domain-neutral — adapt its section names to the material (clinical articles get clinical headings; see Phase 5), and don't force an article from one domain into another's mould.

## Instructions

### Phase 0: Resolve vault path

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

If error, abort — the usual cause is `VAULT_PATH` unset (a required install precondition; `/setup` documents how to set it per-OS). All paths below use `{VAULT}` as a placeholder — substitute the resolved vault path.

Then read `_shared-rules.md` (same commands directory as this file) and apply its rules throughout this skill — §14 (verbatim text vs formatting hooks) is load-bearing here.

### Phase 1: Gather the Article Content

Identify the article body, applying this **source precedence** when more than one is present: **text the user explicitly provided for this archive (a paste) > content already fetched this session (don't re-scrape) > a fresh scrape of the URL** (use the lower-priority ones for citation metadata). A newer explicit paste or correction always beats an older fetch.

1. **If the user pasted the text**, use that.
2. **If the content is already in the conversation** (fetched by a prior step or agent this session), use that — don't re-scrape — and note its provenance for the citation. If several articles are in play, confirm which one is meant before proceeding.
3. **If the user provided a URL**, fetch it via the `_shared-rules.md` §26 ladder: the **§15 static extractor** first (free, and it leaves the exact source bytes on disk — which the Phase 7 quote checks need) → else a configured fetch MCP (e.g. `mcp__firecrawl__firecrawl_scrape` with `waitFor: 5000`, or a jina/exa fetch; a credits/quota error counts as unavailable — move down, don't retry) → `WebFetch` last, and only for metadata/gist: its summarised output cannot ground verbatim quotes, so record the fidelity gap if the note is built from it.
4. **If no usable body remains** (URL-only and every ladder rung fails, nothing pasted, nothing in-conversation), ask the user for pasted text or a different link — **do not** fabricate a content note from citation metadata alone.

### Phase 2: Find the Primary Source

Journalism and secondary write-ups report on primary research or source material. The primary source (the paper, dataset, official document, or original post) is more valuable than the report on it.

1. **Look for identifiers** — DOIs, journal names, author names, or links to the original source in the article text.
2. **If the user provided a DOI**, fetch citation metadata from it (follow redirects — DOI resolves via `doi.org` → publisher).
3. **If no identifier is available, attempt automated discovery:**
   - *Academic / medical work:* search PubMed (`https://pubmed.ncbi.nlm.nih.gov/?term={title keywords}+{first author surname}`) — fast, structured citation metadata; and/or a configured search MCP with the title + venue.
   - *Non-academic sources:* search for the original publication/author to reach the primary version rather than an aggregator.
   - **Only if all automated paths fail**, ask the user for the DOI/source link.
4. **Extract citation metadata**, source priority: PubMed / publisher `<meta>` tags (e.g. `citation_author`, `citation_title`, `citation_online_date`) > publisher page > scraped body (verify against another source).
5. **Prefer the primary as the synthesis basis, not just the citation.** If the primary's abstract or full text is cheaply reachable (PubMed abstract, open-access page), fetch it and synthesise from it, using the secondary report only as context. If only the secondary body is available, the note must say so — the "Reported by" line in the Source section (Phase 5) plus a gap note in Phase 7's report. Don't dress a secondary-report summary in primary-paper framing.

### Phase 3: Classify and Propose a Location (ask before placing)

Don't assume a destination — infer the article's domain, propose a home that fits the vault's existing structure, and let the user confirm. **Do not write the note until the destination is confirmed.**

1. **Infer the domain and the actionable insight** — what is this about, and what would the user *do differently* or *refer back to* as a result? Classify by that insight, not just the topic.
2. **Propose a destination by inspecting the vault.** Search `04 Areas/` by the article's topic / author / domain keywords — use the **Grep tool** scoped to `{VAULT}/04 Areas`; **never an unbounded `rg --no-ignore` or unfiltered `grep -r` over the vault** (the tree-walk cost rule in Phases 4 and 6 applies here too). Then read 1–3 candidate notes to find the cluster it belongs with (same topic, authors, or thread). If a fitting cluster exists, propose it. *Don't assume a generically-named subfolder (`Research/`, `Articles/`) is that cluster — a folder's name often describes something other than its contents, so verify by inspection.*
   - *Recurring destination:* if the vault already has an established home for this kind of article (a clinical-knowledge folder, a research-notes cluster), prefer it — but verify its **live** structure by inspection rather than assuming a subfolder taxonomy exists; don't invent one. (You can still classify by the actionable insight — what the reader *does differently* — in the note's framing, wherever the file lands.)
   - *No established home:* route to the relevant area of the vault (e.g. a genetics paper to its research cluster, a technical piece to a computing area). Create a sensibly-named subfolder only if none fits.
3. **Ask the user where to store it.** Present your recommended path plus any cluster alternative you found, and ask them to confirm or name a different location. Wait for the answer before writing.
4. **Generate a filename** from the key takeaway, not the raw paper title — but match the destination's existing convention (a takeaway-style name like "Treatment X and Procedure Y Safety.md" for a practice-notes folder; `Author et al — Topic (Venue Year)` if joining a research cluster that uses it). Before writing, inspect **2–3** existing notes in the destination folder and follow the **modal** filename + frontmatter convention (only invent a layout if the folder is empty).

### Phase 4: Check for Duplicates

Before writing the file, check whether this paper has already been archived. (If a DOI is already known before the Phase 3 ask, run the DOI check first so a duplicate and the destination resolve in one user interaction, not two.)

1. **Check the DOI (if available) and the canonical source URL — as fixed strings, vault-wide.** Both are unique strings, so a match anywhere means it's already archived; the URL check catches a retitled/renamed note that step 2's keyword check would miss (same dedupe mechanism as `archive-transcript`). Use the **Grep tool** (rg-backed); **never an unbounded `rg --no-ignore` or an unfiltered `grep -r` over the vault** — those read content across the untracked mass (see `_shared-rules.md` §25 on grep-vs-rg in executable blocks). A unique-string check is a safe whole-vault sweep.
2. **Check distinctive title keywords** (2-3 unique terms) scoped to the proposed destination + any Phase-3 cluster (keywords are noisier than a DOI); widen vault-wide only if needed.
3. **If a match is found**, report it to the user and ask whether to update the existing note or skip. Do not create a duplicate.

### Phase 5: Write the Note

Use this template as a spine, adapting section names to the material — the adaptations below define which sections are applicable per material type; within the applicable set, every section is required. **Compose the note in full — including the Phase 6 wikilinks, whose targets you verify first — and write it in a single `Write`.** Don't write the note and then edit links in afterwards: each `Write`/`Edit` re-fires the formatting hook on the whole file.

```markdown
# {Title — the key takeaway, not the raw paper title}

**Bottom line:** {One sentence. What should the reader do differently, conclude, or be able to rely on?}

## Key Findings

- {3-5 bullets. Concrete numbers, outcomes, claims. No fluff.}

## Details

- **Source:** {Institution(s) / author(s) / outlet}
- **Design / nature:** {Study type + sample size, or the kind of piece it is}
- **Subject:** {What/who was studied or covered}
- {Additional methodological or contextual detail as relevant}

## Why It Matters / Application

- {2-4 bullets. How does this change practice, decisions, or understanding? When would you use it?}

## Limitations

- {2-4 bullets. Honest caveats — sample size, design, generalisability, bias, uncertainty}

## Source

{Full citation: Authors. Title. *Venue*. Date. doi/URL. (PMID if applicable.)}
{If via a secondary report: "Reported by: Author. Title. *Publication*, Date."}
```

Adapt the spine to the material:
- **Clinical articles:** a clinical corpus is often **mixed** (some notes use Study Details / Clinical Application / Limitations; others use Mechanism / Evidence / Practical / Safety) — inspect 2–3 sibling notes and match the closest convention rather than forcing a fixed set. Common clinical headings: "Study Details", "Clinical Application", "Limitations"; include practical tips where the source gives them (e.g. "have silver nitrate on hand").
- **Guideline / consensus / review (not a study):** drop "Details"/"Limitations"; use "Key Recommendations" or "Guideline Summary".
- **Essay / opinion / news:** "Key Findings" → "Key Points"; "Limitations" → "Caveats / Counterpoints" where relevant.

### Phase 6: Add Wikilinks

This runs **while composing the note, before the Phase 5 write lands** (see the single-write rule in Phase 5) — verify targets, then include the links in that one write.

**⛔ Link only to notes that already exist. Verify each target before writing it.** A wikilink is navigation, not annotation — `[[term]]` where no `term.md` exists creates nothing but an entry in the unresolved-links report and a dead click. Never mint a link speculatively, never invent a note name to link to, and never link a concept just because it's important.

Procedure: shortlist the entities worth linking (conditions, procedures, drugs, people, methods, tools — whatever the domain's key nouns are), then check each against the vault's live index before it goes in. **Prefer the live index over a text sweep here** — a filename lookup is a structural query, so use the `obsidian` CLI (below) or the Grep tool on filenames rather than an unfiltered `grep -r` over note contents (`_shared-rules.md` §12: prefer structural queries for link questions).

```bash
obsidian file file="<term>" 2>/dev/null | grep -q '^path' && echo EXISTS || echo "no hit"
```

The per-term lookup is its own liveness test — a dead or absent CLI reads as "no hit" for every term, and that failure direction is safe (a missed link, never a dead one), so no separate health probe is needed.

Match is **exact, not fuzzy** — a partial name returns not-found, so there are no false positives. The discriminator is the `^path` line, **never** the exit code: per `_shared-rules.md` §24 the CLI's exit status is unreliable in both directions, so `&&` on `$?` alone can silently pass every term. Current per-subcommand behaviour is §24's territory, not this skill's — if the lookup misbehaves, check there.

A hit → link it, using the exact filename the command echoes back (alias with `|` if the prose needs different wording). No hit → **leave the term as plain text**. If the CLI is down, don't guess — either use a filename-scoped search route (Grep tool on names, not contents), or ship the note with plain text. If the shortlist yields no hits, the note ships with no wikilinks; that is a normal outcome, not a failure.

Also check the destination folder's convention (Phase 3 already had you read 2–3 siblings): if no sibling links to a non-existent note, don't be the first. Linking a related *document* — a sibling note, a source PDF, a hub — is usually worth more than linking a concept anyway.

Don't over-link — once per term per note, on first meaningful use, not in the title line unless it reads naturally.

### Phase 7: Verify and Report

1. Confirm the file was created at the expected path.
2. **Run the quotation-fidelity check** (see the Guidelines bullet for the full rule, including the two exemptions), both commands against the **saved** file:
   - `grep -nE '["“”‘]' <path>` — inline quoted phrases.
   - `grep -nE '^ *>' <path>` — block quotes, which the first command cannot see.
   Confirm each hit against the fetched source text. Fix any that don't trace — drop the quote marks (or unindent the block to plain prose), or backtick the token if it's spelling-hook corruption. Display: `Quote check: N quoted phrases, M block quotes, all traced ✓` (use `0` for either count rather than omitting it).
3. **Check the citation line for hook corruption.** A spelling hook rewrites unbackticked title/venue tokens after the write, and the quotation greps can't see them. Re-read the saved Source line and compare the title, venue, and author spellings against the fetched citation metadata; for any source-spelled token, also grep the saved file for the hook's re-localised form. Fix a mismatch by backticking the token and rewriting the line — never by accepting the altered spelling. Display: `Citation check: title/venue spellings match source ✓` or name what was fixed.
4. Report to the user:
   - File path
   - Which folder it landed in (the user-confirmed destination, and why, briefly)
   - Any gaps (e.g. "DOI not available — citation is from the news report only")

## Vault Path

No fixed destination — it's proposed per article and confirmed with the user (Phase 3). Articles route to the relevant area under `{VAULT}/04 Areas/` (or wherever the fitting cluster already lives), matching the vault's existing structure by inspection.

## Guidelines

- **Spell per the user's locale** (see CLAUDE.md). This governs *your prose only* — see the next bullet for verbatim text.
- **Citation fidelity vs the spelling hook.** Paper titles, journal names, and any directly quoted phrases keep the source's original spelling (e.g. "Randomized" stays "Randomized" in a British-English vault) — never "correct" them. A PostToolUse spelling hook, if active, will silently re-localise these on `Write`/`Edit`; protect affected tokens with inline code spans per `_shared-rules.md` §14.
- **Match the destination's existing conventions.** Before writing, inspect 2–3 existing notes in the target folder and follow the modal filename + frontmatter convention; only invent a layout if the folder is empty.
- **⛔ Quotation fidelity: every quoted phrase must trace to fetched text.** Quotation marks assert *exact wording*. If you are paraphrasing, or condensing a source's phrasing into a tighter label, **drop the quote marks** — unquoted paraphrase is honest, quoted paraphrase is a fabricated quotation. Two failure shapes to watch, both of which read as fluent and correct: (1) **inventing a quote** for a claim the source makes in different words; (2) **substituting a domain near-synonym** for a source term (a technical qualifier swapped for one that sounds equivalent but is not, especially in clinical/legal/financial material where the two carry different meanings). Synthesis notes are built mostly from secondary reports, and paraphrase-drift is where fidelity leaks — the primary's own wording, where you have it, always outranks a secondary's restatement of it.
  - **Run the check in Phase 7, after writing, against the saved bytes** — a `grep` cannot read a note that isn't on disk yet, and the spelling hook rewrites the file *after* your `Write`, so a pre-save check verifies text the reader will never see. `grep -nE '["“”‘]' <path>` — straight *and* typographic double quotes, plus the left curly single quote; scraped bodies and pastes routinely carry the curly forms, so a `"`-only search false-passes in silence. Straight and right-curly single quotes are deliberately excluded (every apostrophe would hit), so the grep cannot surface a straight-single-quoted quotation — the fidelity rule still covers those; don't use single quotes to route around the check. Block quotes (`>`) are in scope too, and the quote-mark grep cannot see them — that is what the companion `grep -nE '^ *>' <path>` is for.
  - **Confirm each hit against the fetched text, not your memory of it.** Keep the fetched bodies reachable (a scratch file, or the tool result still in context) so the comparison is a literal search rather than the recollection this rule exists to distrust. If a source has left context, re-fetch it before checking — never adjudicate a quote from memory.
  - **Two exemptions, or the check fails on its own compliant output.** (1) **Strip inline code spans before comparing** — the citation-fidelity bullet above tells you to wrap source-spelled tokens in backticks, which the source never had, so the raw string won't match. (2) A mismatch confined to a spelling-hook-mapped word is **hook corruption, not a bad quote** (`_shared-rules.md` §14): fix it by backticking the token, never by dropping the quote marks or "correcting" the source.
- **Synthesis over transcription.** The note should be more useful than the original article — distil, don't copy.
- **No editorialising.** Report what the source found. Save opinions for the Application section, and frame them as practical guidance.
- **Disambiguate dates.** A secondary report's date and the primary source's publication date are different things. State both if available.
- **Adapt to the material.** If it isn't a study (guideline, consensus statement, review, essay, news), use the Phase 5 adaptations rather than forcing study-shaped sections.

## Triggers

This command should trigger when the user says:
- "archive this article" / "archive article" / "save this article" / "archive this paper"
- "clinical pearl" / "clinical article" (clinical mode)
- Pastes an article URL/text and says something like "save this" or "add to vault"

## Skill Monitor

As you execute this skill, follow `_skill-monitor.md` (same commands directory as this file): watch for gaps, and log observations at the end per that file.
