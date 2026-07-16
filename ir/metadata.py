from dataclasses import dataclass, field
from typing import Mapping, Any

@dataclass(frozen=True)
class GraphMetadata:
    schema_version: str
    source_id: str
    created_at: str
    compiler_version: str

@dataclass(frozen=True)
class NodeMetadata:
    attributes: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class EdgeMetadata:
    attributes: Mapping[str, Any] = field(default_factory=dict)