import json
from datetime import datetime
from typing import Any, List, Mapping

from agent_replay.ir import CanonicalEvent, EventKind, EventId, Timestamp
from agent_replay.ir import NodeKind
from .dialects import classify, extract_io, recorded_error


class OTelSpanAdapter:
    """
    Translates OTel spans (any instrumentation, any framework) into a time-ordered
    stream of CanonicalEvents. Every span is kept, so the parent/child tree survives;
    classification and payload shape come from the GenAI semantic-convention dialects.
    """

    def parse_file(self, filepath: str) -> List[CanonicalEvent]:
        with open(filepath, "r", encoding="utf-8") as f:
            return self.parse_spans(json.load(f))

    def parse_spans(self, spans: List[Mapping[str, Any]]) -> List[CanonicalEvent]:
        if not spans:
            return []

        ordered = sorted(spans, key=lambda s: span_ns(s, "start"))
        timeline = []  # (timestamp_ns, phase, seq, event); starts sort before ends at equal time

        for seq, span in enumerate(ordered):
            attrs = span.get("attributes", {}) or {}
            dialect, node_kind = classify(attrs)
            node_input, node_output = extract_io(dialect, node_kind, attrs)
            error = recorded_error(span)
            if error is not None and node_kind in (NodeKind.MODEL, NodeKind.EMBEDDING):
                # The caller saw an exception, not a response: replay must raise it again.
                node_output = {"recorded_error": error}

            ctx = span.get("context", {})
            span_id = ctx["span_id"]
            span_info = {
                "trace_id": ctx.get("trace_id"),
                "span_id": span_id,
                "parent_span_id": span.get("parent_id"),
                "parent_is_remote": span.get("parent_is_remote"),
                "name": span.get("name"),
                "span_kind": _span_kind(span.get("kind")),
                "dialect": dialect,
                "start_time": span.get("start_time"),
                "end_time": span.get("end_time"),
                "start_time_unix_nano": span_ns(span, "start"),
                "end_time_unix_nano": span_ns(span, "end"),
                "status": span.get("status") or {"status_code": "UNSET"},
                "events": span.get("events", []),
                "links": span.get("links", []),
                "trace_state": ctx.get("trace_state", ""),
                "trace_flags": ctx.get("trace_flags"),
                "instrumentation_scope": span.get("instrumentation_scope", {}),
                "resource": span.get("resource", {}),
                "dropped_attributes_count": span.get("dropped_attributes_count", 0),
                "dropped_events_count": span.get("dropped_events_count", 0),
                "dropped_links_count": span.get("dropped_links_count", 0),
            }

            timeline.append((span_info["start_time_unix_nano"], 0, seq, CanonicalEvent(
                id=EventId(f"evt_{span_id}_start"),
                timestamp=Timestamp(str(span.get("start_time"))),
                kind=EventKind.SPAN_START,
                payload={
                    "span_id": span_id,
                    "node_kind": node_kind,
                    "input": node_input,
                    "metadata": attrs,
                    "span": span_info,
                },
            )))
            timeline.append((span_info["end_time_unix_nano"], 1, seq, CanonicalEvent(
                id=EventId(f"evt_{span_id}_end"),
                timestamp=Timestamp(str(span.get("end_time"))),
                kind=EventKind.SPAN_END,
                payload={"span_id": span_id, "output": node_output},
            )))

        timeline.sort(key=lambda t: t[:3])
        events = [t[3] for t in timeline]

        return [
            CanonicalEvent(
                id=EventId("evt_wf_start"),
                timestamp=events[0].timestamp,
                kind=EventKind.WORKFLOW_START,
                payload={"trace_ids": sorted({s.get("context", {}).get("trace_id") for s in spans})},
            ),
            *events,
            CanonicalEvent(
                id=EventId("evt_wf_end"),
                timestamp=events[-1].timestamp,
                kind=EventKind.WORKFLOW_END,
                payload={},
            ),
        ]


def span_ns(span: Mapping[str, Any], which: str) -> int:
    nano = span.get(f"{which}_time_unix_nano")
    if nano is not None:
        return int(nano)
    iso = span.get(f"{which}_time")
    if not iso:
        return 0
    dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    return int(dt.timestamp() * 1e9)


def _span_kind(kind: Any) -> str:
    # The OTel JSON export writes "SpanKind.CLIENT"; normalise to "CLIENT".
    if not kind:
        return "INTERNAL"
    return str(kind).split(".")[-1].upper()
