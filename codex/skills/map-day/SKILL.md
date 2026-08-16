---
name: map-day
description: Turn a day's itinerary (from This Week / a date / a list of places) into a phone-glanceable Organic Maps KML plus a tight markdown day-sheet. Geocodes via OSM, keeps fixed-time stops in time order, and emits numbered pins + a route line.
---

# Map-day — itinerary to Organic Maps

Take a day's planned stops, geocode them, work out a sensible walking order, and
produce two artefacts:

1. **`<slug>.kml`** — numbered, ordered pins + a route line. Import into
   **Organic Maps** (offline OSM): tap the bookmarks button → every pin on the
   map at once → tap one for its note. This is the phone glance.
2. **`<slug>-daysheet.md`** — a tight ordered list (time · place · one-line note ·
   leg distance) that renders on Obsidian mobile.

**Why Organic Maps:** offline OSM, works with no VPN once the region is
downloaded, and WGS-84 end-to-end so pins land correctly even in China (no
GCJ-02 offset, unlike Google/static tiles). Geocoding uses the same OSM dataset,
so a pin lands exactly where the app shows the place.

## When to use

Triggers: "map out [today / Tuesday / this day]", "where are these places", "what
order should I do these in", "make a map for the Shanghai day", or a pasted list
of places to plot. Works for any city, in or out of China.

## Prerequisites

**Hard — verify these, and stop if either is missing:**
- `python3` (stdlib only — no pip installs). Check with `command -v python3`.
- Network at build time for geocoding (the resulting map is fully offline).
  Successful lookups are cached to `~/.cache/itinerary-map/geocode-cache.json`, so a
  re-run of an unchanged day is offline — but any new or edited `query` still needs
  the network.

**Soft — can't be checked from the laptop; tell the user, don't block on them:**
- **Organic Maps** installed on the phone with the destination region downloaded.
  The build runs without it; the map is just unusable until it's there.
- Some way to move a file to the phone — KDE Connect (Linux/KDE), USB/`adb`,
  AirDrop/Quick Share, or email-to-self. Phase 4 falls through channels; if none is
  reachable, leave the file in the vault and say so.

## Arguments

Interpret the free-text arguments following `$map-day` as one of:
- a **date** (e.g. `today`, `Tue`, `2026-06-29`) → read that day's block from
  `01 Now/This Week.md`;
- a **list of places** (pasted) → use those directly;
- empty → default to today.

## Workflow

### Phase 0: Resolve the vault
Run `"$VAULT_PATH/.claude/scripts/resolve-vault.sh"`. Abort if it fails.

### Phase 1: Gather the stops
- If given a date, read the matching day block from `01 Now/This Week.md`. Day blocks
  are flat task checklists, not itineraries — most lines carry no location at all, and
  a past day may be collapsed to a single prose paragraph with no list left. Pull out
  only the lines that name a place: name, any address/cross-street/district already in
  the note, the time (if given), and a one-line note.
- **A day needs roughly three or more located stops to be worth mapping.** If the day
  block yields fewer, say so and stop — don't build a one-pin map, and don't pad the
  day with places the user didn't plan.
- **Reuse addresses already in the vault** before geocoding from scratch — check the
  relevant place/recommendations docs for the destination (e.g. a city's walking-tour
  or recommendations note). Grep the trip folder for the place name.
- Identify **fixed time-windows**: opening hours ("opens 11:00"), set meetings, a
  must-be-there-by time. These anchor the route.
- Identify the **start point** (hotel/hostel/current location) if known.
- Skip stops with no fixed location (e.g. "meet X after work, tentative") — note them
  in the day-sheet prose instead of as a pin.

