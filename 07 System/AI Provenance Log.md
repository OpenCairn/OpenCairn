# AI Provenance Log

Cryptographic audit trail for AI collaboration. Each entry logs a SHA256 hash of the file at time of logging. Integrity is verified by `/weekly-hygiene` (step 14b). Append-only: rows are never rewritten — a re-hash appends a new row and the old row's OTS column becomes `superseded`.

For academic disclosure and audit defence. See `/provenance` for details.

---

| Timestamp | Project | File | SHA256 (first 16) | OTS |
|---|---|---|---|---|
