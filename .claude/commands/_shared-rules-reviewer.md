# Shared Rules — Reviewer

Read only the numbered sections needed for the current operation. Core rules and the global section directory are in [_shared-rules.md](_shared-rules.md), in this same directory. Section numbers retain their original meaning; resolve a cross-file `§N` there and read its procedure before using it. These are instructions shared by skills, not an independently invoked workflow.

---

## 10. Invoking Gemini & Codex (CLI sandbox, vision, panel despatch)

Gotchas that bite any skill calling the `gemini`/`codex` CLIs, plus the canonical read-only despatch block — the **single source of truth** for these commands; `/audit` and `/second-opinion` point here rather than carrying their own copies.

- **Gemini file reads are sandboxed to the workspace = the cwd it was launched from** (plus its project temp dir `~/.gemini/tmp/<hash>`) — NOT the home directory. Verified 2026-06-11 on gemini 0.40.1: launched from `~`, a read of `/tmp/<file>` fails "Path not in workspace"; launched from `/tmp`, a read under `~` fails the same way. Three remedies: launch from the target's root; pass `--include-directories <root>` (verified to extend the workspace); or **pipe text via stdin** — `cat <file> | gemini -p "..."` — so the sandbox never applies to the brief itself. Headless gemini also **hard-refuses to start in an untrusted directory** ("not running in a trusted directory") — when despatching from outside your trusted set, set `GEMINI_CLI_TRUST_WORKSPACE=true` or pass `--skip-trust`.
- **Vision/OCR via the CLI is unreliable** — it may not pass an image as a true vision input and frequently refuses outright ("I cannot perform OCR for handwriting"). For any image task, **bypass the CLI and call the REST API** (`generativelanguage.googleapis.com/.../generateContent`) with inline base64 and `GEMINI_API_KEY` (set in env and `~/.gemini/.env`). Python stdlib `urllib` is enough — no SDK install.
- **Keep Gemini read-only with a `--policy` file, not `--approval-mode plan`** — `plan` blocks `run_shell_command` but still exposes the `replace`/`write_file` edit tools, so a skill that briefs Gemini to propose changes can have them written straight into the target. Verified on gemini 0.40.x: a deny-rule policy strips the named tools from the model entirely (it reports them "not found") while reads stay intact — a hard guarantee. The policy file needs **no `.toml` extension** (verified 0.40.1), so create it with portable `mktemp` — GNU-only `--suffix` breaks BSD/macOS. **Don't** put the file in `~/.gemini/policies/` (auto-loaded for *every* invocation → would make all gemini sessions read-only); use an explicit temp path. After a panel run, check whether the reviewer **attempted** an edit: if it did, it must have reported the tool "not found"/unavailable — an edit that *succeeded* means the policy didn't load; treat the run as contaminated. A clean review with no edit attempt produces no such report (the tools are only reported missing when called) — for that case, and on the no-`--policy` fallback, the `git status`/snapshot backstop is the verification.
- **Canonical read-only panel despatch block.** The Claude seat is the Agent tool with the brief contents verbatim as its prompt; the CLI seats run via Bash with `timeout: 1500000` passed as the **Bash-tool argument** on each call (it is not a shell flag — the default 120s kills reviewers mid-review):

  ```bash
  RO_POLICY=$(mktemp -t gemini-ro-policy.XXXXXX)   # portable: no --suffix, no .toml needed
  printf '[[rule]]\ntoolName = ["write_file", "replace", "run_shell_command"]\ndecision = "deny"\npriority = 100\n' > "$RO_POLICY"
  # Each CLI call below: pass timeout 1500000 as the Bash TOOL argument (not a shell flag)
  cat <brief> | gemini -p "Follow the instructions in the piped input exactly." --policy "$RO_POLICY" -o text --include-directories <root>
  cat <brief> | codex exec --sandbox read-only --skip-git-repo-check -C <root> -
  ~/.claude/scripts/xai_client.py --panel-review <brief> --source <target> [--source <target> ...]
  ```

  `--include-directories <root>` / `-C <root>` point the seats at the target's root; drop them when the target sits under the despatch cwd. Session-handle capture, auth caveats, and fallback invocations stay in `second-opinion.md` Phase 2A.

