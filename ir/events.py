from dataclasses import dataclass
from typing import Mapping, Any
from .enums import EventKind
from .identifiers import EventId, Timestamp

@dataclass(frozen=True)
class CanonicalEvent:
    """
    A normalized lifecycle event emitted by a Trace Adapter.
    Owned by the Adapter Layer, consumed by the IR Compiler.
    """
    id: EventId
    timestamp: Timestamp
    kind: EventKind
    payload: Mapping[str, Any]