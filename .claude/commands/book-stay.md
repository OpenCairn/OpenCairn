---
name: book-stay
description: Choose and book a hotel (or stay) — quiz preferences, generate shortlist, verify rates, hand off booking, fan out references across the vault.
---

# Book Stay

Pipeline for choosing and booking a hotel for a trip leg. **One pipeline run and one accommodation doc per leg** — for a multi-city trip, split into legs first and run Steps 1-11 per leg (record the split rationale in the doc template's Multi-leg section), updating the trip hub once at the end.

**Prerequisites:** web search (candidate research + live FX rates) and the AskUserQuestion quiz tool. The vault doc template lives at `{VAULT}/07 System/Templates/Accommodation Decision.md`. **No vault?** Skip Step 1's context-load, Step 8's doc write, and Step 11 entirely (Step 1's lead-time check and currency step still run) — the quiz → research → verify → handoff core works anywhere.

**Scope:** hotels and short stays. Restaurants and other venue bookings are out of scope.

### 0. Resolve Vault Path (vault installs only)

```bash
if [ -z "${VAULT_PATH:-}" ]; then echo NO_VAULT; else "$VAULT_PATH/.claude/scripts/resolve-vault.sh"; fi
```

If the output is the literal `NO_VAULT`, no vault is configured — don't abort; run in no-vault mode per the Prerequisites note. Any other error is a vault install with a broken path: abort (no silent fallback — `_shared-rules.md` §1). Read `_shared-rules.md` from this skill's own commands directory and apply its rules throughout — §5 (locked edits) governs every shared-planning-file write below. All paths use `{VAULT}` as a placeholder — substitute the resolved vault path.

## Inputs

- City + dates + context (purpose, solo/companion, budget tier hint)
- Currently-loaded vault state (the relevant project hub, any existing accommodation doc for the city)

## Steps

### 1. Context-load + lead-time check

- Read the travel project hub if one exists (`03 Projects/<Trip Name>.md`) and any existing accommodation doc for the city. On a fresh vault with neither, note it and continue — don't invent structure.
- **Don't re-research what's already in the vault — refine instead.**
- **Stale check:** if the existing doc has a SUPERSEDED banner or is >1 month old, treat it as historical context only. If the user has flagged a context shift since the doc was written (e.g. "we used to be planning A but now it's B"), explicitly re-open rather than refining.
- **Compute booking lead time** (`check-in date − today`; run `date` for today — never assume it). Warn the user if it's <7 days: most chain-hotel package discounts require 7-21 days advance booking, so the realistic discount ceiling at short lead time is ~5-10% via a loyalty member rate, not the 18-25% a package can reach. **But distinguish chain-loyalty packages (lead-time-gated) from OTA promo discounts (not).** OTA promotions ("intro offer", "mobile exclusive") and individual property opening-discounts often apply at any lead time — don't tell the user to expect zero discounts last-minute. Set expectations on chain packages specifically.
- **Establish the user's home currency** (locale in CLAUDE.md, or ask once in plain conversation before the quiz — the frame call is already at the 4-question cap) — all totals present in it.
- **An event or conference "partner rate" is not automatically a discount.** When the stay is tied to an event that supplies a negotiated rate sheet, price it against open-market rates for the same dates *before* treating it as a saving — a negotiated rate can sit at or above market, and the sheet typically quotes no rack rate to compare against. Check the sheet for the three things most often missing: a **validity window**, a **booking code and deadline**, and whether the rate covers nights **outside** the event dates. Establish early whether the event has one partner property or several, since that decides whether a cheaper negotiated rate exists at all — and if it has only one, say so plainly, because it means the shortlist runs on open-market pricing and there is nothing further to chase.
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

**The stated hard-requirement list is incomplete by construction — probe for the unfixable.** Users name the requirements they have learned to ask for, which are mostly the ones a listing already answers (location, bed config, breakfast, price). The criterion that actually decides a stay is more often one they never thought to name because they assume basic competence, and which **cannot be fixed once checked in**: room temperature and climate control, water pressure, bed firmness, air quality, light leakage. Before finalising the filter, ask one question — "what would ruin this stay and could not be sorted out at the front desk?" Weight the answer heavily when the stay is sleep-critical: early starts, event or performance days, jet lag, or back-to-back travel with no recovery day. A candidate can satisfy every stated requirement and still be the wrong booking on this axis.

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
- **Enumerate the walkable ring from map data, not from OTA area labels.** OTAs assign properties to named districts for marketing, so a listing filed under an area can sit well outside walking distance of that area's landmark. Where the anchor's street address is known, query a mapping data source for accommodation within a radius of it and rank by measured distance. This surfaces candidates the OTA's area filter omits and drops ones it wrongly includes. **Reuse `map-day`'s geocoding discipline rather than improvising it** — exact-match escalation when a fuzzy search would substitute a similarly-named place in the wrong city, dropping results that land far from the cluster median, and the approximate-street fallback when a property simply isn't in the dataset. Whenever a distance is derived rather than measured (triangulated from a neighbouring street number, or from distances the listing publishes to known points), **state the derivation and its uncertainty** instead of presenting one confident figure.
- **A property's own published distances may measure the wrong landmark.** Listings quote distance to the famous version of a place name, which can be a different location from the anchor that matters. Check which specific landmark a quoted distance refers to before letting it override a measured figure, and treat guest complaints about "location" the same way — they usually describe distance to tourist attractions or the density of nearby food and shops, not distance to the user's actual anchor. Those are separate findings and should be reported separately.
- **Rank the review base, not the headline score.** A score is uninterpretable without its count — a high score across a few hundred reviews and a slightly lower score across several thousand are not comparable, and the larger base is usually the stronger evidence. The same discipline applies to an OTA's **aggregated complaint summary**: read it early, because it is cheap and surfaces recurring themes a hand-read sample will miss — but **read its stated base count and compare it against the property's total before weighting it.** Such a summary is not necessarily computed over the whole set, and a summary drawn from a small subsample is weaker evidence than a larger sample you read yourself, not stronger. Where the source states the base it was computed from, carry that number with the claim; where it doesn't, treat the summary as unquantified and weight it as a lead rather than a finding. Either way, what it names first is a lead to verify against individual reviews, never the property's confirmed weakness. Checkable: any aggregated summary cited in the decision carries either its base count or an explicit note that the source published none.
- **A rebrand or major renovation splits a listing's review history — date-check in both directions.** Aggregator listings routinely carry reviews from a predecessor property straight across a rebrand, so old complaints may describe a building that no longer exists. Establish the opening, renovation or rebrand date before treating an old complaint as current. **The symmetric error costs just as much:** having found one listing carrying stale reviews, do not then dismiss a genuinely current review base as stale. Verify the age distribution of the reviews before adjusting a candidate's ranking either way.
- **Read finalists to comparable depth, or state the asymmetry explicitly.** Reading a large review sample for one candidate and a handful for another, then comparing fault counts, is invalid — the larger sample surfaces more faults regardless of actual quality. Either sample comparably before ranking, or say plainly which comparison the evidence supports and which it does not. A finding that survives the asymmetry (for example, one appearing in a whole-set aggregated summary rather than in individual reviews) can still be relied on; say why.

### 5. User-assisted price verification of finalists

For each finalist, establish: room type, sqm, current rate, breakfast inclusion, cancellation deadline, home-currency total. **Division of labour — the agent verifies the FX rate, the user verifies the prices:**

- Claude generates the qualitative shortlist with reasoning + estimated price ranges + property reputation
- **User pulls live prices on their phone app** (OTA apps / hotel direct) — 5 min, much more reliable than the agent fighting bot-resistant, JS-heavy travel SPAs
- User pastes back screenshots or numbers
- **For chain finalists, bundle the Step 6 direct-channel check into the same phone round-trip** — final re-ranking waits until both OTA and direct prices are in, so the user isn't asked to redo the comparison
- Claude converts using a *live* FX rate (never a remembered conversion heuristic) and re-ranks against the live data

**Price the inclusions by differencing near-identical rate plans.** A property normally lists several rate plans against the same room. Two plans differing in exactly one inclusion give that inclusion's true price; divide it out per person per night and compare it against the à-la-carte price the listing quotes. Then re-compare every candidate on a **room-only** basis, so an inclusion bundled into one rate and sold separately at another doesn't distort the ranking. Two things this catches that scanning the price column does not:
- **A cheaper plan can also be the more inclusive one.** Price does not reliably order inclusions, so the best row is not always the obvious one — and a plan badged as a deal or early-bird price is not guaranteed to beat an unbadged one. Check rather than assume the labelling.
- **Whether pay-at-property costs anything.** The premium over prepay varies by property and is sometimes zero — when it is, it is strictly better, and when it is material it rarely justifies itself against a free-cancellation deadline that already runs close to arrival.

Where a rate's inclusion wording is ambiguous (a count that could mean per-stay or per-person-per-day), check whether the conclusion is robust to both readings before spending effort resolving it — often the ranking holds either way and the ambiguity is moot. The booking confirmation resolves it definitively.

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
- **Write the accommodation doc now, before any booking (vault installs only)** — the research product must survive the session whether or not the user books today. Copy `{VAULT}/07 System/Templates/Accommodation Decision.md` to the trip's project folder as `<City> Accommodation - <date range>.md` (hyphen, not em dash — em dashes in filenames are shell-hostile), and populate it from Steps 2-8 per the template's own instructions (replace placeholders, delete inapplicable sections; booking-confirmation fields stay empty until Step 11). If a doc for this leg already exists, update it in place. If no trip project folder exists, ask the user where to put it — don't invent structure.

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

- The accommodation doc for this trip leg, already written at Step 8 — update it: mark booked, confirmation #, booking URL, free-cancel deadline.
- The trip's timeline / overview docs, if the trip has them.
- The `03 Projects/` doc of the project that drove the trip (event prep, work engagement), if distinct from the trip hub below — update its status/Next Actions where the booking changes them.
- `01 Now/This Week.md`, if it exists (mark task done, update the Status banner if the booking changes it)
- Any project-specific doc that referenced "where am I sleeping" (e.g. event prep, retreat hub)
- **Booking References file** for the trip, if the trip keeps one. If it doesn't and the user wants one, the minimal structure is one section per booking: confirmation #, channel + URL, total paid, cancellation deadline, property contact.
- **The trip's project hub file** (`03 Projects/<Trip Name>.md`), if one exists — update whatever status/summary/pending-decision sections it has.
- **Bidirectional verification grep** — run AFTER all the fan-out updates above are complete, not before. Verification greps to confirm fan-out closure (triage every hit per `_shared-rules.md` §12 — stale cross-reference / live locator / historical record / different context — don't blind-edit):
  1. **Forward (new identifier):** grep the booked hotel name across the trip's folder and `01 Now/` — confirms every living doc that should reference the new state actually does.
  2. **Reverse (old/superseded identifier):** grep the *prior* state phrases (e.g. "still need to book", the previous hotel name if pivoting) across the same scope — confirms nothing got missed. **Variant coverage:** placeholder terms travel in pairs/sets — grep `TBC` AND `TBD` (interchangeable), plus `pending`, `tentative`, `?`, `[ ]` — use fixed-string mode (`grep -F` / `rg -F`) for the literal tokens; as regex, `?` and `[ ]` match wrongly and flood the hit-set. Single-variant grep silently misses the others.
  3. **Relocated-anchor coverage:** if this booking moved a section/doc (e.g. consolidated a sub-trip's notes into a new file), grep the moved-from doc's bare inbound anchor (`[[wikilink]]` + path forms) with NO keyword conjunction — a narrow pattern drops semantic-variant pointers like "the trip doc".
- Superseded shortlists: add this banner at the top of the old doc/section rather than deleting — `> ⚠️ SUPERSEDED — active doc: [[<new doc>]]` — and keep the research below it.

**Edit safety:** Shared planning files in the fan-out (`This Week.md`, project hubs) go through `locked-edit.sh`, not the Edit tool — see `_shared-rules.md` §5. For all edits (either mechanism): PostToolUse formatters may modify files between Read and Edit. Use *minimal-context* `old_string`s (just the unique line being changed, not full table rows with trailing whitespace) so formatter normalisation doesn't break the match. Re-Read and retry with shorter strings if a match fails. If writing verbatim quoted text (review excerpts, source quotes) into the accommodation doc where exact wording matters, formatting hooks can silently rewrite it — see `_shared-rules.md` §14.

## Heuristics summary (the load-bearing ones)

- **Noise heuristic:** intra-property noise (doors, trolleys, neighbours) is the real risk. Tracks hotel tier > neighbourhood. Nice hotel in busy area > busy hotel in nice area.
- **Direct first:** chain hotels with loyalty programs → property direct site before OTA price comparison.
- **Region-dominant OTA first** for candidate discovery.
- **Cash > points for status-progression users:** redemption stalls tier; pay cash.
- **Verbatim quotes for load-bearing facts:** prevents quick-read errors on percentages and feature claims.
- **Lead-time warning (chain-loyalty packages only):** <7 days = expect ~5-10% loyalty rate, not 18-25% package discounts. OTA promo discounts are NOT lead-time-gated — don't conflate.
- **Geography is verifiable, not inferable:** never generate distance claims from prose-grouping. Search or ask. Enumerate the walkable ring from map data; OTA area labels are marketing, not geography.
- **OTA listings disagree:** single-OTA "amenity not listed" ≠ ground truth. Cross-check.
- **The deciding criterion is often absent from the stated requirements.** Probe for what can't be fixed after check-in — climate control above all when the stay is sleep-critical.
- **Review count outranks review score.** An aggregated complaint summary is a lead, not a verdict — check its stated base count against the property total before weighting it.
- **Rebrands and renovations split review history:** date-check before trusting an old complaint *or* dismissing a current review base as stale. Both errors are live.
- **Comparable depth or declared asymmetry:** more faults found in a bigger sample is not evidence of a worse hotel.
- **Difference near-identical rate plans** to price inclusions, then compare room-only. The cheapest plan can also be the most inclusive.
- **Event partner rates need an open-market check:** negotiated ≠ discounted.

## Skill Monitor

As you execute this skill, follow `_skill-monitor.md` (same commands directory as this file): watch for gaps, and log observations at the end per that file.
