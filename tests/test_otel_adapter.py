"""Any OTel span dialect compiles into the same IR; replay points are deduplicated and ordered."""
from agent_replay.adapters.otel import OTelSpanAdapter
from agent_replay.compiler import IRCompiler, PlanCompiler, ReplaySession
from agent_replay.ir import EdgeKind, NodeKind


def _span(span_id, start, end, attrs, parent=None, trace="t1", name="span"):
    return {
        "context": {"trace_id": trace, "span_id": span_id},
        "parent_id": parent,
        "name": name,
        "kind": "SpanKind.INTERNAL",
        "start_time_unix_nano": start,
        "end_time_unix_nano": end,
        "attributes": attrs,
    }


def _compile(spans):
    return IRCompiler().compile(OTelSpanAdapter().parse_spans(spans))


OI_LLM_WITH_TOOL_CALL = {
    "openinference.span.kind": "LLM",
    "llm.model_name": "gpt-4o",
    "llm.input_messages.0.message.role": "user",
    "llm.input_messages.0.message.content": "Weather in Tokyo?",
    "llm.invocation_parameters": '{"temperature": 0}',
    "llm.output_messages.0.message.role": "assistant",
    "llm.output_messages.0.message.tool_calls.0.tool_call.id": "call_1",
    "llm.output_messages.0.message.tool_calls.0.tool_call.function.name": "get_weather",
    "llm.output_messages.0.message.tool_calls.0.tool_call.function.arguments": '{"location": "Tokyo"}',
    "llm.token_count.prompt": 10,
    "llm.token_count.completion": 5,
}


def test_openinference_flattened_messages_become_openai_completion():
    graph = _compile([_span("s1", 1, 2, OI_LLM_WITH_TOOL_CALL)])
    node = graph.nodes["n_s1"]
    assert node.kind == NodeKind.MODEL
    assert node.input == {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Weather in Tokyo?"}],
        "parameters": {"temperature": 0},
    }
    choice = node.output["choices"][0]
    assert choice["finish_reason"] == "tool_calls"
    assert choice["message"]["tool_calls"][0] == {
        "id": "call_1", "type": "function",
        "function": {"name": "get_weather", "arguments": '{"location": "Tokyo"}'},
    }
    assert node.output["usage"] == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


def test_full_provider_response_in_output_value_is_used_verbatim():
    full = '{"id": "chatcmpl-1", "model": "gpt-4o", "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}]}'
    graph = _compile([_span("s1", 1, 2, {"openinference.span.kind": "LLM", "output.value": full,
                                          "input.value": '{"messages": [{"role": "user", "content": "x"}]}'})])
    node = graph.nodes["n_s1"]
    assert node.output["id"] == "chatcmpl-1"
    assert node.input["messages"] == [{"role": "user", "content": "x"}]


def test_genai_semconv_dialect():
    graph = _compile([_span("s1", 1, 2, {
        "gen_ai.operation.name": "chat",
        "gen_ai.request.model": "gpt-4o",
        "gen_ai.request.temperature": 0.2,
        "gen_ai.system_instructions": '[{"type": "text", "content": "Be brief."}]',
        "gen_ai.input.messages": '[{"role": "user", "parts": [{"type": "text", "content": "hi"}]}]',
        "gen_ai.output.messages": '[{"role": "assistant", "finish_reason": "stop", "parts": [{"type": "text", "content": "hello"}]}]',
        "gen_ai.usage.input_tokens": 3, "gen_ai.usage.output_tokens": 1,
    })])
    node = graph.nodes["n_s1"]
    assert node.kind == NodeKind.MODEL
    assert node.input["messages"] == [{"role": "system", "content": "Be brief."}, {"role": "user", "content": "hi"}]
    assert node.input["parameters"] == {"temperature": 0.2}
    assert node.output["choices"][0]["message"]["content"] == "hello"
    assert node.output["usage"]["total_tokens"] == 4


