import json
import dataclasses
from enum import Enum

class IRJSONEncoder(json.JSONEncoder):
    """Safely serializes IR enums, dataclasses, and Pydantic objects to plain JSON."""
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.name
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)
        # Handle Pydantic v2 (LiteLLM / CrewAI)
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        # Handle Pydantic v1
        if hasattr(obj, "dict"):
            return obj.dict()
        return super().default(obj)