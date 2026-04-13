from __future__ import annotations

import re
from dataclasses import dataclass

from .command_models import DialogueAct, DialogueMetadata
from .world_state import WorldState


@dataclass(frozen=True, slots=True)
class InterpretedInput:
    normalized_intent: str | None
    target_text: str | None
    target_reference: str | None
    canonical_command: str | None
    confidence: float
    match_reason: str
    fallback_to_parser: bool
    dialogue_metadata: DialogueMetadata | None = None


class InputInterpreter:
    def interpret(self, raw_input: str, world_state: WorldState) -> InterpretedInput:
        normalized_text = self._normalize_text(raw_input)
        if not normalized_text:
            return self._fallback("input was empty after normalization")

        talk_result = self._interpret_talk(raw_input, normalized_text, world_state)
        if talk_result is not None:
            return talk_result

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
        if self._contains_any(normalized_text, ("investigate", "inspect", "search", "something wrong", "what is wrong", "wrong", "disturbed")):
            return InterpretedInput(
                normalized_intent="investigate",
                target_text=None,
                target_reference=None,
                canonical_command="investigate",
                confidence=0.9,
                match_reason="observation text suggested active investigation",
                fallback_to_parser=False,
            )

        if self._contains_any(normalized_text, ("look", "observe", "watch", "examine", "take a look")):
            return InterpretedInput(
                normalized_intent="look",
                target_text=None,
                target_reference=None,
                canonical_command="look",
                confidence=0.85,
                match_reason="observation text suggested a basic look action",
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

    def _interpret_talk(self, raw_input: str, normalized_text: str, world_state: WorldState) -> InterpretedInput | None:
        npc_match = self._match_npc(normalized_text, world_state)
        if npc_match is None:
            return None

        speech_text = self._extract_speech_text(raw_input, npc_match["matched_text"])
        normalized_speech_text = self._normalize_text(speech_text)
        dialogue_act = self._classify_dialogue_act(raw_input, speech_text, normalized_speech_text)
        direct_address = self._looks_like_direct_address(raw_input, npc_match["matched_text"])

        if dialogue_act is DialogueAct.UNKNOWN and not direct_address:
            return None

        metadata = DialogueMetadata(
            utterance_text=raw_input.strip(),
            speech_text=speech_text,
            dialogue_act=dialogue_act,
        )
        return InterpretedInput(
            normalized_intent="talk",
            target_text=npc_match["matched_text"],
            target_reference=npc_match["npc_id"],
            canonical_command=f"talk {npc_match['npc_id']}",
            confidence=0.95 if dialogue_act is not DialogueAct.UNKNOWN else 0.8,
            match_reason=f"speech text matched NPC '{npc_match['matched_text']}' and classified as {dialogue_act.value}",
            fallback_to_parser=False,
            dialogue_metadata=metadata,
        )

    def _classify_dialogue_act(self, raw_input: str, speech_text: str, normalized_speech_text: str) -> DialogueAct:
        if not normalized_speech_text:
            return DialogueAct.UNKNOWN

        if self._contains_any(
            normalized_speech_text,
            ("good morning", "good afternoon", "good evening", "good night", "hello", "hi", "hey", "greetings"),
        ):
            return DialogueAct.GREET

        if self._contains_any(
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
            ),
        ):
            return DialogueAct.ACCUSE

        if self._contains_any(
            normalized_speech_text,
            (
                "or else",
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
            normalized_speech_text,
            (
                "i need you to",
                "trust me",
                "help me",
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

        if "?" in speech_text or self._contains_any(
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
                "tell me",
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

    def _match_npc(self, normalized_text: str, world_state: WorldState) -> dict[str, str] | None:
        best_match: dict[str, str] | None = None
        for npc in world_state.npcs.values():
            aliases = self._npc_aliases(npc.name)
            match = self._match_alias(normalized_text, aliases)
            if match is None:
                continue
            if best_match is None or len(match["matched_text"].split()) > len(best_match["matched_text"].split()):
                best_match = {
                    "npc_id": npc.id,
                    "matched_text": match["matched_text"],
                }
        return best_match

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
        pattern = rf"^\s*{re.escape(matched_text)}\s*[,!:.-]?\s*"
        match = re.match(pattern, raw_input, flags=re.IGNORECASE)
        if match is None:
            return raw_input.strip()
        return raw_input[match.end():].strip()

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
