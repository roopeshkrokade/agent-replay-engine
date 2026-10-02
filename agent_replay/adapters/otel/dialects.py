"""
Semantic-convention dialects for GenAI spans.

Instrumentors describe the same thing with different attribute names. Each dialect maps
a span's attributes onto our canonical shapes:
  - NodeKind classification
  - model input  -> {"model", "messages", "parameters", "tools"}
  - model output -> OpenAI chat-completion dict (provider-neutral wire format)

Supported: OpenInference (openinference.*, llm.*) and OTel GenAI semconv (gen_ai.*).
"""
import ast
import json
import re
from typing import Any, Dict, List, Mapping, Optional, Tuple

from agent_replay.ir import NodeKind

OPENINFERENCE = "openinference"
GENAI = "otel_genai"
UNKNOWN = "unknown"

_OPENINFERENCE_KINDS = {
    "LLM": NodeKind.MODEL,
    "TOOL": NodeKind.TOOL,
    "AGENT": NodeKind.AGENT,
    "CHAIN": NodeKind.CHAIN,
    "RETRIEVER": NodeKind.RETRIEVER,
    "EMBEDDING": NodeKind.EMBEDDING,
}

_GENAI_OPERATIONS = {
    "chat": NodeKind.MODEL,
    "text_completion": NodeKind.MODEL,
    "generate_content": NodeKind.MODEL,
    "execute_tool": NodeKind.TOOL,
    "invoke_agent": NodeKind.AGENT,
    "create_agent": NodeKind.AGENT,
    "embeddings": NodeKind.EMBEDDING,
}


def classify(attrs: Mapping[str, Any]) -> Tuple[str, NodeKind]:
    """Classify from GenAI semantics; OTel SpanKind is too coarse to tell an LLM call from any other CLIENT call."""
    oi_kind = attrs.get("openinference.span.kind")
    if oi_kind:
        return OPENINFERENCE, _OPENINFERENCE_KINDS.get(str(oi_kind).upper(), NodeKind.OTHER)
    operation = attrs.get("gen_ai.operation.name")
    if operation:
        return GENAI, _GENAI_OPERATIONS.get(str(operation), NodeKind.OTHER)
    return UNKNOWN, NodeKind.OTHER


def extract_io(dialect: str, node_kind: NodeKind, attrs: Mapping[str, Any]) -> Tuple[Any, Any]:
    if node_kind == NodeKind.MODEL:
        if dialect == OPENINFERENCE:
            model_input, model_output = _oi_model_input(attrs), _oi_model_output(attrs)
        else:
            model_input, model_output = _genai_model_input(attrs), _genai_model_output(attrs)
        return (
            model_input if model_input is not None else _generic_input(attrs),
            model_output if model_output is not None else _generic_output(attrs),
        )
    if node_kind == NodeKind.EMBEDDING:
        return _embedding_input(attrs), _embedding_output(attrs)
    if node_kind == NodeKind.TOOL and dialect == GENAI:
        return (
            parse_json(attrs.get("gen_ai.tool.call.arguments", "{}")),
            parse_json(attrs.get("gen_ai.tool.call.result")) if "gen_ai.tool.call.result" in attrs else None,
        )
    return _generic_input(attrs), _generic_output(attrs)


