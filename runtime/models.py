from dataclasses import dataclass
from typing import Any
from ir import NodeId

@dataclass(frozen=True)
class NodeResolution:
    """The result of the Matcher evaluating an incoming request."""
    node_id: NodeId
    confidence: float
    matcher_used: str
    reason: str

@dataclass(frozen=True)
class ReplayResult:
    """The structured outcome of an instruction execution."""
    success: bool
    output: Any
    resolution: NodeResolution