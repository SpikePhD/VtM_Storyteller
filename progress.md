## 2026-04-20
- Added authored ADV1 dialogue social-state loading for Jonas and wired adjudication to consult it for topic availability, guarded acts, and persuade check requirements.
- Added bounded Missing Ledger subtopic carryover for Jonas dialogue, with carry, override, and clear behavior tied to session focus.
## 2026-04-21
- Simplified packet-first dialogue rendering support so the session gate depends on the social outcome packet rather than `npc_1`, while keeping Jonas realization and fallback behavior intact.
- Added a Jonas Missing Ledger end-to-end dialogue harness covering packet truth, check success/failure, renderer fallback, and malformed-intent safety.
- Softened Jonas packet-first realization for small talk and follow-up turns so the Missing Ledger lane sounds less scripted without changing backend truth.
