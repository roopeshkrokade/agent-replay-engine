from enum import Enum, auto

class NodeKind(Enum):
    MODEL = auto()
    TOOL = auto()
    AGENT = auto()
    WORKFLOW = auto()
    INPUT = auto()
    OUTPUT = auto()

class EdgeKind(Enum):
    SEQUENTIAL = auto()
    CONDITIONAL = auto()
    RETRY = auto()
    ERROR = auto()

class EventKind(Enum):
    WORKFLOW_START = auto()
    WORKFLOW_END = auto()
    MODEL_START = auto()
    MODEL_END = auto()
    TOOL_START = auto()
    TOOL_END = auto()