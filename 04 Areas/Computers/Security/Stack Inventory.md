# Stack Inventory

The canonical list of what you actually run, used by the `/landscape-scan cybersec` profile as the allow-list for its exposure pass — a disclosed vulnerability matters only if it reaches something on this list. **Fill in the `[unknown — fill in]` placeholders before your first cybersec scan.** Until a field is filled, the scan treats it as an inventory gap and classifies related findings *Monitor — inventory refresh required* rather than guessing exposed or not-exposed.

For each entry, record **what it is, the installed version, and how it's exposed** (network-facing / local-only / physical). Version + exposure are what turn a CVE into "patch now" vs "doesn't reach me".

> Convention: keep this in sync with reality — a stale version here produces wrong exposure verdicts. The profile re-checks live versions (`dpkg-query`, `uname -r`, admin UIs) for patch decisions, but uses this list to know *what to check*.

## OS / kernel

- **Distro + version:** [unknown — fill in] — e.g. `lsb_release -ds`
- **Kernel:** [unknown — fill in] — e.g. `uname -r`
- **Exposure:** local workstation / server reachable on LAN / internet-exposed — [unknown — fill in]

## NAS + its apps

- **NAS OS + version:** [unknown — fill in] (e.g. TrueNAS SCALE 24.x)
- **Apps / services running on it:** [unknown — fill in] (each with port + whether LAN-only or exposed)
- **Exposure:** [unknown — fill in]

## Router / network gear

- **Router model + firmware:** [unknown — fill in]
- **Other network gear** (switches, APs, VPN endpoints): [unknown — fill in]
- **Exposure:** WAN-facing admin? remote-access services? — [unknown — fill in]

## Browsers

- **Primary browser + channel:** [unknown — fill in] (e.g. Firefox ESR, Chrome stable)
- **Exposure:** the main untrusted-content surface — note extensions that widen it

## Security-critical packages

Packages whose compromise is high-impact (SSH, OpenSSL/TLS libs, sudo, container runtimes, password manager, anything network-listening):

- [unknown — fill in] — version + exposure
- [unknown — fill in] — version + exposure

## Vendor advisory URLs

Fill these from the gear named above so subsequent scans check them automatically (the `cybersec` profile's source list points here):

- **Distro security feed:** [unknown — fill in] (e.g. https://ubuntu.com/security/notices)
- **NAS vendor security page:** [unknown — fill in]
- **Router vendor security page:** [unknown — fill in]
