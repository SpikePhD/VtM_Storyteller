from __future__ import annotations

import re
from enum import Enum
from dataclasses import dataclass

from .command_models import DialogueAct, DialogueMetadata, DialogueMove
from .dialogue_intent_adapter import (
    DialogueIntentAdapter,
    DialogueIntentProposal,
    build_dialogue_intent_context,
    is_non_specific_target,
    is_pronoun_like_target,
)
from .conversation_context import DialogueHistoryEntry
from .dialogue_subtopic import DialogueSubtopic
from .models import NPC
from .world_state import WorldState


class DialogueTargetResolutionState(str, Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    ABSENT = "absent"
    UNKNOWN = "unknown"
    STALE_FOCUS = "stale_focus"
    NO_ACTIVE_FOCUS = "no_active_focus"


@dataclass(frozen=True, slots=True)
class InterpretedInput:
    normalized_intent: str | None
    target_text: str | None
    target_reference: str | None
    canonical_command: str | None
    confidence: float
    match_reason: str
    fallback_to_parser: bool
    no_active_conversation: bool = False
    dialogue_metadata: DialogueMetadata | None = None
    failure_reason: str | None = None


class InputInterpreter:
    _FOCUSED_FOLLOW_UP_PHRASES = (
        "why",
        "what do you mean",
        "go on",
        "continue",
        "carry on",
        "keep going",
        "turn back",
        "can you explain",
        "i don't believe you",
        "i do not believe you",
        "that sounds wrong",
    )

    _FOCUSED_CONTINUATION_PHRASES = (
        "back to her",
        "back to him",
        "back to them",
        "back to you",
        "continue",
        "carry on",
        "keep going",
        "go on",
        "turn back to her",
        "turn back to him",
        "turn back to them",
    )

    _ACTIVE_CONVERSATION_LOGISTICS_PHRASES = (
        "back me up",
        "backup",
        "back up",
        "watch my back",
        "cover me",
        "come along as backup",
        "come along as back up",
        "stay in the car",
        "wait in the car",
        "wait nearby",
        "stay nearby",
        "wait close",
        "stay close",
        "come along",
        "spare change",
        "taxi fare",
        "cab fare",
        "money to pay",
        "money for the taxi",
        "money for the ride",
        "money for the trip",
        "pay for the taxi",
        "pay for the ride",
        "pay for the trip",
        "pay the taxi",
        "pay the fare",
        "cash for the ride",
        "cash for the trip",
        "cover the fare",
        "drive",
        "spare car",
        "have a car",
        "got a car",
        "lift",
        "drop me off",
        "vehicle",
    )

    _FOCUSLESS_ACTIVE_CONVERSATION_PHRASES = (
        "back me up",
        "backup",
        "back up",
        "watch my back",
        "cover me",
        "come along as backup",
        "come along as back up",
        "stay in the car",
        "wait in the car",
        "wait nearby",
        "stay nearby",
        "wait close",
        "stay close",
        "come along",
        "spare change",
        "taxi fare",
        "cab fare",
        "money to pay",
        "money for the taxi",
        "money for the ride",
        "money for the trip",
        "pay for the taxi",
        "pay for the ride",
        "pay for the trip",
        "pay the taxi",
        "pay the fare",
        "cash for the ride",
        "cash for the trip",
        "cover the fare",
    )

    _LOW_INTENSITY_OBSERVATION_PHRASES = (
        "look around",
        "take a look",
        "take a careful look",
        "look carefully",
        "see if something is wrong",
        "feel disturbed",
        "disturbed",
        "look",
        "observe",
        "watch",
        "examine",
    )

    _HIGH_INTENSITY_OBSERVATION_PHRASES = (
        "investigate",
        "inspect closely",
        "inspect the scene carefully for evidence",
        "search the area for clues",
        "check the scene carefully for evidence",
        "examine for clues",
        "probe for clues",
        "search for clues",
    )

    _SPEECH_VERB_PHRASES = (
        "speak to",
        "speak with",
        "speak",
        "talk to",
        "talk with",
        "talk",
        "ask",
        "accuse",
        "persuade",
        "threaten",
        "tell",
        "say",
        "address",
    )

    _ACTIVE_CONVERSATION_PRESSURE_PHRASES = (
        "need your help",
        "i need your help",
        "need help",
        "need info",
        "i need info",
        "i need you",
        "what do you know",
        "what happened",
        "what else do you know",
        "don't have time",
        "do not have time",
        "busy",
        "not here to chit chat",
        "not here to chitty chat",
        "chitty chat",
        "chit chat",
    )

    def interpret(
        self,
        raw_input: str,
        world_state: WorldState,
        conversation_focus_npc_id: str | None = None,
        conversation_subtopic: DialogueSubtopic | None = None,
        stale_conversation_focus_npc_id: str | None = None,
        stale_conversation_focus_reason: str | None = None,
        dialogue_intent_adapter: DialogueIntentAdapter | None = None,
        recent_dialogue_history: tuple[DialogueHistoryEntry, ...] = (),
    ) -> InterpretedInput:
        normalized_text = self._normalize_text(raw_input)
        if not normalized_text:
            return self._fallback("input was empty after normalization")

        talk_result = self._interpret_talk(
            raw_input,
            normalized_text,
            world_state,
            conversation_focus_npc_id,
            conversation_subtopic,
            stale_conversation_focus_npc_id,
            stale_conversation_focus_reason,
            dialogue_intent_adapter,
            recent_dialogue_history,
        )
        if talk_result is not None:
            return talk_result

        unfocused_follow_up_result = self._interpret_unfocused_follow_up(normalized_text)
        if unfocused_follow_up_result is not None:
            return unfocused_follow_up_result

        wait_result = self._interpret_wait(normalized_text)
        if wait_result is not None:
            return wait_result

        movement_result = self._interpret_move(normalized_text, world_state)
        if movement_result is not None:
            return movement_result

        observation_result = self._interpret_observation(normalized_text)
        if observation_result is not None:
            return observation_result

        return self._fallback("no freeform interpretation rule matched")

    def _interpret_observation(self, normalized_text: str) -> InterpretedInput | None:
        if "look like" in normalized_text or "look to you" in normalized_text:
            if "what does" in normalized_text or "how do i know" in normalized_text or "prove it" in normalized_text:
                return None
        if self._contains_any(normalized_text, self._LOW_INTENSITY_OBSERVATION_PHRASES):
            return InterpretedInput(
                normalized_intent="look",
                target_text=None,
                target_reference=None,
                canonical_command="look",
                confidence=0.86,
                match_reason="observation text suggested a low-intensity look action",
                fallback_to_parser=False,
            )

        if self._contains_any(normalized_text, self._HIGH_INTENSITY_OBSERVATION_PHRASES):
            return InterpretedInput(
                normalized_intent="investigate",
                target_text=None,
                target_reference=None,
                canonical_command="investigate",
                confidence=0.9,
                match_reason="observation text suggested active investigation",
                fallback_to_parser=False,
            )

        return None

    def _interpret_move(self, normalized_text: str, world_state: WorldState) -> InterpretedInput | None:
        destination = self._match_location(normalized_text, world_state)
        if destination is None:
            return None

        if not self._contains_any(
            normalized_text,
            ("go to", "head to", "head over", "walk to", "travel to", "move to", "make my way to", "go", "head", "walk", "travel", "move"),
        ):
            return None

        return InterpretedInput(
            normalized_intent="move",
            target_text=destination["matched_text"],
            target_reference=destination["location_id"],
            canonical_command=f"move {destination['location_id']}",
            confidence=0.9,
            match_reason=f"movement text matched location '{destination['matched_text']}'",
            fallback_to_parser=False,
        )

    def _interpret_wait(self, normalized_text: str) -> InterpretedInput | None:
        wait_match = re.search(
            r"\bwait(?:ing)?(?: for)? (?:(?P<amount>\d+)|(?P<word>an?|one|two|three|four|five|six|ten|fifteen|twenty|thirty|forty|fifty|sixty))(?P<unit> minutes?| minute| hours?| hour| hrs?| hr)?\b",
            normalized_text,
        )
        if wait_match is None:
            return None

        amount_text = wait_match.group("amount") or wait_match.group("word")
        assert amount_text is not None
        minutes = self._parse_wait_amount(amount_text, wait_match.group("unit"))
        if minutes is None:
            return None

        return InterpretedInput(
            normalized_intent="wait",
            target_text=str(minutes),
            target_reference=None,
            canonical_command=f"wait {minutes}",
            confidence=0.98,
            match_reason="wait phrase included an explicit duration",
            fallback_to_parser=False,
        )

    def _interpret_talk(
        self,
        raw_input: str,
        normalized_text: str,
        world_state: WorldState,
        conversation_focus_npc_id: str | None,
        conversation_subtopic: DialogueSubtopic | None,
        stale_conversation_focus_npc_id: str | None,
        stale_conversation_focus_reason: str | None,
        dialogue_intent_adapter: DialogueIntentAdapter | None,
        recent_dialogue_history: tuple[DialogueHistoryEntry, ...],
    ) -> InterpretedInput | None:
        if self._looks_like_canonical_talk_command(raw_input):
            return None

        has_active_conversation = conversation_focus_npc_id is not None or conversation_subtopic is not None
        explicit_non_dialogue_action = self._looks_like_explicit_non_dialogue_action(normalized_text, raw_input, world_state)
        if has_active_conversation and not explicit_non_dialogue_action:
            adapter_result = self._interpret_dialogue_intent_proposal(
                raw_input,
                normalized_text,
                world_state,
                conversation_focus_npc_id,
                dialogue_intent_adapter,
                recent_dialogue_history,
            )
            if adapter_result is not None:
                return adapter_result

            fallback_result = self._build_fallback_active_conversation_dialogue(
                raw_input,
                normalized_text,
                world_state,
                conversation_focus_npc_id,
                conversation_subtopic,
            )
            if fallback_result is not None:
                return fallback_result

            if stale_conversation_focus_npc_id is not None:
                return self._failure(
                    match_reason="active conversation line matched a stale conversation focus",
                    failure_reason=stale_conversation_focus_reason
                    or "Talk is blocked: the previous conversation focus is no longer valid.",
                )

            return self._failure(
                match_reason="active conversation line could not be classified by the dialogue intent adapter",
                failure_reason="Talk is blocked: the dialogue intent adapter did not produce a usable dialogue action.",
            )

        npc_matches = self._match_npc_candidates(normalized_text, world_state)
        has_talk_cue = (
            bool(npc_matches)
            or self._looks_like_dialogue_entry(normalized_text, raw_input)
            or self._contains_any(normalized_text, self._FOCUSLESS_ACTIVE_CONVERSATION_PHRASES)
            or (
                has_active_conversation
                and not explicit_non_dialogue_action
                and self._looks_like_active_conversation_follow_up(normalized_text, raw_input, conversation_subtopic)
            )
            or (has_active_conversation and not explicit_non_dialogue_action)
        )

        if not has_talk_cue:
            return None

        if len(npc_matches) > 1:
            return self._failure(
                match_reason="dialogue target matched more than one present NPC",
                failure_reason=self._build_ambiguous_target_message(npc_matches),
            )

        if len(npc_matches) == 1:
            npc_match = npc_matches[0]
            npc = world_state.npcs.get(npc_match["npc_id"])
            if npc is None:
                return self._failure(
                    match_reason="dialogue target matched an NPC that is no longer available",
                    failure_reason="Talk is blocked: the selected NPC is no longer available.",
                )

            if npc.location_id != world_state.player.location_id:
                location = world_state.locations.get(world_state.player.location_id or "")
                location_name = location.name if location is not None else (world_state.player.location_id or "unknown location")
                return self._failure(
                    match_reason=f"dialogue target matched NPC '{npc_match['matched_text']}' but they are absent",
                    failure_reason=f"Talk is blocked: {npc.name} is not present at {location_name}.",
                )

            speech_text = self._extract_speech_text(raw_input, npc_match["matched_text"])
            return self._build_talk_result(raw_input, normalized_text, npc, speech_text, npc_match["matched_text"])

        if dialogue_intent_adapter is not None and self._contains_any(normalized_text, self._SPEECH_VERB_PHRASES):
            adapter_result = self._interpret_dialogue_intent_proposal(
                raw_input,
                normalized_text,
                world_state,
                conversation_focus_npc_id,
                dialogue_intent_adapter,
                recent_dialogue_history,
            )
            if adapter_result is not None:
                return adapter_result

        if self._looks_like_follow_up(normalized_text) or self._contains_any(normalized_text, self._FOCUSLESS_ACTIVE_CONVERSATION_PHRASES) or (
            has_active_conversation and self._looks_like_active_conversation_follow_up(normalized_text, raw_input, conversation_subtopic)
        ):
            if conversation_focus_npc_id is not None:
                focused_npc = world_state.npcs.get(conversation_focus_npc_id)
                if focused_npc is not None and focused_npc.location_id == world_state.player.location_id:
                    return self._build_talk_result(
                        raw_input,
                        normalized_text,
                        focused_npc,
                        raw_input.strip(),
                        focused_npc.name,
                    )

            if stale_conversation_focus_npc_id is not None:
                return self._failure(
                    match_reason="follow-up dialogue matched a stale conversation focus",
                    failure_reason=stale_conversation_focus_reason
                    or "Talk is blocked: the previous conversation focus is no longer valid.",
                )

            return InterpretedInput(
                normalized_intent="conversation_continuation_without_focus",
                target_text=None,
                target_reference=None,
                canonical_command=None,
                confidence=0.7,
                match_reason="follow-up dialogue was attempted without an active conversation focus",
                fallback_to_parser=False,
                no_active_conversation=True,
            )

        if self._contains_any(normalized_text, self._SPEECH_VERB_PHRASES) or "?" in raw_input:
            return self._failure(
                match_reason="dialogue text referenced an unknown or absent target",
                failure_reason="Talk is blocked: I could not identify a valid NPC to address.",
            )

        return None

    def _interpret_focused_talk(
        self,
        raw_input: str,
        normalized_text: str,
        world_state: WorldState,
        conversation_focus_npc_id: str | None,
        stale_conversation_focus_npc_id: str | None,
        stale_conversation_focus_reason: str | None,
    ) -> InterpretedInput | None:
        if not self._looks_like_follow_up(normalized_text):
            return None

        if conversation_focus_npc_id is not None:
            focused_npc = world_state.npcs.get(conversation_focus_npc_id)
            if focused_npc is not None and focused_npc.location_id == world_state.player.location_id:
                return self._build_talk_result(raw_input, normalized_text, focused_npc, raw_input.strip(), focused_npc.name)

        if stale_conversation_focus_npc_id is not None:
            return self._failure(
                match_reason="follow-up dialogue matched a stale conversation focus",
                failure_reason=stale_conversation_focus_reason
                or "Talk is blocked: the previous conversation focus is no longer valid.",
            )

        return InterpretedInput(
            normalized_intent="conversation_continuation_without_focus",
            target_text=None,
            target_reference=None,
            canonical_command=None,
            confidence=0.7,
            match_reason="follow-up dialogue was attempted without an active conversation focus",
            fallback_to_parser=False,
            no_active_conversation=True,
        )

    def _interpret_unfocused_follow_up(self, normalized_text: str) -> InterpretedInput | None:
        if not self._contains_any(normalized_text, self._FOCUSED_FOLLOW_UP_PHRASES):
            return None

        return InterpretedInput(
            normalized_intent="conversation_continuation_without_focus",
            target_text=None,
            target_reference=None,
            canonical_command=None,
            confidence=0.7,
            match_reason="follow-up dialogue was attempted without an active conversation focus",
            fallback_to_parser=False,
            no_active_conversation=True,
        )

    def _classify_dialogue_act(self, raw_input: str, normalized_text: str, speech_text: str, normalized_speech_text: str) -> DialogueAct:
        if not normalized_speech_text:
            return DialogueAct.UNKNOWN

        if self._contains_any(
            normalized_text,
            ("good morning", "good afternoon", "good evening", "good night", "hello", "hi", "hey", "greetings"),
        ):
            return DialogueAct.GREET

        if self._contains_any(
            normalized_text,
            ("i accuse", "i accuse jonas", "i accuse sister", "i accuse you", "i don't believe you", "i do not believe you", "accuse"),
        ) or self._contains_any(
            normalized_speech_text,
            (
                "you're hiding",
                "you are hiding",
                "you're lying",
                "you are lying",
                "what did you do",
                "what are you hiding",
                "i know you",
                "you did this",
                "liar",
                "lying",
                "betray",
                "betrayed",
                "stole",
                "stolen",
                "murder",
                "guilty",
                "confess",
                "not true",
                "that sounds wrong",
                "don't believe you",
                "do not believe you",
            ),
        ):
            return DialogueAct.ACCUSE

        if self._contains_any(
            normalized_text,
            ("i threaten", "i threaten jonas", "i threaten you", "threaten", "or else"),
        ) or self._contains_any(
            normalized_speech_text,
            (
                "before this gets worse",
                "don't make me",
                "do this now",
                "i won't ask again",
                "you'll regret",
                "regret this",
                "make this difficult",
                "last chance",
                "comply",
                "threat",
                "hurt you",
            ),
        ):
            return DialogueAct.THREATEN

        if self._contains_any(
            normalized_text,
            ("i need you to", "i persuade", "i persuade jonas", "i persuade you", "need your help", "need help", "need info"),
        ) or self._contains_any(
            normalized_speech_text,
            (
                "trust me",
                "help me",
                "need your help",
                "need help",
                "need info",
                "please",
                "listen to me",
                "work with me",
                "believe me",
                "i can help",
                "come with me",
                "do this for me",
                "convince",
                "persuade",
            ),
        ):
            return DialogueAct.PERSUADE

        if "?" in raw_input or self._contains_any(
            normalized_text,
            ("i ask", "i ask jonas", "i ask you", "what do you know", "what happened", "tell me what you know"),
        ) or self._contains_any(
            normalized_speech_text,
            (
                "what",
                "why",
                "who",
                "where",
                "when",
                "how",
                "can you",
                "could you",
                "would you",
                "will you",
                "do you",
                "did you",
                "are you",
                "is it",
            ),
        ):
            return DialogueAct.ASK

        return DialogueAct.UNKNOWN

    def _match_location(self, normalized_text: str, world_state: WorldState) -> dict[str, str] | None:
        best_match: dict[str, str] | None = None
        for location in world_state.locations.values():
            aliases = self._location_aliases(location)
            match = self._match_alias(normalized_text, aliases)
            if match is None:
                continue
            if best_match is None or len(match["matched_text"].split()) > len(best_match["matched_text"].split()):
                best_match = {
                    "location_id": location.id,
                    "matched_text": match["matched_text"],
                }
        return best_match

    def _match_npc_candidates(self, normalized_text: str, world_state: WorldState) -> list[dict[str, str]]:
        matches: list[dict[str, str]] = []
        for npc in world_state.npcs.values():
            aliases = self._npc_aliases(npc.name)
            match = self._match_alias(normalized_text, aliases)
            if match is None:
                continue
            matches.append(
                {
                    "npc_id": npc.id,
                    "npc_name": npc.name,
                    "matched_text": match["matched_text"],
                }
            )
        return sorted(matches, key=lambda item: (-len(item["matched_text"].split()), item["npc_name"], item["npc_id"]))

    def _match_alias(self, normalized_text: str, aliases: list[str]) -> dict[str, str] | None:
        for alias in sorted({alias for alias in aliases if alias}, key=lambda value: (-len(value.split()), -len(value))):
            if self._contains_phrase(normalized_text, alias):
                return {"matched_text": alias}
        return None

    def _location_aliases(self, location) -> list[str]:
        aliases = [self._normalize_text(location.name), location.id.removeprefix("loc_")]
        if location.id.startswith("loc_"):
            aliases.append(location.id.removeprefix("loc_").replace("_", " "))
        return aliases

    def _npc_aliases(self, name: str) -> list[str]:
        aliases = [self._normalize_text(name)]
        aliases.extend(self._normalize_text(part) for part in name.split())
        return aliases

    def _extract_speech_text(self, raw_input: str, matched_text: str) -> str:
        stripped_input = raw_input.strip()

        direct_address_pattern = rf"^\s*{re.escape(matched_text)}\s*[,!:.-]?\s*"
        direct_address_match = re.match(direct_address_pattern, stripped_input, flags=re.IGNORECASE)
        if direct_address_match is not None:
            return stripped_input[direct_address_match.end():].strip()

        indirect_prefix_pattern = rf"^\s*(?:i\s+)?(?:speak to|speak with|talk to|talk with|ask|accuse|persuade|threaten|tell|say|address)\s+{re.escape(matched_text)}\b[\s,!:.-]*"
        indirect_prefix_match = re.match(indirect_prefix_pattern, stripped_input, flags=re.IGNORECASE)
        if indirect_prefix_match is not None:
            return stripped_input[indirect_prefix_match.end():].strip()

        return stripped_input

    def _parse_wait_amount(self, amount_text: str, unit_text: str | None) -> int | None:
        number_words = {
            "a": 1,
            "an": 1,
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "ten": 10,
            "fifteen": 15,
            "twenty": 20,
            "thirty": 30,
            "forty": 40,
            "fifty": 50,
            "sixty": 60,
        }
        if amount_text.isdigit():
            amount = int(amount_text)
        else:
            amount = number_words.get(amount_text)
        if amount is None or amount <= 0:
            return None

        if unit_text is None:
            return amount

        unit_text = unit_text.strip()
        if unit_text.startswith("hour") or unit_text.startswith("hr"):
            return amount * 60

        return amount

    def _looks_like_direct_address(self, raw_input: str, matched_text: str) -> bool:
        pattern = rf"^\s*{re.escape(matched_text)}\s*[,!:.-]"
        return re.match(pattern, raw_input, flags=re.IGNORECASE) is not None

    def _looks_like_dialogue_entry(self, normalized_text: str, raw_input: str) -> bool:
        if self._contains_any(normalized_text, self._SPEECH_VERB_PHRASES):
            return True
        if "?" in raw_input:
            return True
        if self._contains_any(normalized_text, self._FOCUSED_FOLLOW_UP_PHRASES):
            return True
        if self._contains_any(normalized_text, self._FOCUSED_CONTINUATION_PHRASES):
            return True
        return False

    def _looks_like_follow_up(self, normalized_text: str) -> bool:
        return self._contains_any(normalized_text, self._FOCUSED_FOLLOW_UP_PHRASES) or self._contains_any(
            normalized_text, self._FOCUSED_CONTINUATION_PHRASES
        )

    def _looks_like_active_conversation_follow_up(
        self,
        normalized_text: str,
        raw_input: str,
        conversation_subtopic: DialogueSubtopic | None = None,
    ) -> bool:
        if self._contains_any(normalized_text, self._ACTIVE_CONVERSATION_LOGISTICS_PHRASES):
            return True
        if self._contains_any(
            normalized_text,
            (
                "what happened at the dock",
                "what happened at the docks",
                "what about the dock",
                "what about the ledger",
                "what about the church records",
                "what about the church",
                "what about the records",
                "what about",
                "tell me",
                "sure tell me",
                "what do you know about the missing ledger",
                "what do you know about the ledger",
                "tell me what you know about the missing ledger",
                "tell me what you know about the ledger",
                "tell me about the church records",
                "tell me about the church",
                "tell me about the records",
                "tell me about",
                "just coming to say hi",
                "coming to say hi",
                "there you are",
                "you just did",
                "are you repeating what i am saying",
                "missing ledger",
                "about the dock",
                "about the ledger",
                "tell me more about you",
                "more about you",
                "what do you do",
                "who are you",
                "what happened",
                "what else",
                "tell me more",
            ),
        ):
            return True
        if self._contains_any(normalized_text, ("i need you to", "i need you as", "yes we are", "yes, we are", "yes we are talking about")) and self._contains_any(
            normalized_text,
            self._ACTIVE_CONVERSATION_LOGISTICS_PHRASES,
        ):
            return True
        if raw_input.strip().lower().startswith(("yes ", "yes,", "yeah ", "yeah,")) and self._contains_any(
            normalized_text,
            (
                "need you",
                "back up",
                "backup",
                "wait nearby",
                "stay nearby",
                "stay in the car",
                "come along",
                "spare change",
                "money to pay",
                "pay for the taxi",
                "pay for the ride",
                "taxi fare",
                "cab fare",
            ),
        ):
            return True
        if conversation_subtopic is DialogueSubtopic.BLOOD_OR_FEEDING_REQUEST and self._contains_any(
            normalized_text,
            (
                "why not",
                "eager to please",
                "please a vampire",
                "let me feed",
                "feed off",
                "blood",
                "vampire",
                "do me a favor",
                "do me this favor",
            ),
        ):
            return True
        if conversation_subtopic is DialogueSubtopic.MISSING_LEDGER and self._contains_any(
            normalized_text,
            (
                "what about it",
                "what about that",
                "what happened there",
                "tell me more about it",
                "tell me more about that",
                "and then",
                "back to that",
            ),
        ):
            return True
        if self._contains_any(
            normalized_text,
            (
                "how are you",
                "how are you doing",
                "how are things",
                "how is it going",
                "how's it going",
                "how have you been",
            ),
        ):
            return True
        if conversation_subtopic is not None and "please" in normalized_text.split() and len(normalized_text.split()) <= 4:
            return True
        return False

    def _looks_like_explicit_non_dialogue_action(self, normalized_text: str, raw_input: str, world_state: WorldState) -> bool:
        first_token = self._normalize_text(raw_input).split(" ", 1)[0] if raw_input.strip() else ""
        if first_token in {"look", "move", "wait", "investigate", "save", "load", "quit"}:
            return True
        if self._interpret_wait(normalized_text) is not None:
            return True
        if self._interpret_observation(normalized_text) is not None:
            return True
        if self._interpret_move(normalized_text, world_state) is not None:
            return True
        if first_token in {"help", "status"}:
            return True
        return False

    def _looks_like_canonical_talk_command(self, raw_input: str) -> bool:
        tokens = raw_input.strip().split()
        return 0 < len(tokens) <= 2 and tokens[0].lower() == "talk"

    def _interpret_dialogue_intent_proposal(
        self,
        raw_input: str,
        normalized_text: str,
        world_state: WorldState,
        conversation_focus_npc_id: str | None,
        dialogue_intent_adapter: DialogueIntentAdapter | None,
        recent_dialogue_history: tuple[DialogueHistoryEntry, ...],
    ) -> InterpretedInput | None:
        if dialogue_intent_adapter is None:
            return None

        has_explicit_npc_reference = bool(self._match_npc_candidates(normalized_text, world_state))
        explicit_addressee_hint = self._extract_explicit_addressee_hint(raw_input)
        proposal = dialogue_intent_adapter.propose_dialogue_intent(
            build_dialogue_intent_context(
                world_state,
                raw_input,
                conversation_focus_npc_id,
                recent_dialogue_history,
            )
        )
        if proposal is None:
            return None

        resolved_npc, resolution_source = self._resolve_adapter_target(
            proposal,
            raw_input,
            normalized_text,
            world_state,
            conversation_focus_npc_id,
            has_explicit_npc_reference,
            explicit_addressee_hint,
        )
        if resolved_npc is None:
            return None

        speech_text = self._extract_speech_text(raw_input, resolved_npc.name)
        dialogue_act = self._coerce_dialogue_act(proposal.dialogue_act)
        dialogue_move = self._coerce_dialogue_move(proposal.dialogue_move)
        metadata = DialogueMetadata(
            utterance_text=raw_input.strip(),
            speech_text=speech_text,
            dialogue_act=dialogue_act,
            topic=proposal.topic,
            tone=proposal.tone,
            dialogue_move=dialogue_move,
        )
        return InterpretedInput(
            normalized_intent="talk",
            target_text=proposal.target_npc_text,
            target_reference=resolved_npc.id,
            canonical_command=f"talk {resolved_npc.id}",
            confidence=0.88 if dialogue_act is not DialogueAct.UNKNOWN else 0.76,
            match_reason=self._build_adapter_match_reason(proposal.target_npc_text, resolved_npc, resolution_source),
            fallback_to_parser=False,
            dialogue_metadata=metadata,
        )

    def _build_fallback_active_conversation_dialogue(
        self,
        raw_input: str,
        normalized_text: str,
        world_state: WorldState,
        conversation_focus_npc_id: str | None,
        conversation_subtopic: DialogueSubtopic | None,
    ) -> InterpretedInput | None:
        focus_npc = world_state.npcs.get(conversation_focus_npc_id) if conversation_focus_npc_id is not None else None
        if focus_npc is None:
            present_npcs = self._present_npcs(world_state)
            if len(present_npcs) == 1:
                focus_npc = present_npcs[0]

        if focus_npc is None or focus_npc.location_id != world_state.player.location_id:
            return None

        dialogue_act = self._classify_dialogue_act(raw_input, normalized_text, raw_input.strip(), normalized_text)
        dialogue_move = self._classify_dialogue_move(
            raw_input,
            normalized_text,
            raw_input.strip(),
            normalized_text,
            dialogue_act,
        )
        topic = self._infer_dialogue_topic(normalized_text, dialogue_act, conversation_subtopic)
        tone = self._infer_dialogue_tone(normalized_text, dialogue_act, dialogue_move)
        proposal = DialogueIntentProposal(
            dialogue_act=dialogue_act.value,
            dialogue_move=dialogue_move.value,
            target_npc_text=focus_npc.name,
            topic=topic,
            tone=tone,
        )
        resolved_npc, resolution_source = self._resolve_adapter_target(
            proposal,
            raw_input,
            normalized_text,
            world_state,
            focus_npc.id,
            False,
            None,
        )
        if resolved_npc is None:
            return None

        speech_text = self._extract_speech_text(raw_input, resolved_npc.name)
        metadata = DialogueMetadata(
            utterance_text=raw_input.strip(),
            speech_text=speech_text,
            dialogue_act=dialogue_act,
            topic=topic,
            tone=tone,
            dialogue_move=dialogue_move,
        )
        return InterpretedInput(
            normalized_intent="talk",
            target_text=proposal.target_npc_text,
            target_reference=resolved_npc.id,
            canonical_command=f"talk {resolved_npc.id}",
            confidence=0.7 if dialogue_act is DialogueAct.UNKNOWN else 0.84,
            match_reason=f"active conversation fallback grounded '{raw_input.strip()}' via {resolution_source or 'conversation focus'}",
            fallback_to_parser=False,
            dialogue_metadata=metadata,
        )

    def _resolve_adapter_target(
        self,
        proposal: DialogueIntentProposal,
        raw_input: str,
        normalized_text: str,
        world_state: WorldState,
        conversation_focus_npc_id: str | None,
        has_explicit_npc_reference: bool,
        explicit_addressee_hint: str | None,
    ) -> tuple[NPC | None, str | None]:
        normalized_target = self._normalize_text(proposal.target_npc_text)
        present_npcs = [npc for npc in world_state.npcs.values() if npc.location_id == world_state.player.location_id]
        single_present_npc = present_npcs[0] if len(present_npcs) == 1 else None
        dialogue_like = self._looks_like_dialogue_entry(normalized_text, raw_input)
        has_explicit_addressee_hint = explicit_addressee_hint is not None

        if is_pronoun_like_target(normalized_target) or is_non_specific_target(normalized_target):
            if conversation_focus_npc_id is None:
                if single_present_npc is not None and dialogue_like and not has_explicit_npc_reference and not has_explicit_addressee_hint:
                    return single_present_npc, "single-present NPC fallback after non-specific adapter target"
                return None, None
            focused_npc = world_state.npcs.get(conversation_focus_npc_id)
            if focused_npc is None or focused_npc.location_id != world_state.player.location_id:
                if single_present_npc is not None and dialogue_like and not has_explicit_npc_reference and not has_explicit_addressee_hint:
                    return single_present_npc, "single-present NPC fallback after non-specific adapter target"
                return None, None
            return focused_npc, "active conversation focus"

        if not normalized_target:
            if single_present_npc is not None and dialogue_like and not has_explicit_npc_reference and not has_explicit_addressee_hint:
                return single_present_npc, "single-present NPC fallback after empty adapter target"
            return None, None

        matches = self._match_npc_candidates(normalized_target, world_state)
        if len(matches) == 1:
            resolved_npc = world_state.npcs.get(matches[0]["npc_id"])
            if resolved_npc is None:
                return None, None
            if resolved_npc.location_id != world_state.player.location_id:
                return None, None
            return resolved_npc, "explicit adapter target"

        if len(matches) > 1:
            return None, None

        if single_present_npc is not None and dialogue_like and not has_explicit_npc_reference and not has_explicit_addressee_hint:
            return single_present_npc, "single-present NPC fallback after unresolved adapter target"

        return None, None

    def _build_adapter_match_reason(self, target_text: str, npc: NPC, resolution_source: str | None) -> str:
        if resolution_source == "explicit adapter target":
            return f"dialogue intent adapter grounded target '{target_text}' as {npc.name}"
        if resolution_source == "active conversation focus":
            return f"dialogue intent adapter reused active conversation focus for {npc.name}"
        if resolution_source is not None:
            return f"dialogue intent adapter grounded '{target_text}' via {resolution_source} as {npc.name}"
        return f"dialogue intent adapter grounded target '{target_text}' as {npc.name}"

    def _extract_explicit_addressee_hint(self, raw_input: str) -> str | None:
        stripped_input = raw_input.strip()
        if not stripped_input:
            return None

        direct_address_match = re.match(
            r"^\s*([A-Z][\w'’\-]*(?:\s+[A-Z][\w'’\-]*){0,2})\s*[,!:]",
            stripped_input,
        )
        if direct_address_match is not None:
            return direct_address_match.group(1)

        for pattern in (
            r"\b(?:to|with|for|at|from)\s+([A-Z][\w'’\-]*(?:\s+[A-Z][\w'’\-]*){0,2})\b",
            r"\b(?:ask|tell|say|speak|talk|address|give)\s+(?:a\s+sign\s+to\s+)?([A-Z][\w'’\-]*(?:\s+[A-Z][\w'’\-]*){0,2})\b",
        ):
            match = re.search(pattern, stripped_input)
            if match is not None:
                return match.group(1)

        return None

    def _coerce_dialogue_act(self, dialogue_act: str) -> DialogueAct:
        try:
            return DialogueAct(dialogue_act)
        except ValueError:
            return DialogueAct.UNKNOWN

    def _coerce_dialogue_move(self, dialogue_move: str) -> DialogueMove:
        try:
            return DialogueMove(dialogue_move)
        except ValueError:
            return DialogueMove.NONE

    def _classify_dialogue_move(
        self,
        raw_input: str,
        normalized_text: str,
        speech_text: str,
        normalized_speech_text: str,
        dialogue_act: DialogueAct,
    ) -> DialogueMove:
        if not normalized_speech_text:
            return DialogueMove.NONE

        if self._contains_any(
            normalized_text,
            (
                "you just did",
                "are you repeating what i am saying",
                "you are repeating what i am saying",
                "youre repeating what i am saying",
                "no you have not given me anything",
                "you have not given me anything",
                "you have not helped me",
                "you didnt help me",
                "you did not help me",
                "that is not what i meant",
                "thats not what i meant",
                "i meant",
            ),
        ):
            return DialogueMove.CLARIFY

        if self._contains_any(
            normalized_text,
            (
                "sure tell me",
                "sure i am listening",
                "tell me more",
                "go on",
                "continue",
                "carry on",
                "keep going",
                "what else",
                "and then",
                "go ahead",
                "i am listening",
            ),
        ) or normalized_text.startswith("sure"):
            return DialogueMove.CONTINUE

        if self._contains_any(
            normalized_text,
            (
                "just coming to say hi",
                "coming to say hi",
                "just wanted to say hi",
                "say hi",
                "hello there",
                "hi there",
                "good to see you",
                "nice to see you",
                "good evening",
                "good morning",
                "good afternoon",
                "just saying hi",
            ),
        ):
            return DialogueMove.REACT

        if self._contains_any(
            normalized_text,
            (
                "there you are",
                "look who it is",
                "well well",
                "oh there you are",
            ),
        ):
            return DialogueMove.BANTER

        if dialogue_act is DialogueAct.ASK and self._contains_any(
            normalized_speech_text,
            (
                "what is going on",
                "how are you",
                "how are things",
                "how is it going",
                "what do you mean",
            ),
        ):
            return DialogueMove.NONE

        if dialogue_act is DialogueAct.GREET:
            return DialogueMove.REACT

        if dialogue_act is DialogueAct.UNKNOWN and any(token in normalized_text.split() for token in ("sure", "right", "okay", "ok")):
            return DialogueMove.REACT

        if dialogue_act is DialogueAct.ASK and self._contains_any(
            normalized_text,
            (
                "go on",
                "continue",
                "what else",
            ),
        ):
            return DialogueMove.CONTINUE

        if self._contains_any(normalized_text, self._ACTIVE_CONVERSATION_PRESSURE_PHRASES):
            return DialogueMove.CONTINUE

        if dialogue_act is DialogueAct.UNKNOWN and self._contains_any(
            normalized_text,
            (
                "what do you know",
                "what happened",
                "need your help",
                "need info",
                "busy",
            ),
        ):
            return DialogueMove.CONTINUE

        return DialogueMove.NONE

    def _build_talk_result(
        self,
        raw_input: str,
        normalized_text: str,
        npc,
        speech_text: str,
        matched_text: str,
        dialogue_act: DialogueAct | None = None,
        topic: str | None = None,
        tone: str | None = None,
    ) -> InterpretedInput:
        normalized_speech_text = self._normalize_text(speech_text)
        if dialogue_act is None:
            dialogue_act = self._classify_dialogue_act(raw_input, normalized_text, speech_text, normalized_speech_text)
        dialogue_move = self._classify_dialogue_move(raw_input, normalized_text, speech_text, normalized_speech_text, dialogue_act)
        metadata = DialogueMetadata(
            utterance_text=raw_input.strip(),
            speech_text=speech_text,
            dialogue_act=dialogue_act,
            topic=topic,
            tone=tone,
            dialogue_move=dialogue_move,
        )
        return InterpretedInput(
            normalized_intent="talk",
            target_text=matched_text,
            target_reference=npc.id,
            canonical_command=f"talk {npc.id}",
            confidence=0.95 if dialogue_act is not DialogueAct.UNKNOWN else 0.8,
            match_reason=f"speech text matched NPC '{matched_text}' and classified as {dialogue_act.value}",
            fallback_to_parser=False,
            dialogue_metadata=metadata,
        )

    def _build_ambiguous_target_message(self, npc_matches: list[dict[str, str]]) -> str:
        npc_names = ", ".join(sorted({match["npc_name"] for match in npc_matches}))
        return f"Talk is blocked: the target is ambiguous between {npc_names}."

    def _present_npcs(self, world_state: WorldState) -> tuple[NPC, ...]:
        player_location_id = world_state.player.location_id
        if player_location_id is None:
            return ()
        return tuple(
            npc
            for npc in world_state.npcs.values()
            if npc.location_id == player_location_id
        )

    def _infer_dialogue_topic(
        self,
        normalized_text: str,
        dialogue_act: DialogueAct,
        conversation_subtopic: DialogueSubtopic | None,
    ) -> str:
        if conversation_subtopic is DialogueSubtopic.MISSING_LEDGER:
            return "missing_ledger"
        if conversation_subtopic is DialogueSubtopic.TRANSPORT_OR_VEHICLE_SUPPORT:
            return "transport"
        if self._contains_any(
            normalized_text,
            (
                "ledger",
                "paper trail",
                "dock",
                "docks",
                "church records",
                "records",
                "trail",
                "what happened",
                "what do you know",
                "tell me more",
            ),
        ):
            return "missing_ledger"
        if self._contains_any(
            normalized_text,
            (
                "help",
                "need help",
                "need your help",
                "need info",
                "what do you know",
                "tell me",
            ),
        ):
            return "help"
        if self._contains_any(
            normalized_text,
            (
                "back me up",
                "backup",
                "back up",
                "watch my back",
                "cover me",
                "stay nearby",
                "stay close",
                "wait nearby",
                "wait in the car",
                "stay in the car",
            ),
        ):
            return "backup"
        if self._contains_any(
            normalized_text,
            (
                "drive",
                "ride",
                "lift",
                "vehicle",
                "car",
                "drop me off",
                "transport",
            ),
        ):
            return "transport"
        if self._contains_any(
            normalized_text,
            (
                "blood",
                "feed",
                "vampire",
            ),
        ):
            return "blood"
        if dialogue_act in {DialogueAct.ASK, DialogueAct.PERSUADE, DialogueAct.ACCUSE, DialogueAct.THREATEN}:
            return "lead_topic"
        return "conversation"

    def _infer_dialogue_tone(
        self,
        normalized_text: str,
        dialogue_act: DialogueAct,
        dialogue_move: DialogueMove,
    ) -> str:
        if self._contains_any(
            normalized_text,
            (
                "don't have time",
                "do not have time",
                "need your help",
                "need info",
                "busy",
                "not here to chit chat",
                "not here to chitty chat",
            ),
        ):
            return "urgent"
        if self._contains_any(
            normalized_text,
            (
                "i do not believe you",
                "i don't believe you",
                "that sounds wrong",
                "you just did",
                "what do you know",
            ),
        ):
            return "guarded"
        if dialogue_act is DialogueAct.THREATEN:
            return "tense"
        if dialogue_act is DialogueAct.ACCUSE:
            return "guarded"
        if dialogue_act is DialogueAct.PERSUADE:
            return "careful"
        if dialogue_move in {DialogueMove.REACT, DialogueMove.BANTER}:
            return "warm"
        if dialogue_move is DialogueMove.CLARIFY:
            return "guarded"
        if "please" in normalized_text:
            return "polite"
        return "curious"

    def _failure(self, match_reason: str, failure_reason: str) -> InterpretedInput:
        return InterpretedInput(
            normalized_intent="talk",
            target_text=None,
            target_reference=None,
            canonical_command=None,
            confidence=0.0,
            match_reason=match_reason,
            fallback_to_parser=False,
            failure_reason=failure_reason,
        )

    def _contains_any(self, normalized_text: str, phrases: tuple[str, ...]) -> bool:
        return any(self._contains_phrase(normalized_text, phrase) for phrase in phrases)

    def _contains_phrase(self, normalized_text: str, phrase: str) -> bool:
        text_tokens = normalized_text.split()
        phrase_tokens = self._normalize_text(phrase).split()
        if not phrase_tokens:
            return False
        for start in range(0, len(text_tokens) - len(phrase_tokens) + 1):
            if text_tokens[start : start + len(phrase_tokens)] == phrase_tokens:
                return True
        return False

    def _normalize_text(self, raw_input: str) -> str:
        return " ".join(re.sub(r"[^a-z0-9]+", " ", raw_input.lower()).split())

    def _fallback(self, reason: str) -> InterpretedInput:
        return InterpretedInput(
            normalized_intent=None,
            target_text=None,
            target_reference=None,
            canonical_command=None,
            confidence=0.0,
            match_reason=reason,
            fallback_to_parser=True,
        )
