---
name: audit
aliases: [review, code-audit, code-review]
description: Rigorous evaluation of any implementation - code, config, plans, processes, systems
---

# Audit - Rigorous Implementation Review

You are auditing an implementation. This applies to anything with logic and structure: code, infrastructure, configurations, plans, processes, decision frameworks, workflows.

## Philosophy

**Zoom out before zooming in.** Most review effort goes to implementation details (step 4), but steps 1-3 are higher leverage and get skipped by default. A perfectly implemented wrong approach is still wrong.

**Iterate until clean.** Every fix changes the system — re-audit after each fix. A single-pass audit is just a bug report. Keep going until a full pass finds nothing.

## Instructions

### Phase 1: Identify the Target

1. **If the user specified what to audit**, load it.
2. **If not**, ask: "What should I audit?" — don't guess.
3. **Read the full implementation** before forming opinions. No drive-by observations.

### Phase 2: Five-Layer Audit

Work through these layers in order. Each layer can invalidate everything below it, so don't skip ahead.

#### Layer 1: Is the approach right?

Before examining how it's built, ask whether it *should* be built this way.

- Does this solve the actual problem, or a proxy of it?
- Are there simpler approaches that weren't considered?
- Does the architecture match the constraints (scale, maintainability, who will operate it)?
- Is there unnecessary complexity? (Premature abstraction, over-engineering, speculative features)

#### Layer 2: What's the operating environment?

The implementation doesn't exist in isolation. What surrounds it matters.

- For code: runtime, dependencies, network paths, resource contention, competing workloads
- For plans: who executes, what resources exist, what's the timeline, what else is in flight
- For processes: who are the actors, what are their incentives, where does friction live
- For config: what reads this, what else touches these settings, what's the failure mode

#### Layer 3: What existing state needs to migrate or integrate?

Change always meets existing reality. What's already there?

- What does this replace or modify? What breaks if the old thing disappears?
- Are there consumers/dependents that expect the current interface/format/behavior?
- Is there data, state, or configuration that needs to carry forward?
- For plans/processes: what habits, expectations, or workflows does this disrupt?

#### Layer 4: Is the implementation correct?

Now zoom in. Evaluate the actual work product.

- For code: logic errors, edge cases, error handling, security (OWASP top 10), naming, readability
- For plans: gaps in sequencing, missing dependencies, unrealistic assumptions, unowned tasks
- For processes: missing steps, ambiguous responsibilities, no feedback loops, single points of failure
- For config: typos, wrong values, missing entries, inconsistencies with documentation

#### Layer 5: Does it actually work?

Theory vs. reality. Can you verify it runs?

- For code: run it, run tests, check for obvious runtime failures
- For plans: trace through a concrete scenario end-to-end — does it hold up?
- For processes: simulate the first execution — where does someone get stuck?
- For config: validate syntax, check that referenced paths/services exist

### Phase 3: Report Findings

4. **Present findings by layer**, not as a flat list. This makes severity obvious — a Layer 1 finding ("wrong approach") outranks ten Layer 4 findings ("minor bugs").

5. **For each finding, state:**
   - What's wrong (specific, no hedging)
   - Why it matters (consequence if left unfixed)
   - Suggested fix (concrete, not "consider improving")

6. **If no findings at a layer**, say so explicitly. "Layer 3: No migration concerns — this is net-new with no existing dependents."

### Phase 4: Fix and Re-audit

7. **If fixes are possible and authorised**, make them.
8. **After each round of fixes, re-audit from Layer 1.** Fixes can introduce new issues or invalidate prior findings.
9. **Repeat until a full pass is clean.** Then report: "Clean pass — no further findings."

## Guidelines

- **Specificity over breadth:** Five specific findings beat twenty vague observations.
- **No hedging:** "This will fail when X" not "This might potentially have issues with X."
- **Severity is implicit in the layer:** Don't add separate severity labels — Layer 1 findings are inherently more important than Layer 4.
- **Don't pad:** If the implementation is solid, say so. "Clean pass" is a valid audit result.
- **Scope to what was asked:** Audit the target, not the surrounding codebase. Flag adjacent concerns briefly if they're blocking, but don't expand scope without asking.

---

**Skill monitor:** Also follow the instructions in `.claude/commands/_skill-monitor.md`.
