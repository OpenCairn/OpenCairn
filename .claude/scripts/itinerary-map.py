#!/usr/bin/env python3
"""itinerary-map — turn a day's stops into an Organic Maps KML + a glanceable day-sheet.

Pure stdlib (urllib for geocoding, no pip installs). Input is a small JSON file
describing the day; output is `<slug>.kml` (numbered, ordered pins + a route line
for Organic Maps / any KML viewer) and `<slug>-daysheet.md` (a tight, ordered
markdown sheet that renders on Obsidian mobile).

Input JSON shape:
{
  "day":  "Mon 29 Jun — Shanghai",        # human label
  "slug": "2026-06-29-shanghai",          # output filename stem
  "region": "Shanghai, China",            # appended to geocode queries for disambiguation
  "start": {"name": "Hostel", "query": "608 Xikang Rd, Jing'an, Shanghai"},
  "stops": [
    {"name": "Ho Tung Residence", "query": "457 Shaanxi North Rd, Jing'an, Shanghai",
     "time": "11:00", "fixed": "11:00", "notes": "Hudec villa; last entry 18:30"},
    {"name": "MAP Pudong", "lat": 31.241, "lon": 121.497, "notes": "manual coords"}
  ]
}

A stop with explicit "lat"/"lon" skips geocoding (use for OSM-sparse POIs).
"fixed" (HH:MM) marks a hard time-window anchor; anchored stops keep their time
order, free stops are slotted by cheapest-insertion to minimise walking.

Usage:
  itinerary-map.py INPUT.json --outdir DIR [--no-network]
"""
import argparse
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from xml.sax.saxutils import escape

CACHE = os.path.expanduser("~/.cache/itinerary-map/geocode-cache.json")
NOMINATIM = "https://nominatim.openstreetmap.org/search"
# Nominatim policy requires a genuine identifying User-Agent with a real contact.
UA = "OpenCairn-itinerary-map/1.0 (+https://github.com/OpenCairn/OpenCairn)"
WALK_KMH = 4.8  # average city walking speed


class GeocodeNetworkError(Exception):
    """A live geocode request failed to reach/parse Nominatim (transient — retryable),
    as distinct from a successful request that returned no match (a genuine miss)."""


# ---- geocoding ------------------------------------------------------------
def load_cache():
    try:
        with open(CACHE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def geocode(query, cache, allow_network):
    key = query.strip().lower()
    if key in cache:
        return cache[key]
    if not allow_network:
        return None
    params = urllib.parse.urlencode({"q": query, "format": "json", "limit": 1})
    req = urllib.request.Request(f"{NOMINATIM}?{params}", headers={"User-Agent": UA})
    time.sleep(1.1)  # throttle BEFORE every live request (Nominatim <=1 req/s) — fires on errors too
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
    except Exception as e:  # network/parse failure is retryable — distinct from an empty result
        raise GeocodeNetworkError(str(e))
    if not data:
        return None
    hit = {"lat": float(data[0]["lat"]), "lon": float(data[0]["lon"]),
           "display": data[0].get("display_name", "")}
    cache[key] = hit
    return hit


def resolve_coords(stop, region, cache, allow_network):
    """Return (lat, lon, source) or (None, None, reason)."""
    if "lat" in stop and "lon" in stop:
        return float(stop["lat"]), float(stop["lon"]), "manual"
    q = stop.get("query") or stop["name"]
    if region and region.lower() not in q.lower():
        q = f"{q}, {region}"
    try:
        hit = geocode(q, cache, allow_network)
    except GeocodeNetworkError as e:
        sys.stderr.write(f"  ! NETWORK error geocoding {q!r}: {e}\n")
        return None, None, "NETERR"
    if hit:
        return hit["lat"], hit["lon"], "osm"
    return None, None, "UNRESOLVED"


# ---- routing --------------------------------------------------------------
def haversine_km(a, b):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def order_stops(start, stops):
    """Anchors (with 'fixed') keep time order; free stops cheapest-inserted.

    `stops` items must already carry 'lat'/'lon'. `start` is the seed position
    (may be None — then the first anchor/stop seeds the path)."""
    def _fixed_minutes(s):  # "9:30"/"09:30" → 570; sort by time, not lexically
        h, m = (s["fixed"].split(":") + ["0"])[:2]
        return int(h) * 60 + int(m)

    anchors = sorted([s for s in stops if s.get("fixed")], key=_fixed_minutes)
    free = [s for s in stops if not s.get("fixed")]

    route = []
    if start is not None:
        route.append(start)
    route.extend(anchors)
    if not route:  # no start, no anchors → seed with first free stop
        if free:
            route.append(free.pop(0))

    def pos(s):
        return (s["lat"], s["lon"])

    for f in free:
        best_i, best_cost = None, None
        # candidate gaps: after each existing node (never before a real start[0])
        lo = 1 if start is not None else 0
        for i in range(lo, len(route) + 1):
            prev = route[i - 1] if i > 0 else None
            nxt = route[i] if i < len(route) else None
            if prev is not None and nxt is not None:
                cost = (haversine_km(pos(prev), pos(f)) + haversine_km(pos(f), pos(nxt))
                        - haversine_km(pos(prev), pos(nxt)))
            elif prev is not None:
                cost = haversine_km(pos(prev), pos(f))
            else:
                cost = haversine_km(pos(f), pos(nxt))
            if best_cost is None or cost < best_cost:
                best_cost, best_i = cost, i
        route.insert(best_i, f)
    # `start` is only the routing seed — emitters take it separately, so it must not
    # come back as a numbered stop (else it double-emits and inflates the count).
    return route[1:] if start is not None else route


# ---- emit -----------------------------------------------------------------
def walk_minutes(km):
    return round(km / WALK_KMH * 60)


def build_kml(day, ordered, start):
    def placemark(n, s, leg_km):
        name = escape(f"{n} · {s['name']}" + (f" ({s['time']})" if s.get("time") else ""))
        desc_lines = []
        if s.get("query"):
            desc_lines.append(escape(s["query"]))
        if s.get("notes"):
            desc_lines.append(escape(s["notes"]))
        if leg_km is not None:
            desc_lines.append(f"↳ {leg_km:.1f} km / ~{walk_minutes(leg_km)} min walk from previous")
        desc = "<br/>".join(desc_lines)
        return (f'    <Placemark>\n      <name>{name}</name>\n'
                f'      <description>{desc}</description>\n'
                f'      <Point><coordinates>{s["lon"]},{s["lat"]},0</coordinates></Point>\n'
                f'    </Placemark>')

    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<kml xmlns="http://www.opengis.net/kml/2.2">', '  <Document>',
             f'    <name>{escape(day)}</name>']
    if start is not None:
        parts.append('    <Placemark>\n      <name>★ Start · ' + escape(start["name"])
                     + '</name>\n      <Point><coordinates>'
                     + f'{start["lon"]},{start["lat"]},0</coordinates></Point>\n    </Placemark>')
    prev = start
    for i, s in enumerate(ordered, 1):
        leg = haversine_km((prev["lat"], prev["lon"]), (s["lat"], s["lon"])) if prev else None
        parts.append(placemark(i, s, leg))
        prev = s
    # route line
    line_pts = ([start] if start else []) + ordered
    coords = " ".join(f'{p["lon"]},{p["lat"]},0' for p in line_pts)
    parts.append('    <Placemark>\n      <name>Route</name>\n'
                 f'      <LineString><coordinates>{coords}</coordinates></LineString>\n'
                 '    </Placemark>')
    parts.append('  </Document>\n</kml>\n')
    return "\n".join(parts)


