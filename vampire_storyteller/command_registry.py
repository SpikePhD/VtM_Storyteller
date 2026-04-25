from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .command_models import Command, InvestigateCommand, LoadCommand, LookCommand, MoveCommand, QuitCommand, SaveCommand, StatusCommand, TalkCommand, WaitCommand
from .input_interpreter import InputInterpreter, InterpretedInput
from .models import Location, NPC
from .text_renderers import render_help_text
from .world_state import WorldState


class CommandModeKind(str, Enum):
    EXECUTE = "execute"
    START_CONVERSATION = "start_conversation"
    STOP_CONVERSATION = "stop_conversation"
    HELP = "help"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CommandRegistryResult:
    kind: CommandModeKind
    command_text: str | None = None
    command: Command | None = None
    output_text: str | None = None
    target_npc_id: str | None = None
    target_npc_name: str | None = None
    target_location_id: str | None = None
    target_location_name: str | None = None
    interpreted_input: InterpretedInput | None = None


@dataclass(frozen=True, slots=True)
class _CommandFamilySpec:
    family: str
    aliases: tuple[str, ...]
    example: str
    supported: bool
    description: str


class CommandRegistry:
    _UNSUPPORTED_MESSAGE = "That command is recognized, but this action is not implemented yet."

    def __init__(self, command_prefix: str) -> None:
        self._command_prefix = command_prefix
        self._command_families = (
            _CommandFamilySpec("talk", ("talk", "talk to", "talk with"), "talk with Jonas", True, "Start or continue a conversation."),
            _CommandFamilySpec("stop talking", ("stop talking", "quit talking", "bye"), "stop talking", True, "End the active conversation."),
            _CommandFamilySpec("movement", ("go to", "move to"), "go to the docks", True, "Move to a location."),
            _CommandFamilySpec("look", ("look", "look around", "look at"), "look around", True, "Observe the current scene."),
            _CommandFamilySpec("investigate", ("investigate", "search"), "search the cargo stacks", True, "Investigate the current situation."),
            _CommandFamilySpec("session", ("save", "load", "status", "help", "quit", "wait"), "status", True, "Session and utility commands."),
            _CommandFamilySpec("unsupported", ("take", "drop", "activate", "use", "push", "pull", "fight", "fight with"), "take the item", False, "Recognized but not implemented."),
        )

    def classify(
        self,
        command_text: str,
        world_state: WorldState,
        input_interpreter: InputInterpreter,
    ) -> CommandRegistryResult:
        normalized = self._normalize_command_text(command_text, input_interpreter)
        if not normalized:
            return CommandRegistryResult(kind=CommandModeKind.UNKNOWN, output_text=self._build_unknown_help_text())

        if self._is_help_commands(normalized):
            return CommandRegistryResult(kind=CommandModeKind.HELP, output_text=self.build_commands_help_text())

        if self._is_plain_help(normalized):
            return CommandRegistryResult(kind=CommandModeKind.HELP, output_text=render_help_text())

        stop_result = self._parse_stop_talking(normalized)
        if stop_result is not None:
            return stop_result

        unsupported_result = self._parse_unsupported(normalized)
        if unsupported_result is not None:
            return unsupported_result

        talk_result = self._parse_talk(normalized, world_state, input_interpreter)
        if talk_result is not None:
            return talk_result

        movement_result = self._parse_movement(normalized, world_state, input_interpreter)
        if movement_result is not None:
            return movement_result

        look_result = self._parse_look(normalized, input_interpreter)
        if look_result is not None:
            return look_result

        investigate_result = self._parse_investigate(normalized, input_interpreter)
        if investigate_result is not None:
            return investigate_result

        wait_result = self._parse_wait(normalized)
        if wait_result is not None:
            return wait_result

        session_result = self._parse_session_command(normalized)
        if session_result is not None:
            return session_result

        return CommandRegistryResult(kind=CommandModeKind.UNKNOWN, output_text=self._build_unknown_help_text())

    def build_help_text(self) -> str:
        lines = [
            f"Command prefix: {self._command_prefix}",
            "Use the prefix for action and control commands.",
            "Unprefixed text is dialogue during conversation, and reflection outside conversation.",
            "",
            "Examples:",
            f"  {self._command_prefix}talk with Jonas",
            f"  {self._command_prefix}stop talking",
            f"  {self._command_prefix}go to the docks",
            f"  {self._command_prefix}look around",
            f"  {self._command_prefix}search the cargo stacks",
            f"  {self._command_prefix}save",
            f"  {self._command_prefix}status",
        ]
        return "\n".join(lines)

    def build_commands_help_text(self) -> str:
        lines = [
            f"Command prefix: {self._command_prefix}",
            "Registered command families:",
        ]
        for family in self._command_families:
            aliases = " | ".join(f"{self._command_prefix}{alias} <...>" if alias not in {"save", "load", "status", "help", "quit"} else f"{self._command_prefix}{alias}" for alias in family.aliases)
            if family.family == "stop talking":
                aliases = " | ".join(
                    [
                        f"{self._command_prefix}stop talking",
                        f"{self._command_prefix}quit talking",
                        f"{self._command_prefix}bye",
                        f"{self._command_prefix}bye <npc>",
                    ]
                )
            elif family.family == "talk":
                aliases = " | ".join(
                    [
                        f"{self._command_prefix}talk <npc>",
                        f"{self._command_prefix}talk to <npc>",
                        f"{self._command_prefix}talk with <npc>",
                    ]
                )
            elif family.family == "movement":
                aliases = " | ".join(
                    [
                        f"{self._command_prefix}go to <place>",
                        f"{self._command_prefix}move to <place>",
                    ]
                )
            elif family.family == "look":
                aliases = " | ".join(
                    [
                        f"{self._command_prefix}look around",
                        f"{self._command_prefix}look at <target>",
                    ]
                )
            elif family.family == "investigate":
                aliases = " | ".join(
                    [
                        f"{self._command_prefix}investigate <target>",
                        f"{self._command_prefix}search <target>",
                    ]
                )
            elif family.family == "session":
                aliases = " | ".join(
                    [
                        f"{self._command_prefix}help --commands",
                        f"{self._command_prefix}save",
                        f"{self._command_prefix}load",
                        f"{self._command_prefix}wait <minutes>",
                        f"{self._command_prefix}status",
                        f"{self._command_prefix}quit",
                    ]
                )
            elif family.family == "unsupported":
                aliases = " | ".join(
                    [
                        f"{self._command_prefix}take <target>",
                        f"{self._command_prefix}drop <target>",
                        f"{self._command_prefix}activate <target>",
                        f"{self._command_prefix}use <target>",
                        f"{self._command_prefix}push <target>",
                        f"{self._command_prefix}pull <target>",
                        f"{self._command_prefix}fight <target>",
                        f"{self._command_prefix}fight with <target>",
                    ]
                )
            lines.append(f"- {family.family}: {aliases}")
            lines.append(f"  {family.description}")
        lines.extend(
            [
                "",
                "Outside conversation, unprefixed text is reflection.",
                "Inside conversation, unprefixed text is spoken dialogue.",
            ]
        )
        return "\n".join(lines)

    def build_unknown_command_help_text(self) -> str:
        return self._build_unknown_help_text()

    def _normalize_command_text(self, command_text: str, input_interpreter: InputInterpreter) -> str:
        normalized = input_interpreter._normalize_text(command_text)
        return self._strip_first_person_prefix(normalized)

    def _strip_first_person_prefix(self, normalized_text: str) -> str:
        for prefix in ("i am ", "i'm ", "i’d ", "i'd ", "i "):
            if normalized_text.startswith(prefix):
                return normalized_text[len(prefix) :].strip()
        return normalized_text

    def _is_help_commands(self, normalized_text: str) -> bool:
        return normalized_text == "help commands"

    def _is_plain_help(self, normalized_text: str) -> bool:
        return normalized_text == "help"

    def _parse_stop_talking(self, normalized_text: str) -> CommandRegistryResult | None:
        for prefix in ("stop talking", "quit talking", "bye"):
            if normalized_text == prefix or normalized_text.startswith(f"{prefix} "):
                return CommandRegistryResult(
                    kind=CommandModeKind.STOP_CONVERSATION,
                    command_text=normalized_text,
                    output_text="Conversation ended.",
                )
        return None

    def _parse_unsupported(self, normalized_text: str) -> CommandRegistryResult | None:
        for prefix in ("take", "drop", "activate", "use", "push", "pull", "fight with", "fight"):
            if normalized_text == prefix or normalized_text.startswith(f"{prefix} "):
                return CommandRegistryResult(
                    kind=CommandModeKind.UNSUPPORTED,
                    command_text=normalized_text,
                    output_text=self._UNSUPPORTED_MESSAGE,
                )
        return None

    def _parse_talk(
        self,
        normalized_text: str,
        world_state: WorldState,
        input_interpreter: InputInterpreter,
    ) -> CommandRegistryResult | None:
        if not normalized_text.startswith("talk"):
            return None

        target_text = normalized_text.removeprefix("talk").strip()
        if target_text.startswith("with "):
            target_text = target_text.removeprefix("with ").strip()
        elif target_text.startswith("to "):
            target_text = target_text.removeprefix("to ").strip()

        if not target_text:
            return CommandRegistryResult(
                kind=CommandModeKind.UNKNOWN,
                output_text=self._build_unknown_help_text(),
            )

        npc = self._resolve_npc_target(target_text, world_state, input_interpreter)
        if npc is None:
            return CommandRegistryResult(
                kind=CommandModeKind.UNKNOWN,
                output_text=self._build_unknown_help_text(),
            )

        npc_name = npc.name
        if npc.location_id != world_state.player.location_id:
            location = world_state.locations.get(world_state.player.location_id or "")
            location_name = location.name if location is not None else (world_state.player.location_id or "unknown location")
            return CommandRegistryResult(
                kind=CommandModeKind.START_CONVERSATION,
                command_text=f"talk {npc.id}",
                target_npc_id=npc.id,
                target_npc_name=npc_name,
                output_text=f"Talk is blocked: {npc_name} is not present at {location_name}.",
                interpreted_input=self._build_interpreted_start_talk(npc, target_text, npc_name),
            )

        return CommandRegistryResult(
            kind=CommandModeKind.START_CONVERSATION,
            command_text=f"talk {npc.id}",
            target_npc_id=npc.id,
            target_npc_name=npc_name,
            output_text=f"You approach {npc_name}.",
            interpreted_input=self._build_interpreted_start_talk(npc, target_text, npc_name),
        )

    def _parse_movement(
        self,
        normalized_text: str,
        world_state: WorldState,
        input_interpreter: InputInterpreter,
    ) -> CommandRegistryResult | None:
        for prefix in ("go to ", "move to ", "move ", "go "):
            if normalized_text.startswith(prefix):
                target_text = normalized_text.removeprefix(prefix).strip()
                return self._build_move_result(target_text, world_state, input_interpreter)
        return None

    def _build_move_result(
        self,
        target_text: str,
        world_state: WorldState,
        input_interpreter: InputInterpreter,
    ) -> CommandRegistryResult:
        normalized_target = self._strip_leading_article(target_text)
        direct_location_id = None
        if normalized_target.startswith("loc_"):
            direct_location_id = normalized_target
        elif normalized_target.startswith("loc "):
            direct_location_id = "loc_" + normalized_target.removeprefix("loc ").replace(" ", "_")

        if direct_location_id is not None:
            command = MoveCommand(destination_id=direct_location_id)
            return CommandRegistryResult(
                kind=CommandModeKind.EXECUTE,
                command_text=f"move {direct_location_id}",
                command=command,
                interpreted_input=self._build_interpreted_simple("move", f"move {direct_location_id}", "prefixed command registry matched location id"),
            )

        resolved = self._resolve_location_target(normalized_target, world_state, input_interpreter)
        if resolved is None:
            return CommandRegistryResult(kind=CommandModeKind.UNKNOWN, output_text=self._build_unknown_help_text())

        location, target_name = resolved
        command = MoveCommand(destination_id=location.id)
        return CommandRegistryResult(
            kind=CommandModeKind.EXECUTE,
            command_text=f"move {location.id}",
            command=command,
            target_location_id=location.id,
            target_location_name=location.name,
            interpreted_input=self._build_interpreted_move(location, target_name),
        )

    def _parse_look(self, normalized_text: str, input_interpreter: InputInterpreter) -> CommandRegistryResult | None:
        if normalized_text == "look" or normalized_text.startswith("look "):
            command = LookCommand()
            return CommandRegistryResult(
                kind=CommandModeKind.EXECUTE,
                command_text="look",
                command=command,
                interpreted_input=self._build_interpreted_simple("look", "look", "prefixed command registry matched look"),
            )
        return None

    def _parse_investigate(self, normalized_text: str, input_interpreter: InputInterpreter) -> CommandRegistryResult | None:
        if normalized_text.startswith("investigate") or normalized_text.startswith("search"):
            command = InvestigateCommand()
            return CommandRegistryResult(
                kind=CommandModeKind.EXECUTE,
                command_text="investigate",
                command=command,
                interpreted_input=self._build_interpreted_simple("investigate", "investigate", "prefixed command registry matched investigate"),
            )
        return None

    def _parse_wait(self, normalized_text: str) -> CommandRegistryResult | None:
        if not normalized_text.startswith("wait"):
            return None

        wait_text = normalized_text.removeprefix("wait").strip()
        if wait_text.startswith("for "):
            wait_text = wait_text.removeprefix("for ").strip()
        if not wait_text:
            return CommandRegistryResult(kind=CommandModeKind.UNKNOWN, output_text=self._build_unknown_help_text())

        first_token = wait_text.split(" ", 1)[0]
        minutes: int | None
        if first_token.isdigit():
            minutes = int(first_token)
        else:
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
            minutes = number_words.get(first_token)

        if minutes is None or minutes <= 0:
            return CommandRegistryResult(kind=CommandModeKind.UNKNOWN, output_text=self._build_unknown_help_text())

        command = WaitCommand(minutes=minutes)
        return CommandRegistryResult(
            kind=CommandModeKind.EXECUTE,
            command_text=f"wait {minutes}",
            command=command,
            interpreted_input=self._build_interpreted_wait(minutes),
        )

    def _parse_session_command(self, normalized_text: str) -> CommandRegistryResult | None:
        if normalized_text == "save":
            return CommandRegistryResult(
                kind=CommandModeKind.EXECUTE,
                command_text="save",
                command=SaveCommand(),
                interpreted_input=self._build_interpreted_simple("save", "save", "prefixed command registry matched save"),
            )
        if normalized_text == "load":
            return CommandRegistryResult(
                kind=CommandModeKind.EXECUTE,
                command_text="load",
                command=LoadCommand(),
                interpreted_input=self._build_interpreted_simple("load", "load", "prefixed command registry matched load"),
            )
        if normalized_text == "status":
            return CommandRegistryResult(
                kind=CommandModeKind.EXECUTE,
                command_text="status",
                command=StatusCommand(),
                interpreted_input=self._build_interpreted_simple("status", "status", "prefixed command registry matched status"),
            )
        if normalized_text == "quit":
            return CommandRegistryResult(
                kind=CommandModeKind.EXECUTE,
                command_text="quit",
                command=QuitCommand(),
                interpreted_input=self._build_interpreted_simple("quit", "quit", "prefixed command registry matched quit"),
            )
        return None

    def _resolve_npc_target(
        self,
        target_text: str,
        world_state: WorldState,
        input_interpreter: InputInterpreter,
    ) -> NPC | None:
        normalized_target = self._strip_leading_article(target_text)
        matches: list[NPC] = []
        for npc in world_state.npcs.values():
            aliases = [npc.id, input_interpreter._normalize_text(npc.id), input_interpreter._normalize_text(npc.name)]
            aliases.extend(input_interpreter._npc_aliases(npc.name))
            if normalized_target in aliases:
                matches.append(npc)
        if len(matches) != 1:
            return None
        return matches[0]

    def _resolve_location_target(
        self,
        target_text: str,
        world_state: WorldState,
        input_interpreter: InputInterpreter,
    ) -> tuple[Location, str] | None:
        normalized_target = self._strip_leading_article(target_text)
        matches: list[tuple[Location, str]] = []
        for location in world_state.locations.values():
            aliases = [
                location.id,
                input_interpreter._normalize_text(location.id),
                input_interpreter._normalize_text(location.name),
                location.id.removeprefix("loc_"),
            ]
            if location.id.startswith("loc_"):
                aliases.append(location.id.removeprefix("loc_").replace("_", " "))
            aliases.extend(input_interpreter._location_aliases(location))
            for alias in aliases:
                if normalized_target == alias:
                    matches.append((location, alias))
                    break
        if len(matches) != 1:
            return None
        return matches[0]

    def _strip_leading_article(self, target_text: str) -> str:
        normalized = " ".join(target_text.split())
        lowered = normalized.lower()
        for prefix in ("the ", "a ", "an ", "to "):
            if lowered.startswith(prefix):
                return normalized[len(prefix) :].strip()
        return normalized

    def _build_interpreted_simple(self, normalized_intent: str, canonical_command: str, match_reason: str) -> InterpretedInput:
        return InterpretedInput(
            normalized_intent=normalized_intent,
            target_text=None,
            target_reference=None,
            canonical_command=canonical_command,
            confidence=1.0,
            match_reason=match_reason,
            fallback_to_parser=False,
        )

    def _build_interpreted_move(self, location: Location, target_text: str) -> InterpretedInput:
        return InterpretedInput(
            normalized_intent="move",
            target_text=target_text,
            target_reference=location.id,
            canonical_command=f"move {location.id}",
            confidence=1.0,
            match_reason=f"prefixed command registry matched location '{location.name}'",
            fallback_to_parser=False,
        )

    def _build_interpreted_wait(self, minutes: int) -> InterpretedInput:
        return InterpretedInput(
            normalized_intent="wait",
            target_text=str(minutes),
            target_reference=None,
            canonical_command=f"wait {minutes}",
            confidence=1.0,
            match_reason="prefixed command registry matched wait",
            fallback_to_parser=False,
        )

    def _build_interpreted_start_talk(self, npc: NPC, target_text: str, npc_name: str) -> InterpretedInput:
        return InterpretedInput(
            normalized_intent="talk",
            target_text=target_text,
            target_reference=npc.id,
            canonical_command=f"talk {npc.id}",
            confidence=1.0,
            match_reason=f"prefixed command registry matched NPC '{npc_name}'",
            fallback_to_parser=False,
        )

    def _build_unknown_help_text(self) -> str:
        return (
            f"Unknown command. Try {self._command_prefix}help --commands, "
            f"{self._command_prefix}talk with <name>, {self._command_prefix}stop talking, "
            f"{self._command_prefix}go to <place>, {self._command_prefix}look around, or type dialogue without "
            f"{self._command_prefix} once you are in conversation."
        )
