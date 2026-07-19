---
name: book-stay
description: Choose and book a hotel (or stay) — quiz preferences, generate shortlist, verify rates, hand off booking, fan out references across the vault.
---

# Book Stay

Pipeline for choosing and booking a hotel for a trip leg. **One pipeline run and one accommodation doc per leg** — for a multi-city trip, split into legs first and run Steps 1-11 per leg (record the split rationale in the doc template's Multi-leg section), updating the trip hub once at the end.

**Prerequisites:** web search (candidate research + live FX rates) and the AskUserQuestion quiz tool. The vault doc template lives at `{VAULT}/07 System/Templates/Accommodation Decision.md`. **No vault?** Skip Step 1's context-load and Step 11 entirely (Step 1's lead-time check and currency step still run) — the quiz → research → verify → handoff core works anywhere.

**Scope:** hotels and short stays. Restaurants and other venue bookings are out of scope.

### 0. Resolve Vault Path (vault installs only)

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

If error on a vault install, abort (no silent fallback — `_shared-rules.md` §1). If the error is just that no vault is configured (`VAULT_PATH` unset on a vault-less install), don't abort — run in no-vault mode per the Prerequisites note. Read `_shared-rules.md` from this skill's own commands directory and apply its rules throughout — §5 (locked edits) governs every shared-planning-file write below. All paths use `{VAULT}` as a placeholder — substitute the resolved vault path.

## Inputs

- City + dates + context (purpose, solo/companion, budget tier hint)
- Currently-loaded vault state (Works in Progress, the relevant project hub, any existing accommodation doc for the city)

## Steps

### 1. Context-load + lead-time check

- Read `01 Now/Works in Progress.md`, the travel project hub if one exists, and any existing accommodation doc for the city. On a fresh vault with none of these, note it and continue — don't invent structure.
- **Don't re-research what's already in the vault — refine instead.**
- **Stale check:** if the existing doc has a SUPERSEDED banner or is >1 month old, treat it as historical context only. If the user has flagged a context shift since the doc was written (e.g. "we used to be planning A but now it's B"), explicitly re-open rather than refining.
- **Compute booking lead time** (`check-in date − today`; run `date` for today — never assume it). Warn the user if it's <7 days: most chain-hotel package discounts require 7-21 days advance booking, so the realistic discount ceiling at short lead time is ~5-10% via a loyalty member rate, not the 18-25% a package can reach. **But distinguish chain-loyalty packages (lead-time-gated) from OTA promo discounts (not).** OTA promotions ("intro offer", "mobile exclusive") and individual property opening-discounts often apply at any lead time — don't tell the user to expect zero discounts last-minute. Set expectations on chain packages specifically.
- **Establish the user's home currency** (locale in CLAUDE.md, or ask once in plain conversation before the quiz — the frame call is already at the 4-question cap) — all totals present in it.
- **Surface prior decisions** from the loaded context. For each upcoming quiz question, check the existing accommodation doc for an answer. If found, state it as the working assumption ("the prior doc recommended X — do you want to change this?") rather than re-asking from scratch.

### 2. Quiz via AskUserQuestion (2 calls if needed; ≤4 questions per call)

Standard set, **skip what context already answers**:

**Frame call:**
- **Dates** — check-in, check-out (note any flexibility)
- **Neighbourhood/anchor** — what should the location be anchored on: the user's own base of operations (work, event, exploration), proximity to a specific venue or person, or "no preference, optimise on tier + requirements"
- **Tier** — give 3 concrete tier brackets with example properties
- **Primary purpose constraint** — work-event AV, family setup, late-arrival logistics, etc. (3 explicit options, not compound prose)

**Execution call:**
- **Hard requirements** — multiSelect collects the set; the quiz tool can't capture order, so follow up with one conversational line asking the user to rank their selections firmest → negotiable. For "quiet," ask about the *type* of noise: continuous vs intermittent, intra-property vs street, mitigated vs un-mitigated by earplugs.
- **Booking channel + loyalty** — which channels they have a preference for, active loyalty status worth using
- **Cancellation flexibility** — free-cancel premium vs non-refundable saving

### 3. Sequencing branch — external-anchor first?

If the trip involves a daily-use external anchor (office, conference venue, coworking, campus, gym, daily class) that's NOT the hotel itself, AND the duration is ≥3 days:
- **Research the anchor first** (location, hours, daily/weekly pricing, amenities)
- **Derive the hotel search neighbourhood from the anchor's location**
- **Then research hotels** within walking distance

For shorter stays or hotel-as-the-base trips, skip this branch.

### 4. Research

Generate 6-8 candidates → filter to 3 finalists.

