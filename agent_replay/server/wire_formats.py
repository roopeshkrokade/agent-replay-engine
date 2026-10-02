"""
Provider wire formats spoken by the replay gateway.

Recordings store every model output as an OpenAI chat-completion dict (see adapters/otel/dialects).
Here each API's request is parsed into the canonical {"model", "messages"} (or {"model", "input"}
for embeddings) used for matching, and a recorded output is rendered back in the API's response
shape, including its streaming (SSE) event protocol.

  chat       POST /v1/chat/completions   OpenAI Chat Completions
  responses  POST /v1/responses          OpenAI Responses
  messages   POST /v1/messages           Anthropic Messages
  embeddings POST /v1/embeddings         OpenAI Embeddings
"""
import base64
import copy
import json
import struct
import time
from typing import Any, Dict, Iterator, List, Mapping, Optional

CHAT, RESPONSES, MESSAGES, EMBEDDINGS = "chat", "responses", "messages", "embeddings"

_TO_OPENAI_FINISH = {"end_turn": "stop", "stop_sequence": "stop", "tool_use": "tool_calls", "max_tokens": "length"}
_TO_ANTHROPIC_STOP = {"stop": "end_turn", "tool_calls": "tool_use", "function_call": "tool_use", "length": "max_tokens"}


# ---------------------------------------------------------
# Requests -> canonical input
# ---------------------------------------------------------
def chat_request(body: Mapping[str, Any]) -> Dict[str, Any]:
    return {"model": body.get("model"), "messages": list(body.get("messages") or [])}


def anthropic_request(body: Mapping[str, Any]) -> Dict[str, Any]:
    messages: List[Dict[str, Any]] = []
    system = body.get("system")
    if system:
        messages.append({"role": "system", "content": _blocks_text(system)})
    for m in body.get("messages") or []:
        content = m.get("content")
        if isinstance(content, str):
            messages.append({"role": m.get("role"), "content": content})
            continue
        blocks = content or []
        results = [b for b in blocks if b.get("type") == "tool_result"]
        for r in results:
            messages.append({"role": "tool", "tool_call_id": r.get("tool_use_id"), "content": _blocks_text(r.get("content"))})
        rest = [b for b in blocks if b.get("type") != "tool_result"]
        if rest or not results:
            msg: Dict[str, Any] = {"role": m.get("role"), "content": _blocks_text(rest)}
            calls = [
                {"id": b.get("id"), "type": "function",
                 "function": {"name": b.get("name"), "arguments": json.dumps(b.get("input", {}))}}
                for b in rest if b.get("type") == "tool_use"
            ]
            if calls:
                msg["tool_calls"] = calls
            messages.append(msg)
    return {"model": body.get("model"), "messages": messages}


def responses_request(body: Mapping[str, Any]) -> Dict[str, Any]:
    messages: List[Dict[str, Any]] = []
    if body.get("instructions"):
        messages.append({"role": "system", "content": body["instructions"]})
    items = body.get("input")
    if isinstance(items, str):
        items = [{"role": "user", "content": items}]
    for item in items or []:
        kind = item.get("type", "message")
        if kind == "function_call":
            messages.append({"role": "assistant", "content": None, "tool_calls": [{
                "id": item.get("call_id"), "type": "function",
                "function": {"name": item.get("name"), "arguments": item.get("arguments")},
            }]})
        elif kind == "function_call_output":
            messages.append({"role": "tool", "tool_call_id": item.get("call_id"), "content": _blocks_text(item.get("output"))})
        elif kind == "message":
            messages.append({"role": item.get("role"), "content": _blocks_text(item.get("content"))})
    return {"model": body.get("model"), "messages": messages}


def embeddings_request(body: Mapping[str, Any]) -> Dict[str, Any]:
    texts = body.get("input")
    return {"model": body.get("model"), "input": texts if isinstance(texts, list) else [texts]}


def _blocks_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "") if isinstance(b, Mapping) else str(b)
            for b in content
            if not isinstance(b, Mapping) or b.get("type") in (None, "text", "input_text", "output_text")
        )
    return str(content)


