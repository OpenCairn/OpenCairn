# Step 12d Propagation Protocol

This file is the protocol the propagation sub-agent invoked by /park Step 12d must execute. The dispatching session passes enumerated identifiers and the vault path as inputs; the protocol below is the same on every despatch.

**You are the propagation sub-agent.** /park has enumerated identifier changes from the session just completed (renames, status flips, replacements, deletions, new named state). Your job: trace each identifier across the vault and update stale cross-references. The dispatching session has embedded the enumerated identifiers and the vault path in its prompt to you.

## Protocol

**1. Path expansion for file rename/move/delete identifiers.** For any enumerated identifier that is a file rename/move/delete, also grep for plausible full-path forms — old absolute path, old vault-relative path, and the bare filename without extension. Plain-text path references inside non-link contexts (e.g. `**Source:** /path/to/file.ext` in transcripts, embedded YAML, fenced code blocks) are NOT surfaced by structural link-integrity queries — only grep catches them. Iterate each form as a separate grep call.

**2. Archive-exclusion glob.** Exclude `**/06 Archive/**` from all grep passes — those are historical records, not stale cross-references.

**3. Tool guidance.** Use `rg --type md` (ripgrep, respects `.gitignore`, skips `.git/` auto-save). Do not use `grep -r` — it crawls `.git/` and takes minutes on long-lived vaults.

**4. No regex alternation from memory when N>3.** If more than three identifiers, iterate each as a separate grep call. Typed-from-memory alternation silently drops entries.

**5. For file-path identifier changes (rename, move, delete) — structural-link-integrity post-check.** After the per-identifier grep pass, run the vault's structural link-integrity query as a post-check (e.g. `obsidian unresolved` for an Obsidian vault; `git grep` + LSP find-references for code repos; broken-link reports for wikis). The grep catches plain-text path references; the structural query catches wikilink/symlink integrity. Both are needed — neither alone is sufficient. Watch for basename collisions: if `new-name.md` and `old-name.md` share a basename with some unrelated file, structural queries may resolve a `[[old-name]]` link to the wrong file rather than flagging unresolved. Flag any ambiguous basename collisions in the report.

**6. Authority.** For each grep hit, read the file and assess: stale cross-reference → update via Edit; historical record of what was actually said/sent → leave; different context that happens to share the identifier → leave. Display grep results in the report (output proves the grep ran).

## Report format expected back

Per-identifier:
- `[identifier]: N files updated` with file list + brief change description, OR
- `[identifier]: no living refs found`

Plus structural-query results if file moves were in scope. Plus any basename-collision flags.

## Why this file exists

The dispatching session previously reconstructed this protocol from inline park.md prose every time, costing 15-25s of token-gen per /park run. The defensive content (path-expansion, no-regex-alternation, structural-link-integrity post-check, etc.) is unchanged — only the *location* of the content moved. Per the defensive-mechanism guardrail in plan-v4: content stays, assembly mechanism becomes mechanical.

Sibling file: `park-step14-audit-task-brief.md`.
