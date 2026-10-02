"""
OTLP/HTTP trace receiver. Any OTel SDK, in any language, can export here with the standard
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:5000/v1/traces.

Spans are decoded into the same dict layout as the OTel JSON span export (see tests/fixtures/sample_trace.json)
and stored raw, grouped by the `agent_replay.run_id` attribute.
"""
import gzip
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, Response
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)
from opentelemetry.proto.common.v1.common_pb2 import AnyValue
from opentelemetry.proto.trace.v1.trace_pb2 import Span, Status

RUN_ID_ATTRIBUTE = "agent_replay.run_id"
UNASSIGNED_RUN = "_unassigned"

_SPAN_KINDS = {
    Span.SPAN_KIND_UNSPECIFIED: "INTERNAL",
    Span.SPAN_KIND_INTERNAL: "INTERNAL",
    Span.SPAN_KIND_SERVER: "SERVER",
    Span.SPAN_KIND_CLIENT: "CLIENT",
    Span.SPAN_KIND_PRODUCER: "PRODUCER",
    Span.SPAN_KIND_CONSUMER: "CONSUMER",
}
_STATUS_CODES = {
    Status.STATUS_CODE_UNSET: "UNSET",
    Status.STATUS_CODE_OK: "OK",
    Status.STATUS_CODE_ERROR: "ERROR",
}


def create_router(store) -> APIRouter:
    router = APIRouter()

    @router.post("/v1/traces", summary="OTLP/HTTP trace ingestion (protobuf)")
    async def receive_traces(request: Request) -> Response:
        body = await request.body()
        if request.headers.get("content-encoding", "").lower() == "gzip":
            body = gzip.decompress(body)
        export = ExportTraceServiceRequest()
        export.ParseFromString(body)
        for run_id, spans in group_by_run(decode_request(export)).items():
            store.add_spans(run_id, spans)
        return Response(
            content=ExportTraceServiceResponse().SerializeToString(),
            media_type="application/x-protobuf",
        )

    return router


def group_by_run(spans: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for span in spans:
        run_id = span["attributes"].get(RUN_ID_ATTRIBUTE) or span["resource"].get(RUN_ID_ATTRIBUTE)
        grouped[run_id or UNASSIGNED_RUN].append(span)
    return grouped


def decode_request(export: ExportTraceServiceRequest) -> List[Dict[str, Any]]:
    spans = []
    for resource_spans in export.resource_spans:
        resource = _attributes(resource_spans.resource.attributes)
        for scope_spans in resource_spans.scope_spans:
            scope = {"name": scope_spans.scope.name or None, "version": scope_spans.scope.version or None}
            for span in scope_spans.spans:
                spans.append(_span(span, resource, scope))
    return spans


def _span(span: Span, resource: Dict[str, Any], scope: Dict[str, Any]) -> Dict[str, Any]:
    parent_id = span.parent_span_id.hex() or None
    return {
        "name": span.name,
        "context": {
            "trace_id": span.trace_id.hex(),
            "span_id": span.span_id.hex(),
            "trace_state": span.trace_state,
            "trace_flags": span.flags & 0xFF,
        },
        "parent_id": parent_id,
        # OTLP flags bits 8/9 carry whether the parent is remote (when known)
        "parent_is_remote": bool(span.flags & 0x200) if parent_id and span.flags & 0x100 else None,
        "kind": _SPAN_KINDS.get(span.kind, "INTERNAL"),
        "start_time": _iso(span.start_time_unix_nano),
        "end_time": _iso(span.end_time_unix_nano),
        "start_time_unix_nano": span.start_time_unix_nano,
        "end_time_unix_nano": span.end_time_unix_nano,
        "status": {
            "status_code": _STATUS_CODES.get(span.status.code, "UNSET"),
            "description": span.status.message or None,
        },
        "attributes": _attributes(span.attributes),
        "events": [
            {"name": e.name, "timestamp": _iso(e.time_unix_nano), "attributes": _attributes(e.attributes)}
            for e in span.events
        ],
        "links": [
            {"trace_id": link.trace_id.hex(), "span_id": link.span_id.hex(), "attributes": _attributes(link.attributes)}
            for link in span.links
        ],
        "resource": resource,
        "instrumentation_scope": scope,
        "dropped_attributes_count": span.dropped_attributes_count,
        "dropped_events_count": span.dropped_events_count,
        "dropped_links_count": span.dropped_links_count,
    }


def _attributes(key_values) -> Dict[str, Any]:
    return {kv.key: _value(kv.value) for kv in key_values}


def _value(value: AnyValue) -> Any:
    which = value.WhichOneof("value")
    if which is None:
        return None
    if which == "array_value":
        return [_value(v) for v in value.array_value.values]
    if which == "kvlist_value":
        return {kv.key: _value(kv.value) for kv in value.kvlist_value.values}
    if which == "bytes_value":
        return value.bytes_value.hex()
    return getattr(value, which)


def _iso(ns: int) -> Optional[str]:
    if not ns:
        return None
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).isoformat()
