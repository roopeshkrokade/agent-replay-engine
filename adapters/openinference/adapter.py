import json
from typing import List, Any
from ir import CanonicalEvent, EventKind, EventId, Timestamp

class OpenInferenceAdapter:
    """
    Translates OpenInference OTel JSON traces into a flat stream 
    of CanonicalEvents.
    """
    
    def parse_file(self, filepath: str) -> List[CanonicalEvent]:
        with open(filepath, 'r') as f:
            spans = json.load(f)
            
        events = []
        
        # 1. Inject WORKFLOW_START
        events.append(CanonicalEvent(
            id=EventId("evt_wf_start"),
            timestamp=Timestamp(spans[0]["start_time"]),
            kind=EventKind.WORKFLOW_START,
            payload={}
        ))
        
        # 2. Translate Spans to START and END events
        for span in spans:
            attrs = span.get("attributes", {})
            oi_kind = attrs.get("openinference.span.kind")
            
            if oi_kind == "LLM":
                start_kind, end_kind = EventKind.MODEL_START, EventKind.MODEL_END
            elif oi_kind == "TOOL":
                start_kind, end_kind = EventKind.TOOL_START, EventKind.TOOL_END
            else:
                continue  # Prune irrelevant OTel spans
                
            # Safely parse JSON strings often found in OTel attributes
            input_val = self._safe_parse_json(attrs.get("input.value", "{}"))
            output_val = self._safe_parse_json(attrs.get("output.value", "{}"))
            
            span_id = span["context"]["span_id"]
            
            # Emit START event
            events.append(CanonicalEvent(
                id=EventId(f"evt_{span_id}_start"),
                timestamp=Timestamp(span["start_time"]),
                kind=start_kind,
                payload={"input": input_val, "metadata": attrs}
            ))
            
            # Emit END event
            events.append(CanonicalEvent(
                id=EventId(f"evt_{span_id}_end"),
                timestamp=Timestamp(span["end_time"]),
                kind=end_kind,
                payload={"output": output_val}
            ))
            
        # 3. Inject WORKFLOW_END
        events.append(CanonicalEvent(
            id=EventId("evt_wf_end"),
            timestamp=Timestamp(spans[-1]["end_time"]),
            kind=EventKind.WORKFLOW_END,
            payload={}
        ))
            
        return events

    def _safe_parse_json(self, val: str) -> Any:
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return {"raw": val}