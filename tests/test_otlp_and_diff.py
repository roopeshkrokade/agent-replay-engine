from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import SpanKind, Status, StatusCode

from agent_replay.adapters.otel import OTelSpanAdapter
from agent_replay.compiler import IRCompiler
from agent_replay.runtime.divergence import diff_tools
from agent_replay.server import otlp


class _Capture(SpanExporter):
    def __init__(self):
        self.spans = []

    def export(self, spans):
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS


def test_otlp_protobuf_round_trip():
    capture = _Capture()
    provider = TracerProvider(resource=Resource.create({"service.name": "svc", "agent_replay.run_id": "run-1"}))
    provider.add_span_processor(SimpleSpanProcessor(capture))
    tracer = provider.get_tracer("my.instrumentation", "1.2.3")
    with tracer.start_as_current_span("agent") as parent:
        parent.set_attribute("openinference.span.kind", "AGENT")
        with tracer.start_as_current_span("chat", kind=SpanKind.CLIENT) as child:
            child.set_attribute("llm.token_count.prompt", 7)
            child.set_attribute("tags", ["a", "b"])
            child.add_event("exception", {"exception.type": "Timeout"})
            child.set_status(Status(StatusCode.ERROR, "boom"))

    decoded = otlp.decode_request(encode_spans(capture.spans))
    by_name = {s["name"]: s for s in decoded}
    agent, chat = by_name["agent"], by_name["chat"]

    assert chat["parent_id"] == agent["context"]["span_id"]
    assert chat["context"]["trace_id"] == agent["context"]["trace_id"] and len(chat["context"]["trace_id"]) == 32
    assert chat["kind"] == "CLIENT" and agent["kind"] == "INTERNAL"
    assert chat["status"] == {"status_code": "ERROR", "description": "boom"}
    assert chat["attributes"] == {"llm.token_count.prompt": 7, "tags": ["a", "b"]}
    assert chat["events"][0]["attributes"] == {"exception.type": "Timeout"}
    assert chat["instrumentation_scope"] == {"name": "my.instrumentation", "version": "1.2.3"}
    assert chat["resource"]["service.name"] == "svc"
    assert set(otlp.group_by_run(decoded)) == {"run-1"}  # run id carried on the resource


def _tool_graph(result: str):
    span = {
        "context": {"trace_id": "t", "span_id": "tool"},
        "start_time_unix_nano": 1, "end_time_unix_nano": 2,
        "attributes": {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "get_weather",
                       "gen_ai.tool.call.arguments": '{"location": "Tokyo"}', "gen_ai.tool.call.result": result},
    }
    return IRCompiler().compile(OTelSpanAdapter().parse_spans([span]))


def test_tool_diff_flags_changed_results():
    recorded = _tool_graph('"75F"')
    assert diff_tools(recorded, _tool_graph('"75F"')) == []
    divergence = diff_tools(recorded, _tool_graph('"60F"'))[0]
    assert divergence["type"] == "tool_output_changed"
    assert divergence["tool"] == "get_weather"
    assert (divergence["expected"]["output"], divergence["got"]["output"]) == ("75F", "60F")