- **Search via the region-dominant OTA first** (e.g. Trip.com in mainland China, Booking.com in most Western markets), with a second OTA as cross-check. Direct-channel price comparison for chain finalists happens in Step 6.
- Filter on the firmest hard requirement + recent-review red flags (thin walls, slow wifi, construction, lift noise).
- **Apply the noise-tier heuristic if "quiet" is the firmest requirement:** intra-property noise (slamming doors, trolleys, neighbour babies) correlates with **hotel tier and brand build quality**, not neighbourhood refinement. **Nice hotel in busy area > busy hotel in nice area.** Don't default to "quiet area = quiet hotel" — check brand build standards instead.
- **Geography verification before claiming distances.** When a recommendation pivots on walking/driving distance to a specific landmark (cafe, museum, office, station), do NOT generate the distance from prose-grouping inferences ("user mentioned X and Y in the same paragraph, so they must be near each other"). Either web-search the landmark first to verify its actual location, or explicitly ask the user "where is X relative to Y?" Distance claims are load-bearing for hotel-pocket recommendations and confabulating them wastes the user's time and erodes trust. Acceptable form: "I don't know exactly where X is — can you confirm?" Unacceptable form: confidently asserting "10 min taxi from Y to X" without verification.

### 5. User-assisted price verification of finalists

For each finalist, establish: room type, sqm, current rate, breakfast inclusion, cancellation deadline, home-currency total. **Division of labour — the agent verifies the FX rate, the user verifies the prices:**

- Claude generates the qualitative shortlist with reasoning + estimated price ranges + property reputation
- **User pulls live prices on their phone app** (OTA apps / hotel direct) — 5 min, much more reliable than the agent fighting bot-resistant, JS-heavy travel SPAs
- User pastes back screenshots or numbers
- **For chain finalists, bundle the Step 6 direct-channel check into the same phone round-trip** — final re-ranking waits until both OTA and direct prices are in, so the user isn't asked to redo the comparison
- Claude converts using a *live* FX rate (never a remembered conversion heuristic) and re-ranks against the live data

**OTA listing-quality varies — treat single-OTA amenity gaps as listing-gap, not ground truth.** The same property's listing across OTAs can disagree on languages spoken, breakfast inclusion, room amenities, etc. Before flagging a missing amenity as a con of a candidate, cross-check at least one other OTA or recent reviews. Don't downgrade a candidate based on a single listing's silence.

### 6. Direct-channel check (for chain finalists — run within Step 5's round-trip, before final re-ranking)

For chain hotels with loyalty programs, **always have the user check the property's official site direct** before comparing OTA prices:
- Loyalty member rates often beat OTA prices
- Package discounts (advance-purchase bundles, bed-and-breakfast packages) are usually direct-only
- On-site benefits (lounge access, dining discounts, complimentary experiences) are direct-only
- Loyalty point earning + status credit happen properly on direct bookings

Phone bookings to the property count as "direct" and unlock the same benefits — useful if the website doesn't show all rates.

### 7. Fallback if no candidate clears the bar

Present the gap (which constraint failed: tier? hard requirement? neighbourhood?) and ask which to relax — preference order: **tier → neighbourhood → hard requirements last.**

### 8. Decision presentation

- Compact markdown comparison table with **separate per-night (incl. tax) and stay-total columns** (don't collapse "cheapest" into one number — it's multidimensional)
- Recommendation with explicit reasoning
- Explicit "Ruled out" lines for transparency
- For load-bearing facts (specific discount percentages, feature claims), **include verbatim source quotes** in the response, not just parsed numbers. Verbatim quotes protect against quick-read errors.
- **Verify, don't infer.** If a feature is load-bearing for the decision (e.g. "private meeting room with door"), actually verify it before claiming it. Marketing copy / testimonials are *suggestive*, not *verified*.

### 9. Loyalty-program advice (if user has status / points)

These are heuristics, not rules — program terms differ and change, so verify the current program-specific rule (web search) before applying any of them to a specific chain.

- Distinguish **status points** (tier qualification) from **award points** (redemption currency). Don't conflate the balances.
- For status-progression-conscious users: **earned points on cash stays beat redeemed points on award stays**. Award stays don't earn status credit at most loyalty programs, so redeeming points stalls tier qualification. Pay cash, earn the points.
- Only redeem points if redemption value-per-point exceeds 1.5-2x the cash equivalent (typically only at flagship suite tiers, not at brand-tier properties).
- Don't recommend buying points to bridge a tier gap if the upcoming stay would bridge it organically.

### 10. Booking handoff

User executes the actual purchase. Output format:

```
Channel: <OTA name / hotel direct>
URL or deeplink: <link>
Expected total: <home currency>
Free-cancel deadline: <date>
Special requests text: "<paste-ready text>"
```

Pre-commit checklist for the user:
- Loyalty member number attached (verify before clicking Confirm)
- Card matches what they'll bring to check-in (physical card or Apple/Google Pay)
- Email confirmation will arrive at a checkable address
- Cancellation deadline noted in their calendar