### Phase 2: Build the input JSON
Write a JSON file (to scratch) in this shape:
```json
{
  "day": "Mon 29 Jun — City",
  "slug": "2026-06-29-city",
  "region": "City, Country",
  "start": {"name": "Hotel", "query": "<address>"},
  "stops": [
    {"name": "Place", "query": "<address or POI>, <district>, <city>",
     "time": "11:00", "fixed": "11:00", "notes": "<one line>"},
    {"name": "Named Venue", "poi": true, "notes": "no street address known"},
    {"name": "Sparse POI", "lat": 31.24, "lon": 121.49, "notes": "manual coords"}
  ]
}
```
- `query` should be as specific as the vault allows (street number + district + city).
- If the day label includes a weekday, verify it with `date -d "YYYY-MM-DD" +%A`; never infer the weekday from the date.
- **`"poi": true`** for a stop that is a venue *name* rather than a street address.
  Nominatim fuzzy-ranks and will confidently substitute a similarly-named place
  (same-named POI in another city, a different museum in the right city — both
  observed in the field); `poi` escalates to an Overpass **exact** name-tag match
  (`name`/`name:en`/`alt_name`/`official_name`) inside the region's bounding box —
  the venue itself, or an honest zero (`UNRESOLVED`), never a substitute. The match
  is case-sensitive and whole-name: give the name with OSM's capitalisation (for
  Chinese venues, the native-script name usually matches best). **On a `poi` stop,
  `query` (if present) is used as that exact whole name** — so omit `query`, or make
  it the bare venue name with NO district/city suffix (a suffixed query guarantees a
  false zero). The "as specific as possible" rule above applies to address stops only.
- `fixed` (HH:MM, zero-padded) only on genuine time-window stops — these keep their
  time order; everything else is slotted by shortest added walking distance. Ordering
  is **distance-only**: it keeps anchors in time order but does *not* verify travel time
  fits between them — eyeball the result. Reserve `fixed` for hard appointments /
  last-entry; omit it for soft opening-hours where arriving any time later is fine.
- For a POI you already know OSM lacks (or that geocodes wrong on a dry run), supply
  `lat`/`lon` directly and omit `query` to skip geocoding.
- **Dry-run probe** (optional, to sanity-check a doubtful stop before the full run).
  Probe the service the stop will actually use — an address stop goes to Nominatim, a
  `poi` stop goes straight to Overpass and never touches Nominatim, so a Nominatim hit
  says nothing about it. Either way use `--data-urlencode` so spaces, quotes, `&` and
  CJK in the place name are encoded correctly (hand-building the URL is exactly how the
  query silently truncates).
  **Address stops** — `limit=1`, because the script only ever takes the first hit; a
  rank-2 match is not what will be pinned:
  ```
  curl -sG "https://nominatim.openstreetmap.org/search" \
      --data-urlencode "q=<place>, <city>" \
      --data-urlencode "format=json" --data-urlencode "limit=1" \
      -A "OpenCairn-itinerary-map/1.0 (+https://github.com/OpenCairn/OpenCairn)" \
    | python3 -m json.tool
  ```
  Read the `display_name` — is it the right place in the right city? (Raise `limit`
  only to see what else is nearby, never to call a lower-ranked hit a pass.)
  **`poi` stops** — exact whole-name match inside the region's bounding box, given as
  `south,west,north,east`:
  ```
  curl -s "https://overpass-api.de/api/interpreter" \
      --data-urlencode 'data=[out:json][timeout:25];nwr["name"="<exact name>"](<s>,<w>,<n>,<e>);out center 1;' \
      -A "OpenCairn-itinerary-map/1.0 (+https://github.com/OpenCairn/OpenCairn)" \
    | python3 -m json.tool
  ```
  An empty `elements` list means wrong capitalisation, wrong name, or the venue simply
  isn't in OSM under it — the real run also tries `name:en`, `alt_name` and
  `official_name`, so probe those tags too before calling it a genuine zero.

### Phase 3: Run the script

Generate outside the vault first. Vault files must be installed through the locking wrapper, never written by the map script directly:

```
STAGE_DIR="$(mktemp -d)"
python3 "$VAULT_PATH/.claude/scripts/itinerary-map.py" <input.json> \
    --outdir "$STAGE_DIR"
```
- Optional flags: `--keep-order` emits stops in input order (skips the
  cheapest-insertion route optimisation — use when the user has already fixed the
  order; it also **ignores every `fixed` anchor**, so time order survives only if the
  input is already in it); `--max-spread-km <km>` tunes the wrong-city guard (default
  50; `0` disables it, e.g. for a genuine multi-city day); `--no-network` is
  cache-only — never calls Nominatim/Overpass, so anything not already cached comes
  back unresolved.
