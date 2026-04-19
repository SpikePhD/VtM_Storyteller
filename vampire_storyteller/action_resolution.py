from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .command_models import Command
from .input_interpreter import InterpretedInput


class NormalizationSource(str, Enum):
    INTERPRETED = "interpreted"
    DIRECT_COMMAND = "direct_command"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class NormalizedActionInput:
    raw_input: str
    canonical_command_text: str | None
    command: Command | None
    source: NormalizationSource
    interpretation: InterpretedInput | None = None
    failure_reason: str | None = None

    @property
    def is_success(self) -> bool:
        return self.command is not None

    @property
    def used_interpreter(self) -> bool:
        return self.source is NormalizationSource.INTERPRETED

    @property
    def used_parser_boundary(self) -> bool:
        return self.source is NormalizationSource.DIRECT_COMMAND
