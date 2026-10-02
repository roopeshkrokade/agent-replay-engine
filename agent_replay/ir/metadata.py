from dataclasses import dataclass, field
from typing import Mapping, Any

@dataclass(frozen=True)
class GraphMetadata:
    schema_version: str
    source_id: str
    created_at: str
    compiler_version: str
    # Trace-level context: trace_ids, resource attributes, instrumentation scopes, entrypoint
    attributes: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class NodeMetadata:
    # Raw OTel span attributes, as emitted by the instrumentation
    attributes: Mapping[str, Any] = field(default_factory=dict)
    # Structural OTel span fields: ids, kind, status, timings, scope, events, links
    span: Mapping[str, Any] = field(default_factory=dict)
    # False when the recording is not faithful enough to replay this node
    replayable: bool = True
    replay_note: str = ""

@dataclass(frozen=True)
class EdgeMetadata:
    attributes: Mapping[str, Any] = field(default_factory=dict)
