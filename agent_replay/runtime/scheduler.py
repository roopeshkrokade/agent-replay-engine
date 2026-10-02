from dataclasses import dataclass
from typing import Any, Iterable, List, Mapping, Optional, Sequence

from agent_replay.compiler import Instruction
from agent_replay.ir import NodeKind
from .matcher import canonical_request


@dataclass(frozen=True)
class Resolution:
    instruction: Optional[Instruction]
    diverged: bool
    reason: str
    expected: Any = None  # canonical recorded request closest to this one, for divergence reports


class ReplayScheduler:
    """
    Serves recorded calls by content rather than arrival order, so concurrent or reordered
    requests each get the response that was recorded for them.

    A request takes the first unserved recorded call of the same kind with an identical
    (canonical) request. Failing that, RELAXED mode falls back to the first unserved call and
    reports the difference; STRICT mode refuses it.
    """

    def __init__(self, instructions: Sequence[Instruction], strict: bool = False):
        self.instructions = list(instructions)
        self.strict = strict
        self._served = [False] * len(self.instructions)

    @property
    def served_count(self) -> int:
        return sum(self._served)

    @property
    def total(self) -> int:
        return len(self.instructions)

    def unserved(self) -> List[Instruction]:
        return [i for i, done in zip(self.instructions, self._served) if not done]

    def resolve(self, request: Mapping[str, Any], kinds: Iterable[NodeKind]) -> Resolution:
        kinds = set(kinds)
        candidates = [
            idx for idx, instr in enumerate(self.instructions)
            if not self._served[idx] and (instr.node_kind in kinds or instr.node_kind is None)
        ]
        if not candidates:
            recorded = sum(1 for i in self.instructions if i.node_kind in kinds or i.node_kind is None)
            return Resolution(None, True, f"Agent made more calls than the {recorded} recorded.")

        wanted = canonical_request(request)
        for idx in candidates:
            if canonical_request(self.instructions[idx].expected_input) == wanted:
                return self._serve(idx, False, "Request matched the recording.")

        first = candidates[0]
        expected = canonical_request(self.instructions[first].expected_input)
        if self.strict:
            return Resolution(None, True, "Request differs from every remaining recorded call.", expected)
        resolution = self._serve(first, True, "Served the next recorded call; the request differs from the recording.")
        return Resolution(resolution.instruction, True, resolution.reason, expected)

    def _serve(self, idx: int, diverged: bool, reason: str) -> Resolution:
        self._served[idx] = True
        instruction = self.instructions[idx]
        return Resolution(instruction, diverged, reason, canonical_request(instruction.expected_input))
