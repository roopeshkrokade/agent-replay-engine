from dataclasses import dataclass
from typing import Mapping, Any, Optional
from .enums import NodeKind
from .metadata import NodeMetadata
from .identifiers import NodeId

@dataclass(frozen=True)
class ExecutionNode:
    """
    An immutable, discrete step within the execution workflow.
    """
    id: NodeId
    kind: NodeKind
    input: Mapping[str, Any]
    output: Optional[Mapping[str, Any]]
    metadata: NodeMetadata