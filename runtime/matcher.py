from typing import Any, Mapping
from compiler import Instruction
from .models import NodeResolution

class ExactMatcher:
    """Resolves an incoming SDK request to a Replay Plan instruction using exact parity."""
    
    def resolve(self, app_input: Mapping[str, Any], instruction: Instruction) -> NodeResolution:
        # In MVP, we assume the app queries the VM sequentially. 
        # We verify parity against the instruction at the current cursor.
        if app_input == instruction.expected_input:
            return NodeResolution(
                node_id=instruction.node_id,
                confidence=1.0,
                matcher_used="ExactMatcher",
                reason="Incoming payload exactly matched the recorded historical input."
            )
        else:
            return NodeResolution(
                node_id=instruction.node_id,
                confidence=0.0,
                matcher_used="ExactMatcher",
                reason=f"Input mismatch. Expected {instruction.expected_input}, got {app_input}"
            )