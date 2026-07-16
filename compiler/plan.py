from dataclasses import dataclass
from typing import List, Any, Mapping
from enum import Enum, auto
from ir import NodeId, GraphId

class InstructionKind(Enum):
    RETURN_RECORDED = auto()
    EXECUTE_LIVE = auto()  # Reserved for future

@dataclass(frozen=True)
class Instruction:
    """An atomic, executable bytecode instruction for the Replay VM."""
    kind: InstructionKind
    node_id: NodeId
    expected_input: Mapping[str, Any]
    output_to_return: Any

@dataclass(frozen=True)
class ReplaySession:
    """The volatile, user-provided runtime configuration."""
    mode: str = "CACHE"  # CACHE or LIVE

@dataclass(frozen=True)
class ReplayPlan:
    """The immutable sequence of execution instructions (Bytecode)."""
    graph_id: GraphId
    instructions: List[Instruction]