- **Headless `gemini -p` has no shell tool at all — this is not the `--policy` file's doing.** Verified on gemini 0.40.1 by despatching with *no* `--policy` flag and asking the model to enumerate its own toolset: `update_topic, list_directory, read_file, grep_search, glob, google_web_search, enter_plan_mode, invoke_agent`. `run_shell_command` is absent. So the deny-rule above is belt-and-braces for shell rather than its cause, and **loosening the policy does not buy an executing Gemini seat** — the seat can read, grep and glob, nothing more. Codex is the CLI seat that *can* run commands: `--sandbox read-only` blocks writes, not execution. Two traps: seeing `Tool "run_shell_command" not found` and blaming your own policy (costs a redundant despatch to disprove), and briefing a Gemini seat to "run the tests" — it cannot, so per the pre-flight below the orchestrator runs them and embeds the receipts.

- **Seats do not verify equally, and the read-only measure is what causes the gap.** Where a CLI offers a filesystem-level read-only sandbox, the seat keeps shell and can check a claim against local man pages, config and unit files. Where no read-only sandbox or command-level policy is available, the remaining option is to deny the shell tool outright (shell *is* a write path: `echo > file`) — which also removes that seat's ability to verify anything locally. Classify each seat by the outcome, not by the product: whichever seats end up shell-denied under your despatch config are the ones that cannot verify. Two consequences to design around, not fix:
  - **A shell-denied seat's findings skew toward the unverifiable.** In a tiebreak, its unique claim about a flag, key or path carries less evidential weight than the same claim from a seat that could run the command. Weigh by what the seat could actually check; don't count votes.
  - **A seat whose only evidence route is the network fails wholesale when that route degrades**, producing no output rather than a weaker review. Silence from such a seat is a transport failure, never endorsement — announce it as a reduced panel.

  **Remedy — a pre-flight, and it is the orchestrator's job.** Before despatch, not after: if any seat is shell-denied and the review turns on anything a shell would settle (a flag's behaviour, a config key, whether a path exists, what a command actually prints), run those checks yourself and embed the output under §16's out-of-band heading. For a shell-denied seat, "material the reviewer cannot reach from the artefact" includes everything behind a shell, so omitting it reproduces §16's partial-evidence false positives in that seat specifically. Doing it afterwards does not help — by then the seat has already guessed, and you are adjudicating its guess instead of preventing it. Every skill despatching a mixed-capability panel runs this as a step in its own pre-despatch sequence and points here rather than restating it.

