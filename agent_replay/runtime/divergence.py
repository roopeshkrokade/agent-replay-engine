from typing import Any, Dict, List

from agent_replay.ir import ExecutionGraph, ExecutionNode, NodeKind


def diff_tools(recorded: ExecutionGraph, replayed: ExecutionGraph) -> List[Dict[str, Any]]:
    """
    Tools run live during replay. Compare the replay's tool spans with the recording, in
    execution order: a changed name, input or output means the agent's behaviour drifted.
    """
    expected, actual = _tool_nodes(recorded), _tool_nodes(replayed)
    divergences: List[Dict[str, Any]] = []
    for i in range(max(len(expected), len(actual))):
        step = i + 1
        if i >= len(actual):
            divergences.append(_divergence("tool_missing", step, expected[i], None, "Recorded tool call did not happen during replay."))
            continue
        if i >= len(expected):
            divergences.append(_divergence("tool_extra", step, None, actual[i], "Replay made a tool call that was not recorded."))
            continue
        exp, act = expected[i], actual[i]
        if tool_label(exp) != tool_label(act):
            divergences.append(_divergence("tool_changed", step, exp, act, "A different tool was called."))
        elif exp.input != act.input:
            divergences.append(_divergence("tool_input_changed", step, exp, act, "Tool was called with different arguments."))
        elif exp.output != act.output:
            divergences.append(_divergence("tool_output_changed", step, exp, act, "Tool returned a different result."))
    return divergences


def tool_label(node: ExecutionNode) -> str:
    attrs = node.metadata.attributes
    return attrs.get("tool.name") or attrs.get("gen_ai.tool.name") or node.metadata.span.get("name") or "tool"


def _tool_nodes(graph: ExecutionGraph) -> List[ExecutionNode]:
    nodes = [n for n in graph.nodes.values() if n.kind == NodeKind.TOOL]
    return sorted(nodes, key=lambda n: n.metadata.span.get("start_time_unix_nano", 0))


def _divergence(kind: str, step: int, expected: Any, actual: Any, reason: str) -> Dict[str, Any]:
    node = expected or actual
    return {
        "type": kind,
        "severity": "warning",
        "tool_step": step,
        "tool": tool_label(node),
        "reason": reason,
        "expected": None if expected is None else {"input": expected.input, "output": expected.output},
        "got": None if actual is None else {"input": actual.input, "output": actual.output},
    }