# ---------------------------------------------------------
# OpenAI Chat Completions
# ---------------------------------------------------------
def to_chat_completion(output: Any, request_model: Optional[str], node_id: str) -> Dict[str, Any]:
    """Shape a recorded model output as an OpenAI chat-completion response."""
    if isinstance(output, Mapping) and isinstance(output.get("choices"), list):
        completion = copy.deepcopy(dict(output))
    else:
        if isinstance(output, Mapping):
            text = next((output[k] for k in ("content", "raw", "text") if output.get(k) is not None), None)
            text = text if text is not None else json.dumps(output)
        else:
            text = "" if output is None else str(output)
        completion = {"choices": [{"index": 0, "message": {"role": "assistant", "content": text}}]}

    completion.setdefault("id", f"chatcmpl-replay-{node_id}")
    completion["object"] = "chat.completion"
    completion["created"] = completion.get("created") or int(time.time())
    completion["model"] = completion.get("model") or request_model or "agent-replay"
    for i, choice in enumerate(completion["choices"]):
        choice.setdefault("index", i)
        message = choice.get("message") or {}
        message.setdefault("role", "assistant")
        message.setdefault("content", None)
        for tool_call in message.get("tool_calls") or []:
            tool_call.setdefault("type", "function")
        choice["message"] = message
        reason = choice.get("finish_reason") or ("tool_calls" if message.get("tool_calls") else "stop")
        choice["finish_reason"] = _TO_OPENAI_FINISH.get(reason, reason)
    if not completion.get("usage"):
        completion["usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return completion


def chat_stream(completion: Mapping[str, Any], include_usage: bool) -> Iterator[str]:
    """Re-emit a recorded completion as an OpenAI streaming (SSE) response."""
    base = {
        "id": completion["id"],
        "object": "chat.completion.chunk",
        "created": completion["created"],
        "model": completion["model"],
    }

    def chunk(choices, **extra) -> str:
        return f"data: {json.dumps({**base, 'choices': choices, **extra})}\n\n"

    for choice in completion["choices"]:
        index, message = choice["index"], choice["message"]
        yield chunk([{"index": index, "delta": {"role": message.get("role", "assistant")}, "finish_reason": None}])
        if message.get("content"):
            yield chunk([{"index": index, "delta": {"content": message["content"]}, "finish_reason": None}])
        for j, tool_call in enumerate(message.get("tool_calls") or []):
            delta = {"tool_calls": [{"index": j, "id": tool_call.get("id"), "type": "function",
                                     "function": tool_call.get("function", {})}]}
            yield chunk([{"index": index, "delta": delta, "finish_reason": None}])
        yield chunk([{"index": index, "delta": {}, "finish_reason": choice["finish_reason"]}])
    if include_usage:
        yield chunk([], usage=completion.get("usage"))
    yield "data: [DONE]\n\n"


def _first_message(completion: Mapping[str, Any]):
    choice = completion["choices"][0] if completion.get("choices") else {"message": {}, "finish_reason": "stop"}
    return choice.get("message") or {}, choice.get("finish_reason") or "stop"


def _arguments(tool_call: Mapping[str, Any]) -> str:
    args = tool_call.get("function", {}).get("arguments")
    return args if isinstance(args, str) else json.dumps(args or {})


# ---------------------------------------------------------
# Anthropic Messages
# ---------------------------------------------------------
def to_anthropic_message(completion: Mapping[str, Any], request_model: Optional[str]) -> Dict[str, Any]:
    message, finish = _first_message(completion)
    content: List[Dict[str, Any]] = []
    if message.get("content"):
        content.append({"type": "text", "text": message["content"]})
    for tc in message.get("tool_calls") or []:
        try:
            tool_input = json.loads(_arguments(tc))
        except json.JSONDecodeError:
            tool_input = {"raw": _arguments(tc)}
        content.append({"type": "tool_use", "id": tc.get("id"), "name": tc.get("function", {}).get("name"), "input": tool_input})
    usage = completion.get("usage") or {}
    return {
        "id": f"msg_replay_{str(completion.get('id', '')).replace('chatcmpl-replay-', '')}",
        "type": "message",
        "role": "assistant",
        "model": request_model or completion.get("model") or "agent-replay",
        "content": content,
        "stop_reason": _TO_ANTHROPIC_STOP.get(finish, finish),
        "stop_sequence": None,
        "usage": {"input_tokens": int(usage.get("prompt_tokens", 0)), "output_tokens": int(usage.get("completion_tokens", 0))},
    }


def anthropic_stream(message: Mapping[str, Any]) -> Iterator[str]:
    def event(kind: str, data: Mapping[str, Any]) -> str:
        return f"event: {kind}\ndata: {json.dumps({'type': kind, **data})}\n\n"

    start = {**message, "content": [], "stop_reason": None,
             "usage": {"input_tokens": message["usage"]["input_tokens"], "output_tokens": 0}}
    yield event("message_start", {"message": start})
    for index, block in enumerate(message["content"]):
        if block["type"] == "text":
            yield event("content_block_start", {"index": index, "content_block": {"type": "text", "text": ""}})
            yield event("content_block_delta", {"index": index, "delta": {"type": "text_delta", "text": block["text"]}})
        else:
            yield event("content_block_start", {"index": index, "content_block": {**block, "input": {}}})
            yield event("content_block_delta", {"index": index, "delta": {
                "type": "input_json_delta", "partial_json": json.dumps(block["input"])}})
        yield event("content_block_stop", {"index": index})
    yield event("message_delta", {"delta": {"stop_reason": message["stop_reason"], "stop_sequence": None},
                                  "usage": {"output_tokens": message["usage"]["output_tokens"]}})
    yield event("message_stop", {})


# ---------------------------------------------------------
# OpenAI Responses
# ---------------------------------------------------------
def to_response(completion: Mapping[str, Any], request_model: Optional[str], node_id: str) -> Dict[str, Any]:
    message, _ = _first_message(completion)
    output: List[Dict[str, Any]] = []
    if message.get("content"):
        output.append({
            "type": "message", "id": f"msg_replay_{node_id}", "status": "completed", "role": "assistant",
            "content": [{"type": "output_text", "text": message["content"], "annotations": []}],
        })
    for j, tc in enumerate(message.get("tool_calls") or []):
        output.append({
            "type": "function_call", "id": f"fc_replay_{node_id}_{j}", "call_id": tc.get("id"),
            "name": tc.get("function", {}).get("name"), "arguments": _arguments(tc), "status": "completed",
        })
    usage = completion.get("usage") or {}
    prompt, generated = int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))
    return {
        "id": f"resp_replay_{node_id}", "object": "response", "created_at": int(time.time()),
        "status": "completed", "model": request_model or completion.get("model") or "agent-replay",
        "output": output, "error": None, "incomplete_details": None, "instructions": None, "metadata": {},
        "parallel_tool_calls": True, "tool_choice": "auto", "tools": [], "temperature": None, "top_p": None,
        "text": {"format": {"type": "text"}},
        "usage": {"input_tokens": prompt, "output_tokens": generated, "total_tokens": prompt + generated,
                  "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}},
    }


def responses_stream(response: Mapping[str, Any]) -> Iterator[str]:
    sequence = iter(range(1_000_000))

    def event(kind: str, data: Mapping[str, Any]) -> str:
        return f"event: {kind}\ndata: {json.dumps({'type': kind, 'sequence_number': next(sequence), **data})}\n\n"

    yield event("response.created", {"response": {**response, "status": "in_progress", "output": []}})
    for index, item in enumerate(response["output"]):
        if item["type"] == "message":
            part = item["content"][0]
            yield event("response.output_item.added", {"output_index": index, "item": {**item, "status": "in_progress", "content": []}})
            yield event("response.content_part.added", {"item_id": item["id"], "output_index": index, "content_index": 0,
                                                        "part": {**part, "text": ""}})
            yield event("response.output_text.delta", {"item_id": item["id"], "output_index": index, "content_index": 0,
                                                       "delta": part["text"], "logprobs": []})
            yield event("response.output_text.done", {"item_id": item["id"], "output_index": index, "content_index": 0,
                                                      "text": part["text"], "logprobs": []})
            yield event("response.content_part.done", {"item_id": item["id"], "output_index": index, "content_index": 0, "part": part})
        else:
            yield event("response.output_item.added", {"output_index": index, "item": {**item, "status": "in_progress", "arguments": ""}})
            yield event("response.function_call_arguments.delta", {"item_id": item["id"], "output_index": index, "delta": item["arguments"]})
            yield event("response.function_call_arguments.done", {"item_id": item["id"], "output_index": index,
                                                                  "name": item["name"], "arguments": item["arguments"]})
        yield event("response.output_item.done", {"output_index": index, "item": item})
    yield event("response.completed", {"response": response})


# ---------------------------------------------------------
# OpenAI Embeddings
# ---------------------------------------------------------
def to_embeddings(output: Mapping[str, Any], request_model: Optional[str], encoding_format: Optional[str]) -> Dict[str, Any]:
    result = copy.deepcopy(dict(output))
    result["object"] = "list"
    result["model"] = result.get("model") or request_model or "agent-replay"
    if encoding_format == "base64":  # the OpenAI SDK asks for base64 float32 by default
        for item in result["data"]:
            item["embedding"] = base64.b64encode(struct.pack(f"<{len(item['embedding'])}f", *item["embedding"])).decode()
    return result


# ---------------------------------------------------------
# Errors
# ---------------------------------------------------------
def error_body(api: str, message: str, error_type: str) -> Dict[str, Any]:
    if api == MESSAGES:
        return {"type": "error", "error": {"type": error_type, "message": message}}
    return {"error": {"message": message, "type": error_type, "code": error_type}}
