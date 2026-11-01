# Skill reference

[README](../README.md) · [Setup guide](getting-started.md)

Each skill is a workflow the agent follows. The command links below open its instructions, including arguments and prerequisites.

Use `/name` in a Claude Code full-vault installation, `/opencairn:name` with the [Claude Code plugin](getting-started.md#claude-code-plugin), and `$name` in Codex. `setup` and `setup-hooks` are Claude-only.

This feature map pairs each skill’s required outcome with a focused check. **Manual** checks require inspecting a run and its outputs; this page supplies no end-to-end automation. Missing or contradictory evidence fails the stated criterion. **Helper** links cover only the named fixture behaviour. Run their linked file from the repository root with pytest, for example `python3 -m pytest tests/test_pickup_scan.py -q`: exit 0 passes those assertions. This index records checks, not completed workflow verification.

## Requirements

| Installation | Workflows |
|---|---|
| No vault required | `audit`, `second-opinion`, `thinking-partner`, `shop`, `book-stay`. Shopping and accommodation workflows skip their vault extras when no vault is configured. |
| No vault required; external tools needed | `ocr`, `transcribe`, `transcribecloud`, `podcast-digest`. Check the linked instructions for the selected engine and input type. |
| Full vault | Session, planning, review, archiving and other vault workflows below need the NIPARAS structure, `VAULT_PATH` and shared runtime. `setup` establishes the initial configuration. |

Standalone workflows can still have dependencies: research needs web access, and additional review models need their own CLI or API access. OCR uses local extraction tools by default; transcription requires the selected engine and alignment tools locally, or a paid cloud GPU. Podcast digests use published transcripts when available. The plugin does not install these tools for you.

## Sessions and daily planning

| Claude Code | Codex | Required outcome | Check |
|---|---|---|---|
| [/pickup](../.claude/commands/pickup.md) | [$pickup](../codex/skills/pickup/SKILL.md) | Show active projects, or restore a named project or topic. | **Manual:** bare invocation lists active root projects; a named topic loads its latest matching session and hub when available. **Helper:** [TSV fixtures](../tests/test_pickup_scan.py) preserve empty time/project columns. |
| [/park](../.claude/commands/park.md) | [$park](../codex/skills/park/SKILL.md) | Save session outcomes, close open loops and update affected project notes. | **Manual:** saved log and task destinations match the work; full completion follows a passing verifier and clean independent review. **Helper:** [quick-path tests](../tests/test_park_quick_contract.py) cover instruction contracts and the Codex verifier wrapper only. |
| [/morning](../.claude/commands/morning.md) | [$morning](../codex/skills/morning/SKILL.md) | Review current work and reminders, then plan the day. | **Manual:** trace every actionable item in the user’s response to a saved destination and capture receipt; the day plan retains unfinished work and the rolling horizon. |
| [/afternoon](../.claude/commands/afternoon.md) | [$afternoon](../codex/skills/afternoon/SKILL.md) | Check progress and adjust the remaining day's priorities. | **Manual:** compare the recap with today’s tasks and sessions; a stale plan is labelled stale. Changed priorities land in their owning notes, with a receipt for each write. |
| [/goodnight](../.claude/commands/goodnight.md) | [$goodnight](../codex/skills/goodnight/SKILL.md) | Close the day, capture unfinished work and prepare the next day's plan. | **Manual:** unfinished task blocks survive carry-forward intact; collapsed days link to saved reports. Verification and independent review finish before transcript export and provenance. |
| [/hibernate](../.claude/commands/hibernate.md) | [$hibernate](../codex/skills/hibernate/SKILL.md) | Save project state and return priorities before an extended break. | **Manual:** compare the snapshot with active hubs and current task sources; open loops, deliberate deferrals and return priorities are retained, with no guessed dates or session links. |
| [/awaken](../.claude/commands/awaken.md) | [$awaken](../codex/skills/awaken/SKILL.md) | Restore a pre-break snapshot and reassess priorities on return. | **Manual:** the selected snapshot gains an awaken summary; due Tickler items are surfaced without being silently completed, and agreed next actions appear once in their task homes. |

## Project lifecycle

| Claude Code | Codex | Required outcome | Check |
|---|---|---|---|
| [/start-project](../.claude/commands/start-project.md) | [$start-project](../codex/skills/start-project/SKILL.md) | Create a project note with an objective and next actions. | **Manual:** read back the new note in the requested tier: stated done-state, bucket and empty Session History are present; any initiative link resolves and has the matching backlink. |
| [/set-project-status](../.claude/commands/set-project-status.md) | [$set-project-status](../codex/skills/set-project-status/SKILL.md) | Move a project between active, Cold and Backlog through Obsidian's link-healing move. | **Manual:** check source disappearance, destination contents, healed links and move receipt. **Helper:** [lifecycle fixtures](../tests/test_set_project_status.py) check dry-run non-mutation and moves using a simulated Obsidian transport. |
| [/complete-project](../.claude/commands/complete-project.md) | [$complete-project](../codex/skills/complete-project/SKILL.md) | Archive a completed, abandoned or superseded project and record the outcome. | **Manual:** every open task has a disposition; useful material reaches the agreed shelf with healed links, or pending moves are explicitly reported. No open task disappears into an archive. |

## Reviews and maintenance

| Claude Code | Codex | Required outcome | Check |
|---|---|---|---|
| [/weekly-review](../.claude/commands/weekly-review.md) | [$weekly-review](../codex/skills/weekly-review/SKILL.md) | Review accomplishments, project movement, open loops and priorities. | **Manual:** the report’s retrospective interval follows any previous review’s covered dates; cited reports resolve, agreed actions reach their task homes, and the context snapshot passes its staleness scrub. |
| [/weekly-hygiene](../.claude/commands/weekly-hygiene.md) | [$weekly-hygiene](../codex/skills/weekly-hygiene/SKILL.md) | Check vault structure, stale items, links and provenance records. | **Manual:** read the saved findings and routed tasks together; unresolved actions have verified destinations, and rerunning the same finding updates its existing task instead of duplicating it. |
| [/quarterly-review](../.claude/commands/quarterly-review.md) | [$quarterly-review](../codex/skills/quarterly-review/SKILL.md) | Reassess direction and choose priorities for the coming quarter. | **Manual:** the selected quarter matches the report and sources; prior commitments receive explicit outcomes, and next-quarter choices distinguish confirmed decisions from suggestions. |
| [/quarterly-hygiene](../.claude/commands/quarterly-hygiene.md) | [$quarterly-hygiene](../codex/skills/quarterly-hygiene/SKILL.md) | Review context, contacts, logs and skill-library maintenance. | **Manual:** the report identifies the weekly source and its freshness or absence, records deep-check outcomes, and separates applied edits, routed findings and proposals still awaiting approval. |
| [/oops](../.claude/commands/oops.md) | [$oops](../codex/skills/oops/SKILL.md) | Record a mistake, its correction and a reusable lesson. | **Manual:** compare the displayed failure-mode inventory with saved entries: each distinct cause is accounted for and its lesson specifies an observable trigger and corrective mechanism. |
| [/inbox-processor](../.claude/commands/inbox-processor.md) | [$inbox-processor](../codex/skills/inbox-processor/SKILL.md) | Sort captured items into their permanent vault locations. | **Manual:** reconcile the agreed item plan with source/destination files; deferred items remain, moves arrive, and deletions have separate explicit approval. |

## Research, decisions and review

| Claude Code | Codex | Required outcome | Check |
|---|---|---|---|
| [/research-assistant](../.claude/commands/research-assistant.md) | [$research-assistant](../codex/skills/research-assistant/SKILL.md) | Search and synthesise existing vault knowledge before external research. | **Manual:** open each cited note/section and trace the synthesis to it; the answer separates direct evidence, related context and gaps, with vault searching preceding external research. |
| [/thinking-partner](../.claude/commands/thinking-partner.md) | [$thinking-partner](../codex/skills/thinking-partner/SKILL.md) | Explore a problem through questions and challenge its assumptions. | **Manual:** a bare invocation asks one opener and waits; topic discussion probes assumptions, with no edits or implementation plan unless explicitly requested. |
| [/second-opinion](../.claude/commands/second-opinion.md) | [$second-opinion](../codex/skills/second-opinion/SKILL.md) | Get independent review of work or decisions, with follow-up rounds if needed. | **Manual:** compare the synthesis with retained reviewer outputs: findings are attributed, disagreement and unavailable seats are explicit, and target hashes are reconciled against the pre-review baseline. |
| [/audit](../.claude/commands/audit.md) | [$audit](../codex/skills/audit/SKILL.md) | Evaluate an implementation from problem framing through execution. | **Manual:** retained reports address the specified audit layers with evidence; the synthesis identifies actual reviewers and any fallback, and resolves findings against the target, including whether the approach serves the requester’s goal. |
| [/shop](../.claude/commands/shop.md) | [$shop](../codex/skills/shop/SKILL.md) | Clarify a purchase need, research options and recommend a decision. | **Manual:** compare the recommendation with stated hard requirements and current sources; compatibility, prices and trade-offs are evidenced, and an exact requested model stays exact. |
| [/book-stay](../.claude/commands/book-stay.md) | [$book-stay](../codex/skills/book-stay/SKILL.md) | Compare accommodation, verify rates and hand off booking. | **Manual:** compare verified rates for the requested dates and inclusions; the handoff states total and cancellation terms. Booking fields stay empty until confirmation is received. |
| [/landscape-scan](../.claude/commands/landscape-scan.md) | [$landscape-scan](../codex/skills/landscape-scan/SKILL.md) | Scan and digest curated sources for a selected topic. | **Manual:** the saved report identifies its profile and acquisition gaps; comparative claims about local skills cite source read that run, and executed actions are distinguished from proposed trials. |

## Prioritisation

| Claude Code | Codex | Required outcome | Check |
|---|---|---|---|
| [/longpoles](../.claude/commands/longpoles.md) | [$longpoles](../codex/skills/longpoles/SKILL.md) | Find `[LP]` tasks that block other work. | **Manual:** include live, completed, unmarked and example hits in a check corpus; the report preserves source status, excludes examples/archive records and counts unresolved context only under Undetermined. |
| [/cornerstones](../.claude/commands/cornerstones.md) | [$cornerstones](../codex/skills/cornerstones/SKILL.md) | Find high-value foundational tasks marked `[CS]`. | **Manual:** inspect open, done, blocked and uncertain source items; statuses and totals agree, while fenced examples, tag documentation and frozen copies are excluded. |
| [/guillotines](../.claude/commands/guillotines.md) | [$guillotines](../codex/skills/guillotines/SKILL.md) | Find `[GT]` deadlines where missing the date forecloses an option. | **Manual:** compare dates and ordering with source items; only open resolved deadlines enter the timeline. Done, undated and ambiguous items remain separate; failed date parses produce no countdown. |

## Writing, media and reference material

| Claude Code | Codex | Required outcome | Check |
|---|---|---|---|
| [/de-ai-ify](../.claude/commands/de-ai-ify.md) | [$de-ai-ify](../codex/skills/de-ai-ify/SKILL.md) | Edit a draft to match your voice and remove formulaic AI phrasing. | **Manual:** compare input and rewrite against the chosen voice/register: ideas remain intact, formulaic phrasing is removed, and the before/after makes meaning changes visible. |
| [/reply](../.claude/commands/reply.md) | [$reply](../codex/skills/reply/SKILL.md) | Draft a reply using your writing preferences and contact context. | **Manual:** read back the saved draft: requested points and factual-claim flags survive the voice pass; a re-draft replaces its existing section. “Just inline” creates no scratchpad entry. |
| [/ocr](../.claude/commands/ocr.md) | [$ocr](../codex/skills/ocr/SKILL.md) | Extract and structure text from screenshots. | **Manual:** compare extracted text with source screenshots and the requested content template; chat output preserves order and sender attribution, and overlap removal matches the reported duplicate count. |
| [/transcribe](../.claude/commands/transcribe.md) | [$transcribe](../codex/skills/transcribe/SKILL.md) | Transcribe audio or YouTube videos locally with Parakeet GGUF for English and WhisperX fallback. | **Manual:** compare representative audio with the transcript and alignment data; timestamps and speaker labels follow the selected options, and unaligned nonempty segments remain with explicit uncertainty. |
| [/transcribecloud](../.claude/commands/transcribecloud.md) | [$transcribecloud](../codex/skills/transcribecloud/SKILL.md) | Transcribe audio or video on a rented RunPod GPU. | **Manual:** reconcile source files with locally validated results and sample audio for omissions; verify deletion of any job-created pod, or report its ID and unresolved billing state. |
| [/podcast-digest](../.claude/commands/podcast-digest.md) | [$podcast-digest](../codex/skills/podcast-digest/SKILL.md) | Summarise a podcast or talk from a published transcript or transcription. | **Manual:** trace cruxes and major claims to the transcript; report acquisition tier and gaps. Timestamps and speaker names have evidence; missing ones are not invented. |
| [/archive-transcript](../.claude/commands/archive-transcript.md) | [$archive-transcript](../codex/skills/archive-transcript/SKILL.md) | Save a published transcript with a synthesis header and verbatim body. | **Manual:** run the source contract’s saved-body byte comparison against the extracted body; any difference fails. The header identifies its metadata basis and the canonical-URL duplicate check is recorded. |
| [/archive-article](../.claude/commands/archive-article.md) | [$archive-article](../codex/skills/archive-article/SKILL.md) | Save an article or paper as a reference note with synthesis and verified citations. | **Manual:** check the saved note’s inline and block quotations against fetched text, citation spellings against metadata, and wikilinks against existing notes; expose source gaps instead of filling them. |
| [/map-day](../.claude/commands/map-day.md) | [$map-day](../codex/skills/map-day/SKILL.md) | Turn an itinerary into an Organic Maps KML and a Markdown day-sheet. | **Manual:** reconcile input stops with KML pins, day-sheet order and unresolved-stop diagnostics; default ordering preserves fixed-anchor time order. Check warnings even on exit 0; distance ordering does not prove travel-time feasibility. |

## Provenance

| Claude Code | Codex | Required outcome | Check |
|---|---|---|---|
| [/provenance](../.claude/commands/provenance.md) | [$provenance](../codex/skills/provenance/SKILL.md) | Request hashing and timestamp proofs at day-end, or attest a final work product immediately. | **Manual:** inspect the pending flag and any immediate attestation: recorded digest matches its retained snapshot; pending/confirmed proof states have matching proof files. A flag alone is not a timestamp proof. |
| [/verify-provenance](../.claude/commands/verify-provenance.md) | [$verify-provenance](../codex/skills/verify-provenance/SKILL.md) | **Deprecated:** redirects to the provenance check in `weekly-hygiene`. | **Manual:** the redirect loads weekly-hygiene’s own-harness instructions, resolves the vault, then executes its provenance check; its reported state comes from proof/hash checks, not the redirect itself. |

## Setup and updates

| Claude Code | Codex | Required outcome | Check |
|---|---|---|---|
| [/setup](../.claude/commands/setup.md) | Not available | Check prerequisites and personalise the vault through an interview. | **Manual, Claude only:** rerun the environment checks and read back personalised fields; saved values match interview answers, untouched content remains, and missing prerequisites are reported. |
| [/setup-hooks](../.claude/commands/setup-hooks.md) | Not available | Configure optional skill-edit and park hooks; requires `jq`. | **Manual, Claude only:** compare each wiring script’s output with settings: changed runs supply the reported backup; repeated setup reports no change. When enabled, trigger a selected hook to establish that it fires. |
| [/update](../.claude/commands/update.md) | [$update](../codex/skills/update/SKILL.md) | Review and apply upstream infrastructure changes to a full vault checkout. | **Manual:** accepted replacements match reviewed diffs; rejected/local-only files remain. A requested signed tag verifies before apply; repository and live Codex copy results are reported separately. |
| [/migrate](../.claude/commands/migrate.md) | [$migrate](../codex/skills/migrate/SKILL.md) | Apply pending migrations for supported OpenCairn vault layouts. | **Manual:** the canonical Doctor checks agree with the actual archive topology and ledger; only verified complete state unblocks workflows, while deferred/declined/blocked components remain explicit. |

Codex `update` and `migrate` are adapters to the canonical procedures in the full vault checkout; a skills-only installation cannot run them. For Codex installation and personalisation, use the [manual setup instructions](getting-started.md#codex-cli).

## Aliases

| Claude Code | Codex | Required outcome | Check |
|---|---|---|---|
| [/checkpoint](../.claude/commands/checkpoint.md) | [$checkpoint](../codex/skills/checkpoint/SKILL.md) | Invoke `park`. | **Manual:** confirm the same-harness `park` workflow runs; the Codex adapter must also forward supplied arguments. Apply the `park` checks above. |
| [/regroup](../.claude/commands/regroup.md) | [$regroup](../codex/skills/regroup/SKILL.md) | Invoke `afternoon`. | **Manual:** confirm the same-harness `afternoon` workflow runs; the Codex adapter must also forward supplied arguments. Apply the `afternoon` checks above. |
| [/shutdown](../.claude/commands/shutdown.md) | [$shutdown](../codex/skills/shutdown/SKILL.md) | Invoke `goodnight`. | **Manual:** confirm the same-harness `goodnight` workflow runs; the Codex adapter must also forward supplied arguments. Apply the `goodnight` checks above. |