User pastes confirmation # back; agent captures it.

### 11. Reference graph fan-out (vault installs only)

**Update what exists; the only file to create is the accommodation doc itself.** Don't invent hubs, planning files, or reference files on a fresh vault.

- The accommodation doc for this trip leg (mark booked, confirmation #, booking URL, free-cancel deadline). If creating from scratch, copy `{VAULT}/07 System/Templates/Accommodation Decision.md` to the trip's project folder as `<City> Accommodation - <date range>.md` (hyphen, not em dash — em dashes in filenames are shell-hostile), and populate it from Steps 2-8's research per the template's own instructions (replace placeholders, delete inapplicable sections). If no trip project folder exists, ask the user where to put it — don't invent structure.
- The trip's timeline / overview docs, if the trip has them.
- `01 Now/Works in Progress.md` (relevant project entries — usually 2: the travel project + the project that drove the trip). When updating a WIP `Last:` field, replace the prior value outright — do not chain "Earlier [date]..." blocks (per `/park`'s Last-field cap rule: prior Last content is preserved in the session-log archive; chaining it inline is the accretion anti-pattern).
- `01 Now/This Week.md`, if it exists (mark task done, update the Status banner if the booking changes it)
- Any project-specific doc that referenced "where am I sleeping" (e.g. event prep, retreat hub)
- **Booking References file** for the trip, if the trip keeps one. If it doesn't and the user wants one, the minimal structure is one section per booking: confirmation #, channel + URL, total paid, cancellation deadline, property contact.
- **The trip's project hub file** (`03 Projects/<Trip Name>.md`), if one exists — update whatever status/summary/pending-decision sections it has.
- **Bidirectional verification grep** — run AFTER all the fan-out updates above are complete, not before. Verification greps to confirm fan-out closure (triage every hit per `_shared-rules.md` §12 — stale cross-reference / live locator / historical record / different context — don't blind-edit):
  1. **Forward (new identifier):** grep the booked hotel name across the trip's folder and `01 Now/` — confirms every living doc that should reference the new state actually does.
  2. **Reverse (old/superseded identifier):** grep the *prior* state phrases (e.g. "still need to book", the previous hotel name if pivoting) across the same scope — confirms nothing got missed. **Variant coverage:** placeholder terms travel in pairs/sets — grep `TBC` AND `TBD` (interchangeable), plus `pending`, `tentative`, `?`, `[ ]` — use fixed-string mode (`grep -F` / `rg -F`) for the literal tokens; as regex, `?` and `[ ]` match wrongly and flood the hit-set. Single-variant grep silently misses the others.
  3. **Relocated-anchor coverage:** if this booking moved a section/doc (e.g. consolidated a sub-trip's notes into a new file), grep the moved-from doc's bare inbound anchor (`[[wikilink]]` + path forms) with NO keyword conjunction — a narrow pattern drops semantic-variant pointers like "the trip doc".
- Superseded shortlists: add this banner at the top of the old doc/section rather than deleting — `> ⚠️ SUPERSEDED — active doc: [[<new doc>]]` — and keep the research below it.

**Edit safety:** Shared planning files in the fan-out (`Works in Progress.md`, `This Week.md`, project hubs) go through `locked-edit.sh`, not the Edit tool — see `_shared-rules.md` §5. For all edits (either mechanism): PostToolUse formatters may modify files between Read and Edit. Use *minimal-context* `old_string`s (just the unique line being changed, not full table rows with trailing whitespace) so formatter normalisation doesn't break the match. Re-Read and retry with shorter strings if a match fails. If writing verbatim quoted text (review excerpts, source quotes) into the accommodation doc where exact wording matters, formatting hooks can silently rewrite it — see `_shared-rules.md` §14.

## Heuristics summary (the load-bearing ones)

- **Noise heuristic:** intra-property noise (doors, trolleys, neighbours) is the real risk. Tracks hotel tier > neighbourhood. Nice hotel in busy area > busy hotel in nice area.
- **Direct first:** chain hotels with loyalty programs → property direct site before OTA price comparison.
- **Region-dominant OTA first** for candidate discovery.
- **Cash > points for status-progression users:** redemption stalls tier; pay cash.
- **Verbatim quotes for load-bearing facts:** prevents quick-read errors on percentages and feature claims.
- **Lead-time warning (chain-loyalty packages only):** <7 days = expect ~5-10% loyalty rate, not 18-25% package discounts. OTA promo discounts are NOT lead-time-gated — don't conflate.
- **Geography is verifiable, not inferable:** never generate distance claims from prose-grouping. Search or ask.
- **OTA listings disagree:** single-OTA "amenity not listed" ≠ ground truth. Cross-check.

## Skill Monitor

As you execute this skill, follow `_skill-monitor.md` (same commands directory as this file): watch for gaps, and propose specific edits to this skill at the end.