def recorded_error(span: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """
    For a failed span, what the caller saw: HTTP status, error type and provider error body.
    SDKs format HTTP errors as "Error code: 429 - {...}", which we parse back.
    """
    status = span.get("status") or {}
    if status.get("status_code") != "ERROR":
        return None
    exception = next((e.get("attributes", {}) for e in span.get("events", []) if e.get("name") == "exception"), {})
    message = exception.get("exception.message") or status.get("description") or "Recorded call failed"
    error: Dict[str, Any] = {
        "status": 500,
        "type": exception.get("exception.type") or "error",
        "message": message,
        "body": None,
    }
    match = re.search(r"Error code: (\d{3})(?: - (.*))?", message, re.S)
    if match:
        error["status"] = int(match.group(1))
        if match.group(2):
            try:
                error["body"] = ast.literal_eval(match.group(2).strip())
            except (ValueError, SyntaxError):
                error["body"] = parse_json(match.group(2).strip())
    elif "connection" in error["type"].lower() or "timeout" in error["type"].lower():
        error["status"] = 503
    return error


def tool_name(attrs: Mapping[str, Any]) -> Optional[str]:
    return attrs.get("tool.name") or attrs.get("gen_ai.tool.name")


def parse_json(val: Any) -> Any:
    if not isinstance(val, str):
        return val
    try:
        return json.loads(val)
    except json.JSONDecodeError:
        return {"raw": val}


def _generic_input(attrs: Mapping[str, Any]) -> Any:
    return parse_json(attrs.get("input.value", "{}"))


def _generic_output(attrs: Mapping[str, Any]) -> Any:
    if "output.value" not in attrs:
        return None
    return parse_json(attrs["output.value"])


# ---------------------------------------------------------
# Embeddings (OpenInference records vectors; the GenAI conventions do not)
# ---------------------------------------------------------
def _embedding_input(attrs: Mapping[str, Any]) -> Dict[str, Any]:
    texts = [e.get("embedding", {}).get("text") for e in _unflatten_list(attrs, "embedding.embeddings")]
    texts = [t for t in texts if t is not None]
    if not texts:
        raw = parse_json(attrs.get("input.value")) if "input.value" in attrs else None
        raw_input = raw.get("input") if isinstance(raw, dict) else raw
        if raw_input is not None:
            texts = raw_input if isinstance(raw_input, list) else [raw_input]
    model = attrs.get("embedding.model_name") or attrs.get("gen_ai.request.model")
    return {"model": model, "input": texts}


def _embedding_output(attrs: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    vectors = [e.get("embedding", {}).get("vector") for e in _unflatten_list(attrs, "embedding.embeddings")]
    if not vectors or any(v is None for v in vectors):
        return None
    prompt_tokens = attrs.get("llm.token_count.prompt") or attrs.get("gen_ai.usage.input_tokens") or 0
    return {
        "object": "list",
        "model": attrs.get("embedding.model_name") or attrs.get("gen_ai.response.model"),
        "data": [{"object": "embedding", "index": i, "embedding": list(v)} for i, v in enumerate(vectors)],
        "usage": {"prompt_tokens": int(prompt_tokens), "total_tokens": int(prompt_tokens)},
    }


# ---------------------------------------------------------
# OpenInference
# ---------------------------------------------------------
def _oi_model_input(attrs: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    messages = [_oi_message(m) for m in _unflatten_list(attrs, "llm.input_messages")]
    if not messages:
        raw = parse_json(attrs.get("input.value")) if "input.value" in attrs else None
        if isinstance(raw, dict) and isinstance(raw.get("messages"), list):
            messages = raw["messages"]
    if not messages:
        return None
    model_input: Dict[str, Any] = {"model": attrs.get("llm.model_name"), "messages": messages}
    if "llm.invocation_parameters" in attrs:
        model_input["parameters"] = parse_json(attrs["llm.invocation_parameters"])
    tools = [t.get("tool", {}).get("json_schema") for t in _unflatten_list(attrs, "llm.tools")]
    if tools:
        model_input["tools"] = [parse_json(t) for t in tools if t]
    return model_input


def _oi_model_output(attrs: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    # Some instrumentors store the full provider response as JSON; that is the most faithful form.
    raw = parse_json(attrs.get("output.value")) if "output.value" in attrs else None
    if isinstance(raw, dict) and "choices" in raw:
        return raw

    messages = [_oi_message(m) for m in _unflatten_list(attrs, "llm.output_messages")]
    if not messages:
        return None
    usage = _usage(
        attrs.get("llm.token_count.prompt"),
        attrs.get("llm.token_count.completion"),
        attrs.get("llm.token_count.total"),
    )
    return chat_completion(messages, attrs.get("llm.model_name"), attrs.get("llm.finish_reason"), usage, None)


def _oi_message(entry: Mapping[str, Any]) -> Dict[str, Any]:
    msg = entry.get("message", entry)
    out: Dict[str, Any] = {"role": msg.get("role")}
    content = msg.get("content")
    if content is None and msg.get("contents"):
        content = "".join(
            c.get("message_content", {}).get("text", "") for c in msg["contents"]
            if c.get("message_content", {}).get("type", "text") == "text"
        )
    out["content"] = content
    tool_calls = [
        {
            "id": tc.get("tool_call", {}).get("id"),
            "type": "function",
            "function": {
                "name": tc.get("tool_call", {}).get("function", {}).get("name"),
                "arguments": _as_json_string(tc.get("tool_call", {}).get("function", {}).get("arguments")),
            },
        }
        for tc in msg.get("tool_calls", [])
    ]
    if tool_calls:
        out["tool_calls"] = tool_calls
    if msg.get("tool_call_id"):
        out["tool_call_id"] = msg["tool_call_id"]
    if msg.get("name"):
        out["name"] = msg["name"]
    return out


def _unflatten_list(attrs: Mapping[str, Any], prefix: str) -> List[Dict[str, Any]]:
    """
    OpenInference flattens lists into indexed keys, e.g.
    llm.output_messages.0.message.tool_calls.0.tool_call.function.name -> nested dicts/lists.
    """
    if isinstance(attrs.get(prefix), str):  # some exporters keep the list as one JSON string
        value = parse_json(attrs[prefix])
        return value if isinstance(value, list) else []

    root: Dict[Any, Any] = {}
    marker = prefix + "."
    for key, value in attrs.items():
        if not key.startswith(marker):
            continue
        node = root
        parts = [int(p) if p.isdigit() else p for p in key[len(marker):].split(".")]
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    result = _listify(root)
    return result if isinstance(result, list) else []


def _listify(node: Any) -> Any:
    if not isinstance(node, dict):
        return node
    if node and all(isinstance(k, int) for k in node):
        return [_listify(node[k]) for k in sorted(node)]
    return {k: _listify(v) for k, v in node.items()}


# ---------------------------------------------------------
# OTel GenAI semantic conventions
# ---------------------------------------------------------
def _genai_model_input(attrs: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    raw_messages = parse_json(attrs.get("gen_ai.input.messages", "[]"))
    if not isinstance(raw_messages, list) or not raw_messages:
        return None
    messages: List[Dict[str, Any]] = []
    system = parse_json(attrs.get("gen_ai.system_instructions", "[]"))
    if isinstance(system, list) and system:
        messages.append({"role": "system", "content": _genai_text(system)})
    for m in raw_messages:
        messages.extend(_genai_message(m))
    parameters = {
        key[len("gen_ai.request."):]: value
        for key, value in attrs.items()
        if key.startswith("gen_ai.request.") and key != "gen_ai.request.model"
    }
    model_input: Dict[str, Any] = {"model": attrs.get("gen_ai.request.model"), "messages": messages}
    if parameters:
        model_input["parameters"] = parameters
    if "gen_ai.tool.definitions" in attrs:
        model_input["tools"] = parse_json(attrs["gen_ai.tool.definitions"])
    return model_input


def _genai_model_output(attrs: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    raw_messages = parse_json(attrs.get("gen_ai.output.messages", "[]"))
    if not isinstance(raw_messages, list) or not raw_messages:
        return None
    messages, finish_reasons = [], []
    for m in raw_messages:
        messages.extend(_genai_message(m))
        finish_reasons.append(m.get("finish_reason"))
    response_finish = attrs.get("gen_ai.response.finish_reasons") or []
    usage = _usage(attrs.get("gen_ai.usage.input_tokens"), attrs.get("gen_ai.usage.output_tokens"), None)
    completion = chat_completion(
        messages,
        attrs.get("gen_ai.response.model") or attrs.get("gen_ai.request.model"),
        None,
        usage,
        attrs.get("gen_ai.response.id"),
    )
    for i, choice in enumerate(completion["choices"]):
        reason = finish_reasons[i] if i < len(finish_reasons) else None
        if reason is None and i < len(response_finish):
            reason = response_finish[i]
        if reason:
            choice["finish_reason"] = reason
    return completion


def _genai_message(m: Mapping[str, Any]) -> List[Dict[str, Any]]:
    parts = m.get("parts", [])
    role = m.get("role")
    tool_responses = [p for p in parts if p.get("type") == "tool_call_response"]
    if tool_responses:
        return [
            {"role": "tool", "tool_call_id": p.get("id"), "content": _as_json_string(p.get("response"))}
            for p in tool_responses
        ]
    out: Dict[str, Any] = {"role": role, "content": _genai_text(parts) or None}
    tool_calls = [
        {
            "id": p.get("id"),
            "type": "function",
            "function": {"name": p.get("name"), "arguments": _as_json_string(p.get("arguments"))},
        }
        for p in parts if p.get("type") == "tool_call"
    ]
    if tool_calls:
        out["tool_calls"] = tool_calls
    return [out]


def _genai_text(parts: List[Mapping[str, Any]]) -> str:
    return "".join(p.get("content", "") for p in parts if p.get("type") == "text")


# ---------------------------------------------------------
# Shared builders
# ---------------------------------------------------------
def chat_completion(
    messages: List[Dict[str, Any]],
    model: Optional[str],
    finish_reason: Optional[str],
    usage: Optional[Dict[str, int]],
    response_id: Optional[str],
) -> Dict[str, Any]:
    choices = []
    for i, msg in enumerate(messages):
        message = {"role": msg.get("role") or "assistant", "content": msg.get("content")}
        if msg.get("tool_calls"):
            message["tool_calls"] = msg["tool_calls"]
        choices.append({
            "index": i,
            "message": message,
            "finish_reason": finish_reason or ("tool_calls" if msg.get("tool_calls") else "stop"),
        })
    completion: Dict[str, Any] = {"object": "chat.completion", "model": model, "choices": choices}
    if response_id:
        completion["id"] = response_id
    if usage:
        completion["usage"] = usage
    return completion


def _usage(prompt: Any, completion: Any, total: Any) -> Optional[Dict[str, int]]:
    if prompt is None and completion is None:
        return None
    prompt, completion = int(prompt or 0), int(completion or 0)
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": int(total) if total is not None else prompt + completion,
    }


def _as_json_string(value: Any) -> Any:
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value)
