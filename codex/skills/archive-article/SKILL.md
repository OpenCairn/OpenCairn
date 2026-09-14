---
name: archive-article
description: Archive an article or research paper into the vault as a structured reference note with synthesis, verified citations and existing-note links.
---

# Archive Article

Archive the article the user supplied as a useful reference note, matching its domain and the destination's conventions. Accept a URL, pasted text, or content already fetched in this session. This is synthesis, not a verbatim full-text archive; use `$archive-transcript` for published podcast/talk transcripts.

## Phase 0: Resolve the vault

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

Stop on failure; never guess the vault path. Read [../_shared-rules.md](../_shared-rules.md) (core, including §§5 and 25), then [../_shared-rules-content.md](../_shared-rules-content.md) §§14, 15 and 26. Read the vault's search-routing document when available. All vault creates, edits and appends use `locked-edit.sh`; an editor or `apply_patch` is not a substitute. Supporting paths are relative to this skill directory, not the shell working directory.

## Phase 1: Gather the article

Source precedence: the user's explicit paste or correction for this archive → content already fetched this session → a fresh fetch. Reuse available content; do not scrape again just to repeat a completed step. Use other sources for metadata or cross-checking. If several articles are in play and the target is unclear, ask which one.

For a URL, follow the shared §26 fetch ladder:

1. Use §15's static extraction mechanics (`curl`, `python3` with `bs4`/`lxml`, `pandoc`) to preserve source text on disk. Its transcript word-count floor, transcript-heading split and speaker checks do **not** apply to articles. Judge whether the actual article body was extracted, including short articles.
2. If needed, use an available configured page-fetch connector. A quota/credit error means move to the next route, not retry or ask for a top-up.
3. Use Codex web tooling for discovery and available source text. If a result supplies only a summary or metadata, label that limitation; it cannot support verbatim body quotes.

Keep the text used for the synthesis and quotation checks reachable in scratch files or tool results. If no usable body remains, ask for pasted text or another link. Do not manufacture an article note from metadata alone.

## Phase 2: Identify the primary source

Look for a DOI, original-paper link, dataset, official document, author or original publication. Resolve a supplied DOI and verify its citation metadata. If discovery is needed, search the title and author through PubMed/publisher sources for academic work, or the original author/publisher for other material. Ask for an identifier only after the available automated routes fail.

Prefer citation metadata from PubMed or publisher metadata tags, then the publisher page; cross-check metadata extracted from a scraped body. Do not infer missing authors, dates, sample sizes or identifiers.

When the primary abstract or full text is reachable, read it and use it to verify the secondary report. Prefer the primary as the synthesis basis unless the user explicitly wants the secondary piece archived in its own right. Distinguish abstract-only access from full-text access. If only the secondary body is available, say so in the note; a primary citation does not turn a secondary summary into a primary-source reading. Keep the report's publication date separate from the primary's date.

## Phase 3: Choose a destination

Honour a destination already specified by the user. Otherwise inspect relevant area folders and propose a fitting location, then obtain the user's choice before writing. A folder name alone does not establish its contents.

Classify by the article's useful insight as well as its topic. Search the relevant `04 Areas/` surface for topic, author and domain terms; read promising notes to identify an existing cluster. Prefer an established home over inventing a taxonomy. If a new subfolder is needed, include it in the destination proposal.

Inspect 2–3 sibling notes where available, following their usual filename, frontmatter and section conventions. Use a takeaway filename for a practice-notes collection or an author/topic/venue filename where that is the existing convention. Do not ask again about an already-specified path or equivalent low-stakes naming choices.

## Phase 4: Check for duplicates

Before writing, search the canonical URL and DOI, when available, as literal strings across the vault's Markdown notes. Run this before the location question when it can resolve both in one interaction. Bound by file type, not a hand-picked folder list:

