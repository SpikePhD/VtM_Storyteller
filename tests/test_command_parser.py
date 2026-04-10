from __future__ import annotations

import unittest

from vampire_storyteller.command_models import (
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
from vampire_storyteller.command_parser import parse_command
from vampire_storyteller.exceptions import CommandParseError


class CommandParserTests(unittest.TestCase):
    def test_valid_look(self) -> None:
        self.assertIsInstance(parse_command("look"), LookCommand)

    def test_valid_status(self) -> None:
        self.assertIsInstance(parse_command("status"), StatusCommand)

    def test_valid_help(self) -> None:
        self.assertIsInstance(parse_command("help"), HelpCommand)

    def test_valid_investigate(self) -> None:
        self.assertIsInstance(parse_command("investigate"), InvestigateCommand)

    def test_valid_save(self) -> None:
        self.assertIsInstance(parse_command("save"), SaveCommand)

    def test_valid_load(self) -> None:
        self.assertIsInstance(parse_command("load"), LoadCommand)

    def test_valid_move(self) -> None:
        command = parse_command("move loc_church")
        self.assertIsInstance(command, MoveCommand)
        self.assertEqual(command.destination_id, "loc_church")

    def test_valid_wait(self) -> None:
        command = parse_command("wait 60")
        self.assertIsInstance(command, WaitCommand)
        self.assertEqual(command.minutes, 60)

    def test_valid_quit(self) -> None:
        self.assertIsInstance(parse_command("quit"), QuitCommand)

    def test_empty_input_rejected(self) -> None:
        with self.assertRaises(CommandParseError):
            parse_command("")

    def test_unknown_command_rejected(self) -> None:
        with self.assertRaises(CommandParseError):
            parse_command("inspect")

    def test_look_with_extra_args_rejected(self) -> None:
        with self.assertRaises(CommandParseError):
            parse_command("look now")

    def test_investigate_with_extra_args_rejected(self) -> None:
        with self.assertRaises(CommandParseError):
            parse_command("investigate dock")

    def test_save_with_extra_args_rejected(self) -> None:
        with self.assertRaises(CommandParseError):
            parse_command("save now")

    def test_load_with_extra_args_rejected(self) -> None:
        with self.assertRaises(CommandParseError):
            parse_command("load now")

    def test_move_missing_arg_rejected(self) -> None:
        with self.assertRaises(CommandParseError):
            parse_command("move")

    def test_move_too_many_args_rejected(self) -> None:
        with self.assertRaises(CommandParseError):
            parse_command("move loc_church extra")

    def test_wait_missing_arg_rejected(self) -> None:
        with self.assertRaises(CommandParseError):
            parse_command("wait")

    def test_wait_non_integer_arg_rejected(self) -> None:
        with self.assertRaises(CommandParseError):
            parse_command("wait zero")

    def test_wait_zero_rejected(self) -> None:
        with self.assertRaises(CommandParseError):
            parse_command("wait 0")

    def test_wait_negative_rejected(self) -> None:
        with self.assertRaises(CommandParseError):
            parse_command("wait -1")


if __name__ == "__main__":
    unittest.main()