def build_daysheet(day, ordered, start, unresolved):
    total = 0.0
    rows = []
    prev = start
    for i, s in enumerate(ordered, 1):
        leg = ""
        if prev:
            km = haversine_km((prev["lat"], prev["lon"]), (s["lat"], s["lon"]))
            total += km
            leg = f" · {km:.1f} km/{walk_minutes(km)}min"
        t = f"**{s['time']}** " if s.get("time") else ""
        note = f" — {s['notes']}" if s.get("notes") else ""
        # Plain bold name + a copyable `geo:` code-span — a markdown link breaks on a
        # name containing ] or ), and Obsidian mobile has no geo: tap-handler anyway.
        rows.append(f"{i}. {t}**{s['name']}**{note} · `geo:{s['lat']},{s['lon']}`{leg}")
        prev = s
    out = [f"# {day} — map day-sheet", ""]
    start_txt = f" from {start['name']}" if start else ""
    out.append(f"**{len(ordered)} stops{start_txt} · ~{total:.1f} km on foot total.** "
               f"Open `{day}` in Organic Maps for the pins.")
    out.append("")
    out.extend(rows)
    if unresolved:
        out += ["", "> [!warning] Unresolved coordinates (geocode these on-device in Organic Maps):",
                "> " + ", ".join(unresolved)]
    out += ["", "*Distances are straight-line (crow-flies) — they ignore rivers, blocks and "
            "metro, so a leg crossing water or a barrier is longer on foot than shown.*",
            "*Geocoding © OpenStreetMap contributors (Nominatim).*"]
    out.append("")
    return "\n".join(out)


# ---- main -----------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--no-network", action="store_true",
                    help="cache-only; never call Nominatim")
    args = ap.parse_args()

    with open(args.input) as f:
        spec = json.load(f)

    region = spec.get("region", "")
    cache = load_cache()
    unresolved = []

    start = spec.get("start")
    if start:
        lat, lon, src = resolve_coords(start, region, cache, not args.no_network)
        if lat is None:
            sys.stderr.write(f"  ! start point unresolved: {start['name']}\n")
            start = None
        else:
            start["lat"], start["lon"] = lat, lon

    stops = []
    for s in spec["stops"]:
        lat, lon, src = resolve_coords(s, region, cache, not args.no_network)
        if lat is None:
            unresolved.append(s["name"])
            hint = ("NETWORK (transient — re-run)" if src == "NETERR"
                    else "UNRESOLVED — supply lat/lon manually")
            sys.stderr.write(f"  ! {hint}: {s['name']}\n")
            continue
        s["lat"], s["lon"], s["_src"] = lat, lon, src
        stops.append(s)
    try:
        save_cache(cache)
    except OSError as e:
        sys.stderr.write(f"  ! could not write geocode cache ({e}); continuing\n")

    if not stops:
        sys.stderr.write("No resolvable stops. Aborting.\n")
        sys.exit(1)

    ordered = order_stops(start, stops)

    os.makedirs(args.outdir, exist_ok=True)
    slug = spec.get("slug", "itinerary")
    kml_path = os.path.join(args.outdir, f"{slug}.kml")
    sheet_path = os.path.join(args.outdir, f"{slug}-daysheet.md")  # slug → no em-dash in filename

    with open(kml_path, "w", encoding="utf-8") as f:
        f.write(build_kml(spec["day"], ordered, start))
    with open(sheet_path, "w", encoding="utf-8") as f:
        f.write(build_daysheet(spec["day"], ordered, start, unresolved))

    print(f"KML:       {kml_path}")
    print(f"Day-sheet: {sheet_path}")
    print(f"Order:     " + " → ".join(s["name"] for s in ordered))
    if unresolved:
        print(f"UNRESOLVED ({len(unresolved)}): " + ", ".join(unresolved))


if __name__ == "__main__":
    main()
