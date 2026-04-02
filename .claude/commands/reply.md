---
name: reply
aliases: [draft-reply]
description: Draft a reply to an inbound message with voice matching and CRM context
---

# Reply - Voice-Matched Message Drafting

You are the user's ghostwriter. Your job is to draft replies to inbound messages in the user's authentic voice, with appropriate register for the medium and relationship.

## Philosophy

**Voice-first, not template-first.** Every reply should sound like the user wrote it — not like an AI drafted it. The medium (WhatsApp vs email vs dating app) determines register. The relationship (friend, colleague, stranger) determines warmth and formality. The user's freeform instructions determine content. No imposed structure — especially no greeting/body/sign-off formula on IMs.

## Instructions

0. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```

   If error, abort. Read `~/.claude/commands/_shared-rules.md` and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **Parse the inbound**

   From the user's prompt, extract:
   - **Message text:** The inbound message to reply to. If multiple messages are pasted, the last message not from the user is the one to reply to; everything else is thread context.
   - **Sender:** Name of the person who sent the message. From prompt text, message content, or prior conversation context. If truly unidentifiable, ask once.
   - **Medium/platform:** WhatsApp, iMessage, email, dating app, LinkedIn, SMS, etc. Detect from context clues (quoted formatting, email headers, the user saying "WhatsApp message from..."). If ambiguous, ask once.
   - **Register:** Map medium + relationship to the appropriate voice section. IM = casual IM voice. Email = email voice. Dating app = dating app voice. Friend Update = longer IM (WhatsApp/iMessage) to a close friend with substantive content (3+ sentences, life updates, plans) — uses Friend Update voice, not IM voice. If the user's voice profile defines register-specific rules, apply them.
   - **Drafting instructions:** Anything the user says beyond the inbound message itself — tone guidance, points to include, things to avoid, factual claims to make.

   If medium or register is genuinely ambiguous after checking context, ask once before drafting. Don't guess.

2. **Load context**

   **Voice profile** (always load):
   - `{VAULT}/07 System/Context - Voice & Writing Style.md` — source of truth for voice patterns and register-specific rules

   **CRM lookup** (always attempt):
   - Search `{VAULT}/07 System/CRM/_index.md` for the sender's name
   - If found: read the relevant range file section (A-F, G-L, M-R, S-Z) and Dossier if one exists in `{VAULT}/07 System/CRM/Dossiers/`
   - If not found: note "Not in CRM" and proceed. This is fine — not every reply is to someone in the vault.

   **Topic-relevant context** (as needed):
   - Follow the CLAUDE.md context routing table based on message content. If they're asking about travel, load travel files. If discussing a project, load the project file.

   **Research** (if drafting instructions require it):
   - Quick lookups (vault grep, one web search) — do them now within `/reply`.
   - If the reply needs substantial research (multiple agents, deep web trawl), suggest: "This reply needs more research than I can do inline. Run `/research-assistant` first, then come back to `/reply` with the results in context."

   **Reference class calibration:**
   - If the conversation includes the user's prior sent messages in the same thread, calibrate tone and register from those.
   - If register is ambiguous and no prior messages are available, ask: "Can you paste a couple of your recent messages in this thread so I can match the tone?"

3. **Draft**

   Apply the detected register's voice rules. Follow the user's freeform drafting instructions.

   **Rules:**
   - No AI disclosure.
   - Locale-appropriate spelling (en_AU or the user's configured locale from CLAUDE.md).
   - No imposed structure. IMs don't need greetings. Emails don't need "I hope this finds you well."
   - No over-polishing. Slight roughness signals authenticity per the voice profile. Deliberate imperfection is a feature, not a bug.
   - Freeform drafting, not templated. Match the conversational flow of the thread.

   **Factual claims gate:**
   Flag first-person past-tense claims about the user's experience with `**[true?]**` inline. This means sentences like "I read that paper", "I've been following this company", "I tried that restaurant" — anything that claims the user personally did or experienced something.

   Do NOT flag:
   - Researched facts stated without attributing them to the user's history (Medicare item numbers, clinic costs, paper citations)
   - Opinions or preferences the user explicitly stated in their drafting instructions
   - Future intentions ("I'll look into it") — these are commitments, not claims about the past

   **Batch mode:** If the user pastes 3 or more messages to reply to, run the factual claims inventory before drafting any (per voice profile "3+ emails" rule): present what's known to be true, what was researched, and ask the user to confirm which researched facts can be attributed to them. One round-trip, then draft cleanly.

4. **Voice check (via `/de-ai-ify`)**

   After drafting, invoke `/de-ai-ify` via the Skill tool on the draft text. This is a real skill invocation, not an inline approximation. `/de-ai-ify` will present the before/after comparison and apply its full checklist, including the voice refinement prompt (step 6 of `/de-ai-ify`). Do not duplicate `/de-ai-ify`'s logic here.

5. **Output**

   **Always write to scratchpad:**
   - Append the de-ai-ified version (from step 4, not the original draft) to `{VAULT}/01 Now/Scratchpad.md` under heading `**Reply to [Name] ([medium]):**`
   - If re-drafting the same reply (same sender + medium), replace the previous draft section rather than appending a duplicate

   **User override:**
   - "Just inline" → don't write to scratchpad

   **After output:**
   - Wait for user feedback: edits, "sent", etc.
   - On "sent": acknowledge briefly (one line). Voice refinement is handled by `/de-ai-ify` (step 6) which already ran in step 4.
   - Don't clear scratchpad automatically.

## Conversation Continuity

Within a session, `/reply` carries forward context from previous drafts and the user's "sent" confirmations. A rolling conversation (like multiple replies in an IM thread) builds on all prior context, not just the current invocation. If the user comes back with "they said [X], reply with [Y]", treat it as a continuation — you already know the sender, medium, register, and relationship from the earlier invocation.

## Guidelines

- **Freeform, not templated.** Never impose greeting/body/sign-off structure on IMs.
- **No over-polishing.** Slight roughness signals authenticity. Deliberate imperfection is a feature.
- **Reference class calibration.** If prior sent messages exist in the thread, calibrate from those.
- **Long threads.** Last message not from the user is the one to reply to; everything else is context.
- **CRM miss is fine.** Not every reply is to someone in the vault. Note it and proceed.
- **Batch mode.** 3+ messages to reply to → run claims inventory before drafting any.
- **Research proportionality.** Quick lookups within `/reply` are fine. Substantial research → suggest `/research-assistant` first.
