import time
from typing import Any, Callable, List
from ir import CanonicalEvent, EventKind, EventId, Timestamp

class LiveRecorder:
    """
    Acts as an in-memory telemetry adapter. 
    Monkey-patches application SDKs to passively record live executions 
    and emit a stream of CanonicalEvents.
    """
    def __init__(self):
        self.events: List[CanonicalEvent] = []
        self.span_counter = 0
        
        # Immediately start the workflow
        self.events.append(CanonicalEvent(
            id=EventId("evt_wf_start"),
            timestamp=Timestamp(str(time.time())),
            kind=EventKind.WORKFLOW_START,
            payload={}
        ))

    def patch(self, target_obj: Any, method_name: str, input_mapper: Callable, node_kind: str):
        """
        Patches a method to record its execution. 
        `node_kind` should be 'MODEL' or 'TOOL'.
        """
        original_method = getattr(target_obj, method_name)

        def recorded_call(*args, **kwargs):
            self.span_counter += 1
            span_id = f"span_{self.span_counter}"
            
            # 1. Map and Record Input (Before the live call)
            mapped_input = input_mapper(*args, **kwargs)
            start_kind = EventKind.MODEL_START if node_kind == "MODEL" else EventKind.TOOL_START
            
            self.events.append(CanonicalEvent(
                id=EventId(f"evt_{span_id}_start"),
                timestamp=Timestamp(str(time.time())),
                kind=start_kind,
                payload={"input": mapped_input, "metadata": {"source": "live_recorder"}}
            ))
            
            print(f"  🔴 [Recorder] Executing LIVE network call for '{method_name}'...")
            
            # 2. Execute the actual original method (Talk to the real internet)
            result = original_method(*args, **kwargs)
            
            # 3. Record Output (After the live call)
            end_kind = EventKind.MODEL_END if node_kind == "MODEL" else EventKind.TOOL_END
            self.events.append(CanonicalEvent(
                id=EventId(f"evt_{span_id}_end"),
                timestamp=Timestamp(str(time.time())),
                kind=end_kind,
                payload={"output": result}
            ))
            
            return result

        setattr(target_obj, method_name, recorded_call)
        return original_method

    def finish(self) -> List[CanonicalEvent]:
        """Closes the workflow and returns the canonicalized event stream."""
        self.events.append(CanonicalEvent(
            id=EventId("evt_wf_end"),
            timestamp=Timestamp(str(time.time())),
            kind=EventKind.WORKFLOW_END,
            payload={}
        ))
        return self.events