import json
from typing import Any, Dict, List, Mapping
from agent_replay.compiler import Instruction
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


class StrictMatcher:
    """
    Model requests must carry the same conversation as the recording. Messages are compared
    in canonical form, so the live wire format and the instrumented span format line up.
    """

    def resolve(self, app_input: Mapping[str, Any], instruction: Instruction) -> NodeResolution:
        if canonical_request(app_input) == canonical_request(instruction.expected_input):
            return NodeResolution(
                node_id=instruction.node_id,
                confidence=1.0,
                matcher_used="StrictMatcher",
                reason="Request messages matched the recording.",
            )
        return NodeResolution(
            node_id=instruction.node_id,
            confidence=0.0,
            matcher_used="StrictMatcher",
            reason="Request messages differ from the recording.",
            diverged=True,
        )


class RelaxedMatcher:
    """Serves the recording by position; a differing request is reported but not fatal."""

    def resolve(self, app_input: Mapping[str, Any], instruction: Instruction) -> NodeResolution:
        diverged = canonical_request(app_input) != canonical_request(instruction.expected_input)
        return NodeResolution(
            node_id=instruction.node_id,
            confidence=1.0,
            matcher_used="RelaxedMatcher",
            reason="Served by sequence position" + (" (request differs from recording)" if diverged else "."),
            diverged=diverged,
        )


def canonical_request(payload: Any) -> Any:
    """Comparable form of a recorded or live request: the conversation, or the embedded texts."""
    if isinstance(payload, Mapping) and isinstance(payload.get("messages"), list):
        return [canonical_message(m) for m in payload["messages"]]
    if isinstance(payload, Mapping) and "input" in payload and "messages" not in payload:
        texts = payload["input"]
        return {"input": [str(t) for t in (texts if isinstance(texts, list) else [texts])]}
    return payload


def canonical_message(message: Mapping[str, Any]) -> Dict[str, Any]:
    content = message.get("content")
    if isinstance(content, list):  # multi-part content -> concatenated text
        content = "".join(p.get("text", "") for p in content if isinstance(p, Mapping))
    out: Dict[str, Any] = {"role": message.get("role"), "content": (content or "").strip()}
    tool_calls: List[Dict[str, Any]] = []
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function", {})
        tool_calls.append({"id": tc.get("id"), "name": fn.get("name"), "arguments": _canonical_json(fn.get("arguments"))})
    if tool_calls:
        out["tool_calls"] = tool_calls
    if message.get("tool_call_id"):
        # A tool result, whatever role label the source used (Anthropic sends them as "user").
        out["role"] = "tool"
        out["tool_call_id"] = message["tool_call_id"]
    return out


def _canonical_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value