```bash
rg -l -F --hidden --no-ignore -g '*.md' -g '!**/.git/**' \
  -- "<DOI_OR_CANONICAL_URL>" "$VAULT_PATH"
```

Run each identifier separately. Exit 1 means no matching Markdown note on that searched surface; another error means the search failed. Inspect every candidate before calling it a duplicate: a source mentioned in a reading list or project note is not an archived article. Search distinctive title terms in the intended folder and related clusters too, widening if needed.

An existing archive → ask update or skip unless already authorised. A mention-only hit → continue and report/link it where useful. Also check the destination filename for collisions. Do not overwrite an unrelated note.

## Phases 5–6: Compose, link and save

Compose the complete note, including verified links, before saving. Use this spine proportionately, adapting to the material and the folder's conventions:

```markdown
# {Title}

{One-sentence takeaway supported by the source.}

## Key Findings

- {Concrete findings; preserve qualifications and denominators.}

## Details

- **Source:** {Authors / institution / outlet}
- **Design / nature:** {Study design and sample, or type of piece}
- **Subject:** {What was studied or discussed}

## Application

{What the findings may change, with inference distinguished from source claims.}

## Limitations

{Relevant uncertainty, design limits or counterpoints.}

## Source

{Verified citation, DOI/URL and PMID where applicable.}
{Reported by: secondary citation, if used. State the actual synthesis basis.}
```

For clinical material, match the closest sibling convention, such as Study Details / Clinical Application / Limitations or Mechanism / Evidence / Practical / Safety. Include practical details only where the source supports them. For guidelines or consensus documents, use Key Recommendations or Guideline Summary rather than forcing study sections. For essays or news, use Key Points and relevant Caveats / Counterpoints. Omit inapplicable fields rather than filling them with guesses.

Shortlist useful related documents or entities, then verify each link target against the actual vault. Use the search-routing document's reliable filename/index route; if Obsidian is unavailable, enumerate filenames with `rg --files --hidden --no-ignore -g '*.md' -g '!**/.git/**' "$VAULT_PATH"` and confirm candidate paths. Tool errors are not proof a note is absent. Resolve ambiguous basenames with the full vault-relative path. Link only existing notes, at most once per meaningful term; plain text is valid when no verified target exists. Do not create speculative concept links.

Stage the final Markdown outside the vault. For a new note, use a locked append after the collision check:

```bash
"$VAULT_PATH/.claude/scripts/locked-edit.sh" "<DESTINATION>" --append < "<STAGED_NOTE>"
```

For an authorised update, read the existing note first, preserve unrelated content and use the wrapper's literal `--replace` mode. On exit 2 or 3, re-read and rebuild a unique match. Do not bypass the lock. Check the exit code and read the saved result.

## Phase 7: Verify and report

Confirm the destination exists and the saved content matches the intended note. Check the saved bytes, not just the draft:

```bash
rg -n '["“”‘]' "<DESTINATION>"
rg -n '^ *>' "<DESTINATION>"
```

Trace every quoted phrase and blockquote to the actual source text. Include straight-single-quoted phrases in the manual review too; the pattern omits apostrophes deliberately. Strip inline code markup when comparing. If only a summary was available, use unquoted paraphrase; an exact citation title may still trace to verified metadata. A paraphrase is not a quotation. If a formatting hook changed a source-spelled token, restore the original spelling through the locked wrapper and protect it per §14; do not reinterpret corruption as permission to paraphrase a quote.

Re-read the Source section and compare author, title, venue, date and identifier spellings with the citation metadata. Preserve source spelling in citations and quotes; the user's locale governs your own prose only. Verify written wikilink targets and URLs after saving.

Report the saved file, its destination and any material source/access gaps. Include `Quote check: N quoted phrases, M block quotes, all traced` and the citation-check result only after performing those checks. Keep the note concise and descriptive; mark application inferences as inferences.

## Skill monitor

Follow [../_skill-monitor.md](../_skill-monitor.md) at completion.
