# [City] [Stay Type] Accommodation — [Date Range]

> Template for accommodation decision documents — see `.claude/commands/book-stay.md` for the workflow that fills it in. Replace bracketed placeholders. Delete sections that don't apply.

**Status:** [Researching / Shortlisted / Booked / Booked + Stayed / Superseded — link to active doc]

## Header — at-a-glance

| | |
|---|---|
| **Hotel** | [Property name + brand if relevant] |
| **Address** | [Full address] |
| **Phone / Email** | [Property contact] |
| **Check-in** | [Day Date Year, after HH:MM] |
| **Check-out** | [Day Date Year, before HH:MM] |
| **Nights** | [N] |
| **Room** | [Category, sqm, bed config, view] |
| **Rate** | [Rate name — e.g. "Member Exclusive — Flexible Rate"] |
| **Total** | [Local currency total ≈ home-currency total, ≈ per-night incl. all taxes & fees] |
| **Reservation #** | [primary booking ref] |
| **Room confirmation #** | [room-specific ref if different] |
| **Card on file** | [Optional — omit if you don't want payment details in notes. Card last-4 + note: must present at check-in if guarantee policy requires] |
| **Cancellation** | [Free until X / Costs N nights to cancel after Y / Non-refundable] |
| **Booked via** | [Direct site name OR OTA name] |
| **Booking URL** | [Deeplink to the booking / confirmation page] |
| **Loyalty** | [Member number attached / status tier / expected points earned] |

## Includes (rate-specific)

- [Breakfast / lounge access / WiFi / pool & gym / loyalty perks / discounts at on-site F&B / etc.]

## Special requests submitted

> [Verbatim text of the special requests box from the booking confirmation, for reference at check-in]

---

## Context

[Why this trip leg, who's travelling, what the stay is for, what frame applies (e.g. "solo professional, event week" vs "romantic weekend" vs "family trip"). Include constraints: connectivity risk, time zone, weather, etc.]

## Decision framework

**Tier:** [Budget/mid/upper/luxury, with per-night ceiling]
**Priorities (ranked, not flat):** [Firmest requirement first, then negotiable, then nice-to-have]
**Hard requirements:** [Specific must-haves: laundry, ethernet, quiet room, etc.]
**Constraints to honour:** [E.g. proximity to coworking, walking distance to event, must be near transit, etc.]
**Risk tolerance:** [Cancellation flexibility, build-quality variability, etc.]

## Price comparison table

> Use your home currency throughout. The *user* provides live hotel prices (from their OTA app / property site); the agent's job is only the FX conversion, using a *live* rate — never a remembered heuristic.
> Keep per-night and stay-total as separate columns so "cheapest" is unambiguous on each dimension.

| Hotel | Area | /night incl. tax | N-night total | [Firmest requirement] match | Anchor proximity (if relevant) |
|---|---|---|---|---|---|
| | | | | | |

## Ranked shortlist (prices user-verified live)

### 1. [Top pick] — [Area] — [Verdict]

- **Location:** [Specific address details, transit/walking distances, neighbourhood vibe]
- **Rating:** [Review stars + review count]
- **Price:** [User-verified live rate + channel + cancellation policy + breakfast inclusion]
- **Room:** [Category, sqm, bed type, view]
- **Distinctive features:** [Recent renovation, build quality, brand standard, recent review excerpt]
- **Pros:** [Bullet]
- **Cons:** [Bullet — be honest]
- **Verdict:** [Conditional or definitive recommendation with reasoning]

### 2. [Runner-up]

[Same structure]

### 3. [Third option / fallback]

[Same structure]

## Ruled out

- **[Hotel]** ([Area]) — [One-line reason: over budget / wrong neighbourhood / wrong vibe / poor reviews / unavailable]
- **[Hotel]** — [Reason]

## Verified prices ([Date])

> User-pulled from [OTA / property direct] on [Date]. Re-verify before booking if dates shift.
>
> ⚠️ For chain hotels with loyalty programs: **always check the property direct site as well as OTAs.** Direct often unlocks member rates, package discounts, and on-site benefits that OTAs don't pass through. Phone bookings to the property count as direct.

| Hotel | Channel | Rate type | /night incl. tax | Total | Cancellation | Notes |
|---|---|---|---|---|---|---|
| | | | | | | |

## Sub-decisions (optional)

### Coworking / event venue (if applicable)

[Decision on daily workspace + event venue if relevant. Same template structure: shortlist → comparison → pick → action items.]

### Multi-leg structure (if applicable)

[Decision on how to split a longer block across multiple cities or weekends.]

## Action items

- [ ] [Concrete pre-stay action — e.g. walk-in inspect, book coworking, request high floor]
- [ ] [Booking action]
- [ ] [Fan-out updates after booking]

---

## Decision context — historical (preserved post-booking)

> Once booked, preserve the deliberation here for future reference and skill iteration. Don't delete.
> If the doc gets superseded by changing context, add this banner at the top — `> ⚠️ SUPERSEDED — active doc: [[<new doc>]]` — and keep the research below it.

### What changed during the decision

[Briefly: what assumptions held, what got falsified, what surprised you, what the final logic was]

### Why the alternatives were ruled out

[List of alternatives considered + why each was dropped]

### What this case taught me about future bookings

[Insights worth carrying forward — promote stable ones into the `book-stay` skill]

---

## Relationship to other vault docs

- [[Link to the travel project hub]]
- [[Link to trip-leg Booking References file]]
- [[Link to project that drove the trip — e.g. event prep, retreat hub]]
