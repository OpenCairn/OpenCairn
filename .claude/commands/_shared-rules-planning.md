# Shared Rules — Planning

Read only the numbered sections needed for the current operation. Core rules and the global section directory are in [_shared-rules.md](_shared-rules.md), in this same directory. Section numbers retain their original meaning; resolve a cross-file `§N` there and read its procedure before using it. These are instructions shared by skills, not an independently invoked workflow.

---

## 2. Project Linking Rules

When a session or task links to a project context:

- **Finite work (in flight)** → link to `03 Projects/[name].md` (or `03 Projects/Backlog/[name].md`)
- **Ongoing area work** → link to `04 Areas/[path]/[name].md`
- **Shipped one-shot work** (published blog post, completed migration, resolved bug, anything finite that's now done with no ongoing tracking need) → link to an *existing* area hub that naturally groups related work. **Do not create a project file retroactively.** The "finite work → project file" rule above is calibrated for in-flight finite work where a project file earns its cost by hosting the task queue; once the work ships, the task queue is empty and a retroactive project file is noise. Example: a published post on your blog links to `[[04 Areas/Blog/Blog]]`, not a newly-created post-specific project file.
- **Operational/meta work with no natural project or area home** (e.g. /morning, /goodnight, general sysadmin, security hygiene, vault maintenance) → `Project: None (operational <scope>)` — e.g. `None (operational /morning)`, `None (operational tech-infra)`. Don't reach for a loosely-related project to fill the slot; `None` is the correct answer.
- **Never link to:** Resources, Archive, or 07 System files (these are references and meta, not project/area homes).
- **No canonical home and work is still in flight?** Create a project or area file. Small one-off items may simply live in This Week or the Tickler with no home doc.
- **Working in Resources?** That's a signal it should graduate to an Area
- **Why:** Consistent project links enable reliable pickup grouping.

---

## 3. Item Linking Convention

Every actionable item in a day section or planning document should link to its project/area context where one exists:

- Project doc exists → `→ [[03 Projects/Project Name]]`
- Area doc exists → `→ [[04 Areas/path/doc]]`
- Standalone/generic items (no project context) → no link

When moving items that already have project/area links, preserve them. Replace session log links (`→ [[06 Archive/OpenCairn/Session Logs/...]]`) with project/area links — session context is low-value once the item is in a planning doc.

**Operational continuation links are an exception.** Preserve an unfinished task’s exact review/session links when they carry state needed to continue the work. Keep them through carry-forward and Tickler transfers; a project link may accompany them but must not replace them. This exception applies to every consumer of this linking convention.

---

## 4. Tickler SSOT Transfer

Tickler is a time-deferred queue, not a persistent SSOT. When items are pulled from Tickler into a planning document (This Week.md, a project page, etc.), **the planning document becomes SSOT** for those items. Delete the Tickler copy immediately to prevent duplicate checkboxes across the vault. The Tickler's job is done once the item surfaces and lands in a plan.

When migrating Tickler items:
- Preserve existing project/area links (`→ [[03 Projects/...]]`, `→ [[04 Areas/...]]`)
- Replace session-log-only links with the relevant project/area link
- Add links to bare items per the Item Linking Convention (Section 3)

---

## 9. This Week.md Rolling Window Maintenance

**Task carry-forward:** /goodnight Step 9 owns task-retention, routing and block-preservation rules. Execute that step with the source and destination sections specified below; do not maintain another routing policy here.

This procedure keeps the rolling 7-day window current. It runs during `/morning` (step 6) and `/goodnight` (step 11). If This Week.md doesn't exist, skip entirely.

**Write mechanism (F1):** `This Week.md` is a shared planning file — every trim/extend/populate mutation below goes through `locked-edit.sh`, not the Edit tool (see §5). Use `--replace`/`--replace-all` to delete or rewrite day sections. `--append` adds at EOF, so it is valid for new day sections **only when the file has no trailing non-day content**; if a `---` / `## Refs` / other trailing section exists, use `--replace` on the trailing boundary block instead (per the placement rule below).

### Trim old day sections

Delete any day sections whose date is more than 3 calendar days before today. Past days are already archived in Daily Reports — keeping them past 3 days adds clutter without value.

1. Parse each `## ` heading for a date (e.g. `## ☀️ Fri 6 Mar` → 6 Mar, `## Mon 9 Mar` → 9 Mar). Skip headings that aren't day sections (e.g. `## Refs`).
2. For each day section, compute `today_date - section_date`. If > 3 calendar days, execute /goodnight Step 9 with source = that section and destination = today’s section. Only after its open tasks are safely carried forward, delete the old day section. Completed items remain in their Daily Report.
3. Keep the 3 most recent past days for quick reference. Today and future days are never trimmed.

### Extend the window

Ensure day sections exist for today + 6 calendar days ahead (7 total including today). Normal window: 3 past + today + 6 future = 10 sections; preserve additional populated future days.

1. Run `date -d "+N days" +"%A %d %b"` for each missing day (N = 0 to 6, including today)
2. Add new day sections after the last existing day, before `---` / Refs / other trailing sections
3. Remove only empty day sections beyond the 6-day window. Preserve populated future days and their dates; do not delete or offload their open tasks to enforce the window size.
4. Format for days with no content: `## [Day] [DD] [Mon]` — just the heading
5. Update the file heading date range — this is a **required, emitted check**, not a silent edit. See **Update the heading** below.

### Populate new days from Tickler

For each newly created day section, convert to YYYY-MM-DD format and check Tickler.md for a matching `## YYYY-MM-DD` date header. Move any unchecked items from that Tickler section into the new day section and delete from Tickler (per Tickler SSOT Transfer rules in Section 4).

**This move is gated on the date and nothing else.** Extending the window into a date is what makes that date's items due, so a section left empty because the window "looks full" is a day section asserting nothing is due while the Tickler still holds the items — the SSOT split this section exists to close. Move them all.

### Update the heading

Update `# This Week — [start] – [new end] [YYYY]` so the range equals the earliest and latest day-section dates currently in the file.

**⛔ Required output — emit the check.** Whenever the window changes (a section added or trimmed), confirm the title against the actual first/last day sections and print the result. This is the load-bearing mechanism: the instruction to update the heading has always existed, so what recurs is *skipping it without noticing*, not not knowing to. A title edit with no emitted check is the failure signature. Format:

```
Window check: title "[start] – [end]" = sections [first day] … [last day] ✓
```

If the title and the first/last day sections disagree, the window edit is incomplete — fix the title before finishing the procedure.

---

## 18. Deadline Tokens Force a Dated Surface

Canonical rule for every skill that routes open items to a destination — `/park` Step 7, `/goodnight` Step 9. Those skills point here and carry no copy to drift.

**The rule.** If an item's text contains a deadline, cut-off, expiry, renewal, or window-close token, its route MUST terminate in a **dated surface**: a specific day section when the date falls inside the rolling window, otherwise the Tickler (via `write-tickler.sh`).

**An undated destination does not discharge such an item**, however canonical that destination is. A project doc, an area hub, an undated notes list — each records *what* to do and never *when it stops being possible*. The undated branch of a routing table exists for items with genuinely no date; a deadline token means the item has one **even when it isn't written as a calendar date**. Derive it (`date -d`), don't route past it.

**The failure surface is caller-specific — name yours.** Each routing skill has a different undated sink, and the check must bind to that skill's own sink: for `/park` Step 7 the disallowed sinks are undated task homes and Whimsy. `/goodnight` Step 9 has no undated sink: existing open tasks remain in This Week under §9. A caller adopting this rule states which of its destinations is the disallowed one, because "route to a dated surface" is unfalsifiable without naming what that excludes.

**Checkable:** any routed item whose text carries a deadline token must land under a dated heading, and the routing summary must name that dated target.

---