- Destination folder: a `Maps/` subfolder of the relevant trip, so artefacts live with the
  trip and sync with the vault. Create the directory if absent. If the day has no obvious trip folder
  (a pasted list, a home-city day), **ask the user where to save** rather than guessing.
- After all output checks pass, install each staged text artefact through
  `"$VAULT_PATH/.claude/scripts/locked-edit.sh"`. For a missing destination, stream the
  staged file to `--append` (which creates it). For an existing destination, re-read its
  complete current contents and use them as the literal OLD payload to `--replace`, with
  the staged file as NEW and the exact separator line
  `========OPENCAIRN-LOCKED-EDIT-SEP========`. On exit 2 or 3, re-read and retry; never
  fall back to a direct copy or write. Remove the scratch directory only after both files
  have landed successfully.
- **Check the run output — stdout *and* stderr.** Every partial failure still exits 0,
  so the exit code proves nothing:
  - stdout `UNRESOLVED (n): <names>` — the roll-up of every stop that got no pin. A
    name annotated `(network — re-run)` was a transient failure, so just re-run; one
    annotated `(wrong-city outlier — fix query)` geocoded far from the day's median and
    was dropped from the map; a bare name is a genuine OSM miss. For the latter two,
    fix the `query`, mark the stop `"poi": true`, or supply manual `lat`/`lon`.
  - stderr `! NETWORK …` / `! UNRESOLVED …` / `! OUTLIER …` — the per-stop detail
    behind those roll-up entries, including how far the outlier sat from the median.
  - stderr `! WARNING: the two resolved points are … km apart` — fires when only two
    points resolved and they are far apart. The guard can't tell which one is wrong, so
    **nothing is dropped and both pins ship**; check both yourself before trusting the map.
  - stderr `No resolvable stops. Aborting.` with exit 1 — nothing resolved, so neither
    the KML nor the day-sheet was written. Fix the queries and re-run.
- You can't inspect the phone app yourself, so when a manual coord is needed, take it
  from a web source or **ask the user** to look the place up in Organic Maps' on-device
  search (pair the name with its romanised form).
- **Not-in-OSM fallback** (Overpass honest zero, no usable address): either pin the
  *street or block* instead — geocode the street and append **` (APPROX)`** to the
  stop's `name` so the pin itself says it's approximate — or drop the stop to
  day-sheet prose. **Never invent coordinates**, and never present a street-level
  pin as the venue.
- Sanity-check the printed order and the day-sheet leg distances: do the coordinates
  sit in the right city? Does a leg crossing a river/harbour look implausibly short?
  (Distances are crow-flies — the day-sheet says so.)

### Phase 4: Deliver to the phone
The KML is in the vault. To get it onto the phone for Organic Maps, use whatever
file-transfer channel fits the OS — then on the phone, open the file → **Open with
Organic Maps** → it imports as a bookmark list:
- **Linux/KDE — KDE Connect:** first `command -v kdeconnect-cli` — if absent, skip
  to another channel. Otherwise check the phone is reachable with `kdeconnect-cli -a`;
  if it lists the phone, `kdeconnect-cli --share "<path>/<slug>.kml" -d <device-id>`
  (`<device-id>` from `kdeconnect-cli -a --id-only`). Needs both on the same LAN, so it
  fails on networks with client isolation (hostel/public wifi).
- **USB (most reliable):** `adb push "<path>/<slug>.kml" /sdcard/Download/` (Android),
  then on the phone open **Files → Downloads**. If it doesn't appear, trigger a media
  scan: `adb shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Download/<slug>.kml`.
- **Otherwise:** AirDrop/Quick Share, email-to-self, or any sync that includes non-`.md`
  files (the `.kml` is small text). If a channel isn't reachable, say so — don't claim
  it was sent.

### Phase 5: Report
Tell the user: the order chosen, total on-foot distance, where the two files are, any
unresolved/hand-fixed pins, and the delivery status (sent / ready-to-send). Do **not**
auto-link the day-sheet into living docs unless asked.

## Notes
- Distances/times are straight-line — fine for "what's near what / what order",
  not for turn-by-turn. Organic Maps does the actual on-foot routing.
- The route line is a single `LineString` through the pins in order — a visual
  thread, not a road-snapped path.
- One stop, one pin: re-running with the same `slug` replaces the two generated files through the vault lock.
