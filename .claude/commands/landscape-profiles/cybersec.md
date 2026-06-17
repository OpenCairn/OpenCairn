# Landscape Profile — Cybersecurity / Threat Intel

Threat-intelligence lens, not tool-adoption. Invoked via `/landscape-scan cybersec`. The question this profile answers is **"does a disclosed threat reach something the user actually runs, and what do they do about it?"** — not "should I adopt this tool." It complements an internal-posture security audit (what's misconfigured on the machine now — if you run one) by covering the external axis (what got disclosed that touches the stack).

**One-liner:** Cybersecurity threat intel — filter disclosures against the user's stack inventory; output exposure + action (patch now / cooldown / monitor), not adopt/skip.

## File naming

- Filename suffix: **`-cybersec`** (display form `YYYY-Www-cybersec.md`, e.g. `2026-W16-cybersec.md`).
- Prior-scan glob (executable): **`20[0-9][0-9]-W[0-9][0-9]-cybersec.md`**. Sort by mtime (`ls -t`).

## Contextualising reads

The whole profile pivots on **what the user actually runs**. Load, every run:

- **The stack-inventory doc** — `{VAULT}/04 Areas/Computers/Security/Stack Inventory.md` (the canonical list of OS/kernel, NAS + its apps, router/network gear, browsers, and security-critical packages, each with how it's exposed). This is the allow-list against which every finding's exposure pass runs — **the profile cannot do its core exposure pass without it.** If the doc is **missing entirely** (e.g. a fresh clone — there's nothing to refresh), stop and ask the user to create it first: a list of OS/kernel, NAS + its apps, router/network gear, browsers, and security-critical packages, each with how it's exposed. If the doc exists but **looks stale** (e.g. an OS version that no longer matches `lsb_release -ds`), say so in the report and offer to refresh it — don't assess exposure against a stale inventory.
- **The most recent internal security-audit output** (if one exists in `{VAULT}/04 Areas/Computers/Security/`) — tells you what's already been hardened/flagged, so a finding that the audit already covered is a cross-reference, not a fresh action.
- **Just-in-time:** if a finding touches a component whose current version matters, verify the installed version live (`dpkg-query -W -f='${Version}' <pkg>`, `uname -r`, NAS/app admin UI) rather than trusting the inventory's recorded version for a patch decision.

## Sources

Focus on what's new since the last cybersec scan. Threat intel has a faster cadence than tool news — a *critical* affecting the stack is same-day actionable, not a weekly-digest item; surface those immediately in the run, don't bank them.

**Authoritative advisories (primary sources — prefer these over news rewrites):**
- https://nvd.nist.gov/vuln/full-listing — NVD recent CVEs (filter to stack-relevant vendors/products)
- https://www.cisa.gov/news-events/cybersecurity-advisories — CISA advisories + KEV (Known Exploited Vulnerabilities) catalogue
- Your distro's security-advisory feed — e.g. https://ubuntu.com/security/notices (Ubuntu USN), RHEL errata, Arch security tracker — whichever maps to the stack inventory's OS
- https://www.openwall.com/lists/oss-security/ — oss-security list (upstream disclosures, often ahead of distro advisories)
- Vendor advisories for stack-specific gear: TrueNAS / iXsystems security page, the router vendor's firmware/security page (fill in per the stack inventory)

**Security news (secondary — use to surface, then chase to the primary advisory):**
- https://cybersecuritynews.com/ — broad coverage (good for surfacing items to then chase to a primary advisory)
- https://thehackernews.com/ — broad coverage
- https://www.bleepingcomputer.com/ — broad coverage, good on Linux/NAS/router items
- https://www.phoronix.com/ — Linux-specific (kernel, distro, package CVEs)

**Supply-chain watch (the user's own dependency surface):**
- Package-repo compromise reports relevant to what the user installs — npm/PyPI advisories, distro-repo incidents (AUR, etc.), Docker Hub image poisoning. A distro-repo incident matters only if the stack inventory runs that distro; otherwise it's informational.

If a source is unreachable, note it "unavailable" and flag in *Sources list updates*.

## Assessment frame

Two passes per finding. Run both, report both, never collapse to one verdict.

**Exposure pass — does it reach the stack?**
- Does the affected product/version appear on the stack inventory? Match on *product AND version range*, not product name alone — a CVE in versions < X doesn't touch the user if they run ≥ X. Verify the installed version live before claiming exposed.
- What's the *attack path*? Network-facing (listening service, internet-exposed) vs local-only (needs a malicious file opened) vs physical. A network-RCE on a service the user doesn't expose is far lower priority than the CVSS implies. (Illustrative example, not a live advisory: an FFmpeg AV1/RTP RCE that only fires on `ffmpeg -i rtsp://untrusted` is irrelevant to a user who only transcodes local files, critical to one running an RTSP-ingesting media server.)
- If it names a stack component, check it against the inventory — **don't assert exposure from a product-name match.**

**Action pass — what does the user do?**
- **Patch now** — exposed + (exploited-in-wild OR critical + reachable path). State the exact command/route (your distro's package update, e.g. `apt upgrade <pkg>`; NAS app update; router firmware update).
- **Cooldown-then-patch** — patch exists but it's a fresh package publish; apply the engine's supply-chain cooldown (the irony: a rushed security patch can itself be a poisoned publish). Give the date.
- **Monitor** — affects the stack but no patch yet, or exposure is conditional on something not currently true (e.g. an app the user might add later). State the trigger that would escalate it.
- **Not exposed — note** — on the stack but the version/path doesn't reach them, OR adjacent-but-not-on-stack. One line, so next scan doesn't re-surface it.

**Inventory gap — when the relevant component is a `[unknown — fill in]` placeholder or its version can't be live-verified** (e.g. router firmware, browser, NAS while offline): do **not** guess either way — never claim *exposed* (false alarm) or *not exposed* (false reassurance) against a blank. Instead classify **Monitor — inventory refresh required**, name the exact missing field(s), and continue the scan rather than stalling. For a finding whose vendor-advisory source is a stub: derive the vendor from the inventory entry and WebSearch its security page; if the entry itself is a placeholder so no vendor is known, log "vendor advisory URL + version needed for `<component>`" under *Sources list updates* — surfaced for fill-in, never silently dropped.

## Obsolescence check

**Value: does not run.** (Threat findings don't obsolete local skills.) The engine's Step 8 branches on this key's value, so it skips the step for this profile.

## Report sections

Insert these in place of the engine's `<<< PROFILE REPORT SECTIONS >>>` marker:

```markdown
## Patch now (exposed + actionable)
For each:
- **[CVE / advisory id] — [product @ affected versions]** — [what it is, link to primary advisory]
  - *Exposure:* [on stack? installed version vs affected range; attack path: network / local / physical]
  - *Action:* [exact command or route] — [supply-chain cooldown note if the patch is a fresh publish]

## Cooldown-then-patch
- **[id] — [product]** — [as above]
  - *Exposure:* …
  - *Action:* defer patch until YYYY-MM-DD (fresh publish + cooldown), then [command]

## Monitor (on stack, no action yet)
- **[id] — [product]** — [why no action now; the trigger that would escalate it]
  - *Exposure:* …

## Not exposed (logged so it isn't re-surfaced)
- **[id] — [product]** — [on stack but version/path doesn't reach; or adjacent-not-on-stack]

## Meta / landscape (no action — situational awareness)
- [Trends worth knowing that aren't stack-specific — e.g. AI agents finding 0-days at scale, a class of attack rising. Keep brief; this is the bucket for the interesting-but-not-actionable.]
```

Section counts for the Step 12 confirmation line: `N patch-now, N cooldown, N monitor, N not-exposed, N meta`.

## Notes for maintainers

- Keep this profile template-suitable: stack specifics live in the vault stack-inventory doc the profile *reads*, never hardcoded here. A different user drops in their own inventory and the profile works unchanged.
- The router/NAS vendor advisory URLs above are stubs — fill them from the actual gear named in the stack inventory on first real run, then record them here so subsequent runs check them automatically.
