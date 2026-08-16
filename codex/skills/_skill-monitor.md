# Skill Self-Improvement Monitor

As you execute this skill, watch for gaps. If you improvise a step that isn't documented, if a mistake could have been caught by a better checklist item, or if a documented step turns out unnecessary — note it.

At the end of the run, **log observations — do not propose skill edits in-session.** Contemporaneous proposals proved exhausting at every-session frequency; the log batches them into `$weekly-hygiene`, where recurrence across sessions is visible.

- **Something observed:** append one block to `{VAULT}/07 System/Skill Monitor Log.md` via the locked append (never a bare `>>`, never a raw editor write — concurrent sessions interleave otherwise). If no vault path is resolved this session, run `"$VAULT_PATH/.claude/scripts/resolve-vault.sh"` yourself first and substitute the resolved path below — this file may be loaded by skills that never read `_shared-rules.md`.

  **Duplicate preflight:** before appending, search the whole monitor with `rg -n -i -F` for the observation's distinctive mechanism (target script/step plus the failing behaviour). Same mechanism and same evidence → do not append. An independent run that materially strengthens the evidence → append one concise recurrence bullet naming the prior date and only what the new run adds.

```bash
{ printf '## %s — $<skill>\n' "$(date +%F)"; cat <<'EOF'
- [gap observed]: [specific suggested edit]
EOF
} | "{VAULT}/.claude/scripts/locked-edit.sh" "{VAULT}/07 System/Skill Monitor Log.md" --append
```

The fence and the heredoc terminator sit at column 0 deliberately — an indented `EOF` is not recognised as the delimiter, so the block must be run as written rather than nested under the bullet.

The heredoc delimiter is quoted deliberately: observation bullets routinely contain code-spans, `$vars`, and backticks that an unquoted heredoc would expand or execute.

The script creates the file if missing. One block per run; multiple observations are bullets under it. Keep each bullet to one or two lines — enough for the weekly pass to reconstruct the edit without this session's context — and name the target file/section when it isn't this skill's own file (e.g. a `_shared-rules.md` section). Date from `date +%F`, never internal computation.

Check the exit status before claiming success — a non-zero exit means the lock was never acquired and the observation was **not** written. On non-zero, retry the block once; if it fails again, display `✗ Skill monitor: log write failed — observation(s) below` and print the bullets in-session so they survive the run. Only on exit 0 display `✓ Skill monitor: N observation(s) logged`.

- **Nothing observed:** display the calling skill's existing clean-case line where its checklist demands a checkpoint (e.g. `✓ Skill monitor: No gaps detected`); otherwise silence is the clean case — don't let meta-maintenance intrude.
- **Sub-agents never write the log.** A sub-agent that spots a skill gap returns it as a finding in its report; the main session logs it.
- **Exception — broken-now failures:** if the gap made *this run's* output wrong, say so in-session (that's error reporting, not skill improvement); still log the skill-edit suggestion rather than proposing it.
- **No resolvable vault** (skill running outside a vault context): display `✓ Skill monitor: no vault — observation not logged` and move on. Do not fall back to in-session proposals.
