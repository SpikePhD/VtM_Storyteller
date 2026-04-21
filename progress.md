## 2026-04-20
- Added authored ADV1 dialogue social-state loading for Jonas and wired adjudication to consult it for topic availability, guarded acts, and persuade check requirements.
- Added bounded Missing Ledger subtopic carryover for Jonas dialogue, with carry, override, and clear behavior tied to session focus.
## 2026-04-21
- Simplified packet-first dialogue rendering support so the session gate depends on the social outcome packet rather than `npc_1`, while keeping Jonas realization and fallback behavior intact.
- Added a Jonas Missing Ledger end-to-end dialogue harness covering packet truth, check success/failure, renderer fallback, and malformed-intent safety.
- Softened Jonas packet-first realization for small talk and follow-up turns so the Missing Ledger lane sounds less scripted without changing backend truth.
- Replaced Jonas' remaining backend-authored reply text path with dossier/profile data plus authorized fact cards, and made talk realization packet-first without hook dialogue strings.
- Added CLI-first transcript dialogue mode for active NPC conversations, with direct-speech realization, conversation banners, and focus-aware prompts.
- Added the first authored NPC dialogue dossier schema in ADV1 plus a Jonas example, with loader validation and focused tests.
- Added a bounded dialogue-context assembler that threads dossier-backed turn context into render-input construction without changing dialogue behavior.
- Routed active Jonas follow-up lines through the dialogue-intent path before unsupported-input fallback, while keeping explicit world actions on their existing routes.
- Made OpenAI dialogue mode mandatory at render time so missing dialogue LLMs now hard-fail dialogue turns instead of falling back to deterministic NPC speech.
- Onboarded Sister Eliza onto the shared dossier-backed dialogue slice, including church-records facts and generic non-Jonas follow-up routing.
- Added bounded meta-conversation classification for Jonas stance challenges so hostile/help-attitude questions now route into a distinct dialogue domain instead of the lead-content lane.
