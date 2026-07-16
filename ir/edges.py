from dataclasses import dataclass
from .enums import EdgeKind
from .metadata import EdgeMetadata
from .identifiers import EdgeId, NodeId

@dataclass(frozen=True)
class ExecutionEdge:
    """
    An immutable relationship denoting the flow between two ExecutionNodes.
    """
    id: EdgeId
    source: NodeId
    target: NodeId
    kind: EdgeKind
    metadata: EdgeMetadata