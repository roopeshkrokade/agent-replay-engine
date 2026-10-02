from dataclasses import dataclass
from typing import Mapping
from .metadata import GraphMetadata
from .nodes import ExecutionNode
from .edges import ExecutionEdge
from .identifiers import GraphId, NodeId, EdgeId

@dataclass(frozen=True)
class ExecutionGraph:
    """
    The provider-agnostic, immutable Intermediate Representation (IR) 
    of an agentic workflow. 
    """
    id: GraphId
    metadata: GraphMetadata
    nodes: Mapping[NodeId, ExecutionNode]
    edges: Mapping[EdgeId, ExecutionEdge]