- **The Grok seat is an API seat, not a CLI seat — it reads nothing.** `xai_client.py` posts to xAI's Responses API over stdlib `urllib`; it has no filesystem access, so the target must be passed with `--source` and is inlined into the prompt as a delimited appendix. Three consequences that the other two seats don't have:
  - **Manifest in place of a read-list.** The wrapper appends each source as `path | bytes | sha256` and instructs the seat to reproduce that manifest verbatim and quote what it relied on. That manifest is this seat's evidence standard — the attestation rule (**§23**) is satisfied by the manifest, not waived. §23 carries the enforcement test; note it requires manifest **and** quoted passages, so supplying only one fails.
  - **Size cap, fail-closed.** `MAX_INLINE_BYTES` (400 KB, ~100k tokens — kept under xAI's >200k-token tier where the per-token rate doubles). Over the cap the wrapper raises and the seat is **dropped with the reduced panel announced**; it never silently truncates, because a truncated appendix produces confident findings about text the seat never saw.
  - **Availability probe is `--probe`, not `--version`.** There is no binary: `xai_client.py --probe` exits 0 when it resolves `XAI_API_KEY`, 1 otherwise. Resolution checks the process environment first, then `~/.claude/settings.json` `env.XAI_API_KEY`; the fallback lets the Codex port use Claude Code's existing credential without duplicating the secret into Codex config. Probe *before* despatch — an unavailable key must degrade to a reduced panel up front, not fail mid-run.

  The wrapper sets `store: false` (xAI otherwise retains responses server-side for 30 days) and never enables live search on a review call. `store: false` forecloses `previous_response_id` threading, which is why the Grok seat has no true resume — round 2 replays prior context. **xAI does not train on API inputs or outputs by default** — its API security FAQ states it "never trains on your API inputs or outputs without your explicit permission," so training is opt-in, not opt-out. The "improve the model" toggle is the *consumer* Grok control, not a developer-API setting; there is nothing to switch off. What does apply: API requests and responses are retained 30 days, encrypted at rest, for abuse auditing. `store: false` governs stateful threading, not that audit window. Zero Data Retention eliminates it but is team-level and disables the stateful Responses API, Files, Collections, Batch, and per-key logging — don't enable it for this.

- **Seat tiering (Claude seats).** Judgment and generation seats — anything whose errors propagate invisibly or whose output *is* the deliverable — run on the despatching session's model; do not downgrade them. Verification and mechanical seats — audits of work the session already did, bounded-failure checks whose misses are caught downstream — may pin to a strong-but-cheaper tier via the Agent tool's `model` argument (e.g. `model: opus`). A pin is declared at the despatch site in the despatching skill, with its reason stated, and never sits below the Opus tier without an explicit per-skill justification. **A pin is a floor, not a discount:** it only reduces spend when the despatching session is running something more expensive, is a no-op when the parent is already at the pinned tier, and *raises* cost against a cheaper parent. Justify a pin by the capability the seat needs, not by an assumed saving. This tiering governs Claude Agent-tool seats only; the CLI/API seats' models resolve per the bullet below.

- **Seat model resolution (for currency checks).** Each seat resolves its model a different way, and the answer lives in config or a live probe, never in memory: the **Claude seat** floats with the despatching session's model by default; seats pinned under the seat-tiering rule above declare `model:` at their despatch site — resolve pins by grepping the command files (`rg -n "model: (opus|sonnet|haiku)" <commands dir>`); the **Gemini seat** reads `model.name` in `~/.gemini/settings.json` — and for a model the installed CLI does not register natively, the `modelConfigs.aliases` entry keyed to that exact name (re-key both together: a mismatched key silently drops the alias and its thinking level while the served model still reads correct); the **Codex seat** reads the `model` key in `~/.codex/config.toml`, falling back to the CLI's built-in default when unset — probe the resolved default live (a minimal `codex exec` call prints `model:` in its preamble) and record the CLI version, since an unpinned seat is only as current as its last CLI update; the **Grok seat**'s models are the constants at the top of `xai_client.py`, checked against the provider's models endpoint (`GET https://api.x.ai/v1/models`, using the key resolved by the client). Consumed by `/quarterly-hygiene`'s model-currency step; update here, not there, when a CLI moves its config.

---

## 16. Out-of-Band Evidence in Reviewer Briefs

Canonical rule for every skill that despatches a brief to a reviewer that cannot see this session — `/park`'s audit sub-agent, `/audit`'s panel seats, `/second-opinion`'s reviewers, and any non-template skill that despatches a brief (e.g. a private review skill of your own). Those skills point here and carry no copy to drift.

**The rule.** Where the work product's claims rest on material the reviewer cannot reach from the artefact itself — web fetches, emails, API results, tool output, the user's pasted text — embed that material in the brief, verbatim, under a heading that marks it established: `## Out-of-band evidence (treat as given — do NOT flag as fabricated)`.

**Tag each excerpt's provenance — `[primary]`, `[secondary]`, or `[unverified]`** — and state under the heading what "given" licenses: *these excerpts are real and were genuinely gathered, so do not report them as fabricated; their **content** is still open to challenge, and anything tagged `[secondary]` or `[unverified]` especially so.* `[primary]` is the authority itself (vendor docs, the API's own response, the source file); `[secondary]` is someone reporting on it (a news write-up, a third-party guide, another model's summary); `[unverified]` is an assertion you carried in without checking, including one inherited from the artefact under review.

**Why the tags.** Without them this rule inverts: the heading that stops false positives starts manufacturing false negatives. An unverified claim embedded as "given" is immune to the panel — every seat is instructed not to question it, so a wrong premise emerges from review wearing four models' endorsement, and the tiebreak reads the silence as agreement. Correlated agreement is already weak evidence; agreement you *instructed* is no evidence at all. The tag is what keeps "don't call this invented" from collapsing into "don't think about this." Caught 2026-07-19: a third-party guide's claim about a vendor's data-handling defaults went into a brief untagged, survived a full tri-model audit unchallenged, and was false — the primary source said the opposite.

**Checkable:** every excerpt under the heading carries one of the three tags. An untagged excerpt is a claim you are asserting on your own authority — either verify it and tag it `[primary]`, or tag it `[unverified]` and let the panel do its job.

**Why.** A reviewer confined to the artefact cannot distinguish *"sourced from evidence you withheld"* from *"invented"*, so it reports the first as fabrication. Each false positive costs a round-trip to adjudicate and discredits the true findings beside it. In a panel it is worse: one omitted source produces a false positive *per seat*, and the synthesis then reads convergent fabrication findings as corroboration when they are one shared artefact of your own brief.

**Embedding most of the sources is the trap.** Partial evidence yields *confident, specific* false positives exactly on the claims whose source you omitted — and the omitted one skews toward the **originating** source (the report or message that began the work), because by brief-writing time your attention has moved to whatever you fetched later while correcting it.

### Deriving N — never from recollection

The count is the mechanism, and it only works if it is anchored **outside the attention that failed**. An agent that dropped a source while writing will drop it again while counting, then emit a self-consistent `3 → 3` and pass while short. So do not count "what I drew on". Derive N from two artefacts:

1. **The work product's own citation/source section** — every distinct external item it names. A secondary report is a **distinct source** from the primary it reports on.
2. **A sweep of this session's fetch/read tool calls** — every URL fetched, file read, email opened, paste received that fed a claim. This is the half that catches what a note *never cites*: pasted text, tool output, emails.

N is the union. Display before despatch:

```
Out-of-band evidence: sources drawn on N → excerpts embedded N
```

A short count means the brief is incomplete, not the work wrong.

### Scope, size, and the seats

- **"Relevant text" means the passages the claims rest on** — not whole documents. Quote the load-bearing passage; cap each source at roughly 500 words.
- **Mind the transport.** `/audit` and `/second-opinion` pipe the brief into CLI seats with differing context windows, under a requirement that the payload be identical across seats. An uncapped dump can silently truncate in one seat — reproducing the partial-evidence false positives this rule exists to prevent, now invisibly. If the evidence exceeds the budget, attach it as a file path all seats can read (§10's `--include-directories` / `-C`) rather than inlining it.
- **Coverage is per claim:** include each supporting passage, including earlier excerpts from a source fetched again, action confirmations and relevant limitations. Reconcile the source union immediately before despatch with later tool results and user corrections. Name failed retrievals as partial coverage; source-count equality cannot prove completeness.
- **Conflicting sources:** where two disagree and the work picked one, say which won and why — otherwise the reviewer re-litigates a settled question.

### A never-opened citation is closed by opening it, not by declaring it

Where the work product cites a source the session never opened, **open it before despatch.** Declaring the gap in the brief does not neutralise it — it *aims* every seat at the same hole. Each reviewer then reasons from the same absent evidence to the same conclusion, and the synthesis reads that convergence as corroboration when it is a single artefact of your own brief. Adding seats cannot detect this, because the seats are the mechanism.

The cost is asymmetric. A claim gets challenged precisely where its support looks thinnest, so the source you skipped is disproportionately the one that would settle whatever the panel disputes. The unanimous verdict a disclosed gap produces is therefore not merely unsupported — it is the verdict most likely to be wrong, arriving with the most confidence behind it.

This is also a bar on the work product, not only on the brief: an artefact should not cite what it never opened. Repairing the citation list before review is far cheaper than adjudicating every seat's guess about it afterwards.

**Checkable:** every citation in the work product's reference list has a corresponding fetch or read in the session *before* the brief is written. Where a source genuinely cannot be opened, record the **failure mode** (dead link, paywall, auth wall, unparseable format) rather than the fact that it was untried — a tested failure is evidence a reviewer can reason from; an untried link is a gap that manufactures one.

### When a source is unrecoverable

If a source's text has left context (a long session, a `/compact` — and the first thing lost is the earliest fetch, which this rule identifies as disproportionately the originating source), **re-fetch it**. If it cannot be recovered, say so in the brief under the same heading — `<source> — text unavailable; do NOT flag claims traced to it as fabricated` — and **still count it in N**. Never paraphrase it from memory (that manufactures the fabricated-quote failure), and never drop it silently (that is the original failure, reproduced).

---

## 20. Session-Boundary Attribution (the file list is the boundary, not the commit window)

Canonical rule for every skill that delegates an audit over "the files this session touched" — `/park` Step 9, `/goodnight` Step 15(c). Those skills point here and carry no copy to drift; each supplies its own embedded file list.

**The rule.** The vault's `.git` is an **auto-save** repo: commits are time-window snapshots, not session boundaries, and concurrent sessions write to the same vault. A file appearing in the same commit as a session's bookkeeping is therefore **not** evidence that session produced it.

Attribute work **only** from the file list embedded in the brief. A changed file that is not on that list belongs to a concurrent session: surface it as an observation, and never

- add it to `Files Created` / `Files Updated`,
- open a `Next Steps` loop or `Pickup Context` thread for it, or
- write a Session History row for it in another project's hub.

**Partial application is the failure mode.** Applying the test to some files in a commit and not others produces a confident, internally consistent record of work the session did not do — which is harder to detect than an obvious error, because every individual claim reads as plausible and the record is self-consistent. When unsure whether a file is in scope, say so in the report rather than deciding.

**Checkable:** every file the auditor writes into a session record appears in the brief's embedded file list. One that doesn't is misattribution, whatever the commit history shows.

Caught 2026-07-19: an audit sub-agent correctly excluded two files from a commit window as concurrent work, then attributed a 194-line project file from the *same* window to the session, and wrote four separate false records off the back of it — a Files Created entry, an open loop, a Pickup Context thread, and a Session History row in an unrelated project hub.

The read-side sibling is `_shared-patterns.md`'s *Auto-save git is not pre-state*: that one governs using auto-save history to reconstruct what a file looked like before; this one governs using it to decide who did what.

---

## 23. Reviewer Evidence Attestation (a review counts only as far as it shows its work)

Canonical rule for every skill that despatches a review to a reviewer whose tool calls you cannot see — panel seats, delegated audit sub-agents, any brief sent to a separate context. Those skills point here and carry no copy to drift. §16 governs what evidence *you* must put **into** a brief; this section governs what evidence the reviewer must return **out** of one.

**The rule.** A reviewer's working is invisible to you, so a review is evidence only to the extent it attests where its claims came from. Require the attestation in the brief's output-format section, and enforce it on receipt. The artefact differs by what the seat can reach; the standard does not:

| Seat can reach | Required attestation |
|---|---|
| The filesystem | The list of files it read |
| A shell | For each command-backed claim: the exact command and the quoted output |
| The network | For each fetched-source claim: the URL and the quoted passage |
| Nothing (sources inlined into its prompt) | The source manifest reproduced verbatim, **and** the passages it relied on |

A seat owes every row its reach covers, not one of them. **Paste this table into the brief body — do not point the reviewer at this file.** A reviewer's workspace is the audit target, which is rarely the directory holding these rules, so a bare cross-reference is an instruction it cannot follow, and discarding it on receipt then punishes a competent review for a rule it never saw.

**Enforcement.** A review attesting nothing is brief-echo, not independent judgement — discard it and say so in the synthesis rather than quietly running an N-1 panel labelled as N. Partial attestation is not discarded wholesale: the unattested claims are reported as unverified and never promoted to findings on the reviewer's say-so. Where a row requires two artefacts, missing either fails that claim; the test is not "neither was supplied".

**Snapshot locators:** record absolute paths, or an explicit base directory and resolve relative entries against it. Verify against that same root before applying a review fix.

**Attestation is a locator, not a proof — spot-check before promoting.** A citation is as forgeable as the claim it supports, so an unchecked URL-and-quote does not merely fail to help, it actively inverts the ranking below: a fabricated primary source outranks an honest "from recall". Before promoting any fetched-source or command-backed finding that changes what you do, verify it yourself — open the URL and match the quote, or re-run the command. If you cannot, carry the finding as `[unverified]` at its unattested rank. The attestation's job is to make the check cheap and targeted, not to substitute for it.

**Do not solve the invisibility problem by cutting off the reach.** A seat that can search will sometimes locate the primary source you did not know to put in the brief, which is precisely the discovery a fixed evidence block cannot supply and the reason an independent seat is worth its cost. Removing the capability removes the upside along with the risk. Attestation keeps both: the seat may go looking, and you can see what it came back with.

**Evidence class is the tiebreak, and it outranks seat count.** Rank a finding by what backs it: a command the reviewer ran, then a primary source it quoted, then a secondary source, then unattested assertion. A lone finding carrying a quoted primary source outranks a majority reasoning from recall, and on a question of how a tool actually behaves, the seat that ran the command or read the source wins regardless of how many disagree. Correlated agreement is weak evidence to begin with (models share priors); agreement with nothing behind it is none. This is what makes attestation load-bearing rather than bookkeeping — without it the classes are indistinguishable, and a confident guess reads exactly like a verified fact.

**Checkable:** every brief a skill despatches names the required attestation for the seats it is despatching to, and every finding carried into a synthesis is traceable to a read, a manifest entry, a command, or a citation.

---
