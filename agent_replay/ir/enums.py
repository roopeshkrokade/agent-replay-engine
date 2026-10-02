from enum import Enum, auto

class NodeKind(Enum):
    MODEL = auto()
    TOOL = auto()
    AGENT = auto()
    WORKFLOW = auto()
    CHAIN = auto()
    RETRIEVER = auto()
    EMBEDDING = auto()
    INPUT = auto()
    OUTPUT = auto()
    OTHER = auto()  # Span with no recognised GenAI semantics; kept so the tree stays intact

class EdgeKind(Enum):
    SEQUENTIAL = auto()
    CONDITIONAL = auto()
    RETRY = auto()
    ERROR = auto()
    PARENT_CHILD = auto()  # From the OTel parent_span_id relationship

class EventKind(Enum):
    WORKFLOW_START = auto()
    WORKFLOW_END = auto()
    # One START/END pair per OTel span; payload["node_kind"] carries the classification
    SPAN_START = auto()
    SPAN_END = auto()
