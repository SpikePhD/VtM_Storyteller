from __future__ import annotations

from .command_models import (
    Command,
    HelpCommand,
    InvestigateCommand,
    LoadCommand,
    LookCommand,
    MoveCommand,
    QuitCommand,
    SaveCommand,
    StatusCommand,
    WaitCommand,
)
from .exceptions import CommandParseError


def parse_command(raw_input: str) -> Command:
    normalized_input = " ".join(raw_input.strip().split())
    if not normalized_input:
        raise CommandParseError("input cannot be empty")

    tokens = normalized_input.split(" ")
    keyword = tokens[0].lower()
    args = tokens[1:]

    if keyword == "look":
        if args:
            raise CommandParseError("look does not accept arguments")
        return LookCommand()

    if keyword == "status":
        if args:
            raise CommandParseError("status does not accept arguments")
        return StatusCommand()

    if keyword == "help":
        if args:
            raise CommandParseError("help does not accept arguments")
        return HelpCommand()

    if keyword == "investigate":
        if args:
            raise CommandParseError("investigate does not accept arguments")
        return InvestigateCommand()

    if keyword == "save":
        if args:
            raise CommandParseError("save does not accept arguments")
        return SaveCommand()

    if keyword == "load":
        if args:
            raise CommandParseError("load does not accept arguments")
        return LoadCommand()

    if keyword == "quit":
        if args:
            raise CommandParseError("quit does not accept arguments")
        return QuitCommand()

    if keyword == "move":
        if len(args) != 1:
            raise CommandParseError("move requires exactly 1 destination_id argument")
        destination_id = args[0]
        if not destination_id:
            raise CommandParseError("move requires exactly 1 destination_id argument")
        return MoveCommand(destination_id=destination_id)

    if keyword == "wait":
        if len(args) != 1:
            raise CommandParseError("wait requires a positive integer number of minutes")
        try:
            minutes = int(args[0])
        except ValueError as exc:
            raise CommandParseError("wait requires a positive integer number of minutes") from exc
        if minutes <= 0:
            raise CommandParseError("wait requires a positive integer number of minutes")
        return WaitCommand(minutes=minutes)

    raise CommandParseError(f"unknown command: {tokens[0]}")
