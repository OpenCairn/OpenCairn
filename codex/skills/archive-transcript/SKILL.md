---
name: archive-transcript
description: Archive published podcast or talk transcripts into the vault with a verbatim body and a short metadata-based synthesis header.
---

# Archive Transcript

Archive one or more published transcripts. Preserve the body exactly as extracted and build a short topic summary from the published description and section outline. Do not load the whole transcript into model context to write its header. For transcription from audio, use `$transcribe` or `$transcribecloud`; for a substantive episode digest, use `$podcast-digest`.

## Phase 0: Preflight

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

Stop on failure; never guess the vault path. Read [../_shared-rules.md](../_shared-rules.md) (core, including §5), then [../_shared-rules-content.md](../_shared-rules-content.md) §§14–15 and 26, and the vault's search-routing document when available. Paths to supporting files are relative to this skill directory. Every vault write, including creation, body append, header correction and hub integration, uses `locked-edit.sh`.

Run §15's prerequisites (`curl`, `pandoc`, `python3` with `bs4`/`lxml`) before fetching. Missing tooling needs a specific prerequisite report; an audio transcription fallback requires an available transcription skill and the user's choice, including paid-cloud authorisation where relevant.

Establish any active formatting hook's actual matcher before relying on a write route. Do not assume Claude's `Write`/`Edit` hooks describe Codex's hooks. Where hooks exist, §14's control test must show whether shell/locked writes preserve source bytes. If the chosen route rewrites the body, use an authorised path exclusion or stop; do not silently change global hooks. A later edit from another harness can still rewrite a verbatim note, so stage and verify the complete note before saving it.

## Phase 1: Resolve sources

Use URLs the user supplied. If asked to find appearances of a person or show, search first, verify candidate URLs and present the proposed episode list before fetching the batch. Record only verified show, host, guest, publication date and canonical URL. Do not infer identities from filenames or garbled transcript speaker labels.

## Phase 2: Fetch into files

Use the shared §15 published-transcript extractor once per episode. Retain its printed `BODY=` path and the exact source URL; its per-URL path can be reconstructed across exec calls. Shell variables from an earlier call do not persist.

The extractor owns HTML cleanup, Markdown conversion, word/leak checks and metadata extraction. Validate the result as sustained episode-specific speech, not show notes, a summary or a paywalled excerpt. Probe structure, word counts and bounded head/tail snippets through the shell; do not print the full body into context.

Retain the published description and section outline for the header. Apply §15's Names and speakers procedure before using identities: resolve its page/transcript boundary, compare name tokens across the appropriate regions, and use the timestamped chapter list when identifying segments. A failed boundary split means uncertain attribution, not evidence of absent metadata. Provenance starts as `published transcript (provenance unverified)`; a source disclaimer may establish auto-generation, and only a positive editing claim establishes human editing.

If a static extractor fails on a rendered page, try the available §26 fetch route while preserving exact text on disk. A summarised tool response cannot supply a verbatim body. If no usable published transcript remains, explain the gap and offer `$transcribe` or `$transcribecloud` after reading the selected skill. Do not silently replace published text with ASR.

## Phase 3: Compose and save

1. **Choose the destination.** Honour a supplied path. Otherwise inspect existing transcript/podcast folders and propose a fitting home. Ask if the location is unclear; do not invent a folder taxonomy. Retain the exact folder, destination-note and body-file paths across calls.

2. **Check duplicates.** Search the canonical URL as a literal string across the vault's Markdown notes, then title/date in the destination and related clusters:

   ```bash
   rg -l -F --hidden --no-ignore -g '*.md' -g '!**/.git/**' \
     -- "<CANONICAL_URL>" "$VAULT_PATH"
   ```

   Exit 1 is a scoped no-match result; another error is a failed search. Inspect candidate notes through bounded header/source probes: a URL mention in a hub is not an archived transcript. For an existing archive, ask update or skip unless already specified. Check filename collisions too. An update rebuilds the header and body in scratch, then replaces the existing file under the lock; never use raw `mv` over a vault note.

3. **Match conventions.** Enumerate filenames and read only bounded headers of 2–3 actual transcript notes where available. Prefer `type: podcast-transcript` examples over digests or unrelated notes; do not glob-print every note's header. Follow the usual filename and frontmatter. If no convention exists, use `<Speaker> - <Title> (<Show>, <Year>).md` with verified fields only, omitting unavailable components. Suggested metadata: title, show, host, guest, date, source, captured, type. `captured` is this run's date from `date`, not the episode publication date.

4. **Stage the header outside the vault.** State that its topic summary and section-derived key points are based on the published description and outline, not a full transcript reading. Relate those topics to the user's purpose only where supported; do not invent an episode thesis. End with `## Full transcript` and a provenance line identifying the source and extraction changes, such as removed timestamp links. Preserve source names and spelling.

5. **Assemble from disk.** Keep the body out of context:

   ```bash
   { cat "<HEADER_FILE>"; printf '\n'; cat "<BODY_FILE>"; } > "<STAGED_NOTE>"
   ```

   All staging paths are outside the vault. Use distinct scratch paths per episode/run. For a new destination after the collision check:

   ```bash
   "$VAULT_PATH/.claude/scripts/locked-edit.sh" "<DESTINATION_NOTE>" --append < "<STAGED_NOTE>"
   ```

   For an authorised update, prefer `--replace-whole <expected-sha256>` if that mode is advertised by the installed wrapper: hash the current destination, supply the rebuilt bytes on stdin, and re-read/rebuild on a stale-snapshot refusal. Otherwise use its supported literal `--replace` mode with the exact old content. An error never permits a lockless fallback. Avoid whole-note editor rewrites after the body lands; corrections rebuild the staged note and repeat the locked update and byte check.

## Phase 4: Integrate, verify and report

Link the transcript from an existing relevant person/dossier or topic hub where that fits the user's requested archive and the vault's conventions. Read the target first, preserve existing prose and quotes, and apply a small locked edit. Verify all wikilink targets. Do not create a new person or hub merely to add a backlink.

Verify the saved result through the shell:

```bash
wc -w "<BODY_FILE>" "<DESTINATION_NOTE>"
tail -n 5 "<DESTINATION_NOTE>"
cmp <(tail -c "$(wc -c < "<BODY_FILE>")" "<DESTINATION_NOTE>") "<BODY_FILE>"
```

Require a non-empty validated body first. `cmp` exit 0 proves that the saved body is byte-identical; word counts or a plausible tail alone do not. Also compare the saved header with the staged header. On a mismatch, identify the write/hook problem before rebuilding; report failure until the comparison passes.

Report file links, final word counts, any transcription fallbacks and material fidelity or attribution caveats. The header follows the user's locale; the body retains its source wording, grammar and spelling.

## Skill monitor

Follow [../_skill-monitor.md](../_skill-monitor.md) at completion.
