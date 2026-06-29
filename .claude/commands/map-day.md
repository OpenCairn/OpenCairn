---
name: map-day
description: Turn a day's itinerary (from This Week / a date / a list of places) into a phone-glanceable Organic Maps KML plus a tight markdown day-sheet. Geocodes via OSM, keeps fixed-time stops in time order, and emits numbered pins + a route line.
argument-hint: "[date | list of places | empty = today]"
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

- `python3` (stdlib only — no pip installs).
- Network at build time for geocoding (the resulting map is fully offline). Results
  are cached to `~/.cache/itinerary-map/geocode-cache.json`, so re-runs are offline.
- **Organic Maps** installed on the phone with the destination region downloaded.
- For phone delivery: any way to move a file to the phone — KDE Connect (Linux/KDE),
  USB/`adb`, AirDrop/Quick Share, or email-to-self (optional — see Phase 4).

Verify `python3` is present (`command -v python3`); if any prerequisite is missing,
tell the user the specific thing to install/download and stop.

## Arguments

`$ARGUMENTS` — one of:
- a **date** (e.g. `today`, `Tue`, `2026-06-29`) → read that day's block from
  `01 Now/This Week.md`;
- a **list of places** (pasted) → use those directly;
- empty → default to today.

## Workflow

### Phase 0: Resolve the vault
Run `"$VAULT_PATH/.claude/scripts/resolve-vault.sh"`. Abort if it fails.

### Phase 1: Gather the stops
- If given a date, read the matching day block from `01 Now/This Week.md`. Pull out
  every place with a location: name, any address/cross-street/district already in
  the note, the time (if given), and a one-line note.
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
    {"name": "Sparse POI", "lat": 31.24, "lon": 121.49, "notes": "manual coords"}
  ]
}
```
- `query` should be as specific as the vault allows (street number + district + city).
- `fixed` (HH:MM, zero-padded) only on genuine time-window stops — these keep their
  time order; everything else is slotted by shortest added walking distance. Ordering
  is **distance-only**: it keeps anchors in time order but does *not* verify travel time
  fits between them — eyeball the result. Reserve `fixed` for hard appointments /
  last-entry; omit it for soft opening-hours where arriving any time later is fine.
- For a POI you already know OSM lacks (or that geocodes wrong on a dry run), supply
  `lat`/`lon` directly and omit `query` to skip geocoding.

### Phase 3: Run the script
```
python3 "$VAULT_PATH/.claude/scripts/itinerary-map.py" <input.json> \
    --outdir "<trip folder>/Maps"
```
- Output folder: a `Maps/` subfolder of the relevant trip, so artefacts live with the
  trip and sync with the vault. Create it if absent. If the day has no obvious trip folder
  (a pasted list, a home-city day), **ask the user where to save** rather than guessing.
- **Check the run output:** `UNRESOLVED` = a genuine OSM miss → fix the `query` and
  re-run, or supply manual `lat`/`lon`; `NETWORK` = a transient failure → just re-run.
  You can't inspect the phone app yourself, so when a manual coord is needed, take it
  from a web source or **ask the user** to look the place up in Organic Maps' on-device
  search (pair the name with its romanised form).
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
- One stop, one pin: re-running with the same `slug` overwrites cleanly.
