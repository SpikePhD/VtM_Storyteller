## 2026-04-22
- Hardened Jonas statement and observation dialogue so meta pushback, insinuations, and short remarks stay in dialogue without echoing the player or defaulting to follow-up questions.
- Hardened guarded-turn focus persistence so suspicion and challenge follow-ups stay addressed to Jonas instead of falling into the no-valid-NPC failure path.
- Hardened Jonas logistics/cooperation outcomes so accompaniment, backup, transport, and fare requests resolve into bounded refusal or partial-cooperation packets without implying stronger commitments than the backend authorizes.
- Hardened the active-conversation dialogue-intent path so Jonas follow-up lines like declarative statements, pressure, and help requests stay in dialogue even when the adapter returns unusable output.
- Tightened the OpenAI dialogue-intent prompt and added move normalization plus a local fallback repair path for active-conversation turns without changing backend truth ownership.
- Added bounded active-conversation history plus per-NPC previous-interactions summaries for Jonas dialogue, and threaded both into intent and render payloads without changing deterministic adjudication or state ownership.
- Switched active-conversation input routing to LLM-first dialogue intent by default, with only explicit world actions bypassing the intent gateway.
- Reworked the CLI dialogue prompt to use `Action >` outside conversation and `Player >` during active dialogue, while keeping the transcript labels consistent.
- Softened dialogue rendering to stop defaulting to hook-style handoff endings like `Go on.` and `I'm listening.`, especially in the Jonas slice.
## 2026-04-20
- Added authored ADV1 dialogue social-state loading for Jonas and wired adjudication to consult it for topic availability, guarded acts, and persuade check requirements.
- Added bounded Missing Ledger subtopic carryover for Jonas dialogue, with carry, override, and clear behavior tied to session focus.
## 2026-04-21
- Added a bounded statement-style dialogue move layer so acknowledgments, banter, clarification, and continuation lines stay out of the parroting path while preserving packet-first adjudication.
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
- Retired the legacy talk-output generator from the live conversation path; backend hook progression now happens in adjudication while packet-driven rendering remains the only realization step.
- Removed the remaining runtime mode switches and fallback selectors so the app now builds and reports one OpenAI storyteller path only, with config/docs cleaned to match.
