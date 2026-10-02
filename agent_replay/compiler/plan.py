from dataclasses import dataclass, field
from typing import List, Any, Mapping, Optional, Tuple
from enum import Enum, auto
from agent_replay.ir import NodeId, GraphId, NodeKind

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
    node_kind: Optional[NodeKind] = None

@dataclass(frozen=True)
class Fault:
    """
    An injected failure for a replay step (1-based, counted over served model calls).
    A fault does not advance the cursor, so a client retry receives the recorded response,
    unless `persistent` is set.
    """
    step: int
    status: int = 503
    message: str = "Injected fault: simulated upstream failure"
    persistent: bool = False

@dataclass(frozen=True)
class ReplaySession:
    """The volatile, user-provided runtime configuration."""
    mode: str = "CACHE"  # CACHE or LIVE
    match: str = "RELAXED"  # RELAXED: serve by position; STRICT: request must equal the recording
    faults: Tuple[Fault, ...] = field(default_factory=tuple)

@dataclass(frozen=True)
class ReplayPlan:
    """The immutable sequence of execution instructions (Bytecode)."""
    graph_id: GraphId
    instructions: List[Instruction]
