# AI Provenance Log

Cryptographic audit trail for AI collaboration. Each entry logs the first 16 hexadecimal characters of a file's SHA256 digest. Integrity is verified by `/weekly-hygiene` (step 13b). All writes use the validated provenance writer; re-hashes append a new attestation and a separate supersession relationship without rewriting earlier rows.

For academic disclosure and audit defence. See `/provenance` for details.

---

| Timestamp | Project | File | SHA256 (first 16) | OTS |
|---|---|---|---|---|