def test_tree_edges_and_replay_order():
    spans = [
        _span("agent", 0, 100, {"openinference.span.kind": "AGENT"}),
        _span("llm1", 10, 20, OI_LLM_WITH_TOOL_CALL, parent="agent"),
        _span("tool", 30, 40, {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "get_weather",
                               "gen_ai.tool.call.arguments": '{"location": "Tokyo"}',
                               "gen_ai.tool.call.result": "75F"}, parent="agent"),
        _span("http", 31, 39, {"http.method": "GET"}, parent="tool"),
        _span("llm2", 50, 60, OI_LLM_WITH_TOOL_CALL, parent="agent"),
    ]
    graph = _compile(spans)
    assert graph.nodes["n_agent"].kind == NodeKind.AGENT
    assert graph.nodes["n_http"].kind == NodeKind.OTHER  # unknown spans keep the tree intact
    assert graph.nodes["n_tool"].input == {"location": "Tokyo"}

    parents = {(e.source, e.target) for e in graph.edges.values() if e.kind == EdgeKind.PARENT_CHILD}
    assert ("n_agent", "n_llm1") in parents and ("n_tool", "n_http") in parents

    plan = PlanCompiler().compile(graph, ReplaySession())
    assert [i.node_id for i in plan.instructions] == ["n_llm1", "n_tool", "n_llm2"]
    assert graph.nodes["n_agent"].metadata.span["span_kind"] == "INTERNAL"


def test_nested_llm_spans_are_deduplicated():
    spans = [
        _span("outer", 1, 10, OI_LLM_WITH_TOOL_CALL),
        _span("inner", 2, 9, OI_LLM_WITH_TOOL_CALL, parent="outer"),
    ]
    graph = _compile(spans)
    assert not graph.nodes["n_outer"].metadata.replayable
    assert [i.node_id for i in PlanCompiler().compile(graph, ReplaySession()).instructions] == ["n_inner"]


def test_overlapping_llm_spans_without_shared_context_are_deduplicated():
    """Framework and provider instrumentors that do not share context still produce one replay point."""
    spans = [
        {**_span("framework", 1, 10, OI_LLM_WITH_TOOL_CALL), "instrumentation_scope": {"name": "crewai"}},
        {**_span("provider", 2, 9, OI_LLM_WITH_TOOL_CALL), "instrumentation_scope": {"name": "openai"}},  # no parent link
    ]
    graph = _compile(spans)
    assert not graph.nodes["n_framework"].metadata.replayable
    assert graph.nodes["n_provider"].metadata.replayable


def test_parallel_calls_from_one_instrumentor_are_all_replay_points():
    scope = {"instrumentation_scope": {"name": "openai"}}
    spans = [
        {**_span("a", 1, 10, OI_LLM_WITH_TOOL_CALL), **scope},
        {**_span("b", 2, 9, OI_LLM_WITH_TOOL_CALL), **scope},  # runs concurrently inside a's window
    ]
    graph = _compile(spans)
    assert graph.nodes["n_a"].metadata.replayable and graph.nodes["n_b"].metadata.replayable


def test_unfaithful_spans_are_not_replay_points():
    dropped = {**_span("dropped", 1, 2, OI_LLM_WITH_TOOL_CALL), "dropped_attributes_count": 3}
    empty = _span("empty", 5, 6, {"openinference.span.kind": "LLM"})
    no_vectors = _span("emb", 7, 8, {"openinference.span.kind": "EMBEDDING", "embedding.embeddings.0.embedding.text": "x"})
    graph = _compile([dropped, empty, no_vectors])
    notes = {nid: n.metadata.replay_note for nid, n in graph.nodes.items()}
    assert all(not n.metadata.replayable for n in graph.nodes.values()), notes
    assert PlanCompiler().compile(graph, ReplaySession()).instructions == []


def test_failed_calls_replay_their_error():
    failed = {
        **_span("failed", 1, 2, {"openinference.span.kind": "LLM"}),
        "status": {"status_code": "ERROR", "description": "RateLimitError"},
        "events": [{"name": "exception", "attributes": {
            "exception.type": "openai.RateLimitError",
            "exception.message": "Error code: 429 - {'error': {'message': 'Slow down', 'type': 'rate_limit'}}",
        }}],
    }
    node = _compile([failed]).nodes["n_failed"]
    assert node.metadata.replayable
    assert node.output["recorded_error"] == {
        "status": 429, "type": "openai.RateLimitError",
        "message": "Error code: 429 - {'error': {'message': 'Slow down', 'type': 'rate_limit'}}",
        "body": {"error": {"message": "Slow down", "type": "rate_limit"}},
    }


def test_embeddings_are_replay_points():
    attrs = {
        "openinference.span.kind": "EMBEDDING",
        "embedding.model_name": "text-embedding-3-small",
        "embedding.embeddings.0.embedding.text": "hello",
        "embedding.embeddings.0.embedding.vector": [0.1, 0.2],
    }
    node = _compile([_span("e", 1, 2, attrs)]).nodes["n_e"]
    assert node.kind == NodeKind.EMBEDDING and node.metadata.replayable
    assert node.input == {"model": "text-embedding-3-small", "input": ["hello"]}
    assert node.output["data"] == [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}]
