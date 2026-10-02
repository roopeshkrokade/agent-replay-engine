from typing import Any, Dict, List, Mapping, Optional
import uuid
from agent_replay.ir import (
    CanonicalEvent, EventKind, ExecutionGraph, ExecutionNode, ExecutionEdge,
    GraphId, NodeId, EdgeId, GraphMetadata, NodeMetadata, EdgeMetadata,
    NodeKind, EdgeKind, IR_SCHEMA_VERSION
)

# Leaf calls the replay engine can serve from the recording, in execution order.
REPLAY_POINT_KINDS = (NodeKind.MODEL, NodeKind.EMBEDDING, NodeKind.TOOL)


class IRCompiler:
    """
    Transforms a flat stream of CanonicalEvents into an immutable ExecutionGraph (IR).
    This process is completely side-effect free.

    Edges:
      PARENT_CHILD - the OTel span tree (agent -> llm / tool)
      SEQUENTIAL   - replay points (MODEL / TOOL) in start-time order; this is what
                     the PlanCompiler linearises
    """

    def compile(
        self,
        events: List[CanonicalEvent],
        graph_id: str = None,
        attributes: Optional[Mapping[str, Any]] = None,
    ) -> ExecutionGraph:
        started: Dict[str, Mapping[str, Any]] = {}
        completed: List[Dict[str, Any]] = []
        workflow_start_time = "unknown"
        trace_ids: List[str] = []

        for event in events:
            if event.kind == EventKind.WORKFLOW_START:
                workflow_start_time = event.timestamp
                trace_ids = list(event.payload.get("trace_ids", []))
            elif event.kind == EventKind.SPAN_START:
                started[event.payload["span_id"]] = event.payload
            elif event.kind == EventKind.SPAN_END:
                start_payload = started.pop(event.payload["span_id"], None)
                if start_payload is not None:
                    completed.append({**start_payload, "output": event.payload.get("output")})

        completed.sort(key=lambda p: p["span"].get("start_time_unix_nano", 0))
        node_id_of = {p["span_id"]: NodeId(f"n_{p['span_id']}") for p in completed}
        kind_of = {p["span_id"]: p["node_kind"] for p in completed}
        children: Dict[str, List[str]] = {}
        for p in completed:
            parent = p["span"].get("parent_span_id")
            if parent in node_id_of:
                children.setdefault(parent, []).append(p["span_id"])

        nodes: Dict[NodeId, ExecutionNode] = {}
        edges: Dict[EdgeId, ExecutionEdge] = {}
        replay_chain: List[NodeId] = []

        model_spans = [p for p in completed if p["node_kind"] == NodeKind.MODEL]

        for p in completed:
            node_id = node_id_of[p["span_id"]]
            replayable, note = self._replayability(p, children, kind_of, model_spans)
            nodes[node_id] = ExecutionNode(
                id=node_id,
                kind=p["node_kind"],
                input=p.get("input", {}),
                output=p.get("output"),
                metadata=NodeMetadata(
                    attributes=p.get("metadata", {}),
                    span=p["span"],
                    replayable=replayable,
                    replay_note=note,
                ),
            )

            parent = p["span"].get("parent_span_id")
            if parent in node_id_of:
                self._add_edge(edges, node_id_of[parent], node_id, EdgeKind.PARENT_CHILD)

            if p["node_kind"] in REPLAY_POINT_KINDS and replayable:
                if replay_chain:
                    self._add_edge(edges, replay_chain[-1], node_id, EdgeKind.SEQUENTIAL)
                replay_chain.append(node_id)

        # 🌟 Automatically generate a unique ID if one isn't provided
        final_id = graph_id if graph_id else f"g_compiled_{uuid.uuid4().hex[:8]}"

        resources, scopes = [], []
        for p in completed:
            resource = p["span"].get("resource")
            if resource and resource not in resources:
                resources.append(resource)
            scope = p["span"].get("instrumentation_scope") or {}
            if scope.get("name") and scope not in scopes:
                scopes.append(scope)

        graph_meta = GraphMetadata(
            schema_version=IR_SCHEMA_VERSION,
            source_id=trace_ids[0] if len(trace_ids) == 1 else "compiled_trace",
            created_at=workflow_start_time,
            compiler_version="0.2.0",
            attributes={
                "trace_ids": trace_ids,
                "resources": resources,
                "instrumentation_scopes": scopes,
                **(attributes or {}),
            },
        )

        return ExecutionGraph(
            id=GraphId(final_id),
            metadata=graph_meta,
            nodes=nodes,
            edges=edges
        )

    @staticmethod
    def _add_edge(edges: Dict[EdgeId, ExecutionEdge], source: NodeId, target: NodeId, kind: EdgeKind):
        if kind == EdgeKind.SEQUENTIAL:
            edge_id = EdgeId(f"e_{source}_to_{target}")
        else:
            edge_id = EdgeId(f"e_{kind.name.lower()}_{source}_to_{target}")
        edges[edge_id] = ExecutionEdge(
            id=edge_id, source=source, target=target, kind=kind, metadata=EdgeMetadata()
        )

    @staticmethod
    def _replayability(
        p: Mapping[str, Any],
        children: Dict[str, List[str]],
        kind_of: Dict[str, NodeKind],
        model_spans: List[Mapping[str, Any]],
    ):
        span = p["span"]
        if span.get("dropped_attributes_count", 0) > 0:
            return False, "attributes were dropped during recording; raise span limits"
        output = p.get("output")
        if p["node_kind"] == NodeKind.EMBEDDING:
            if isinstance(output, Mapping) and ("data" in output or "recorded_error" in output):
                return True, ""
            return False, "embedding vectors were not captured"
        if p["node_kind"] != NodeKind.MODEL:
            return True, ""
        # A framework LLM span wrapping a provider LLM span: the innermost one is the real call.
        stack = list(children.get(p["span_id"], []))
        while stack:
            child = stack.pop()
            if kind_of.get(child) == NodeKind.MODEL:
                return False, "wraps an inner LLM span; the innermost span is the replay point"
            stack.extend(children.get(child, []))
        # Same, when the instrumentors did not share context and the inner span is not a child:
        # a model span whose time window contains another model span of the same trace.
        if any(_contains(span, other["span"]) for other in model_spans if other is not p):
            return False, "time-overlaps an inner LLM span from another instrumentor; the inner span is the replay point"
        if isinstance(output, Mapping) and "recorded_error" in output:
            return True, "replays the recorded error"
        if not output:
            return False, "no output captured; check that the instrumentor records content"
        return True, ""


def _contains(outer: Mapping[str, Any], inner: Mapping[str, Any]) -> bool:
    """
    True when `inner` runs entirely within `outer` and comes from a different instrumentor
    (framework span around a provider span). Parallel calls from one instrumentor overlap
    too, but are distinct calls. Ties are broken by span id, so only one side wins.
    """
    if outer.get("trace_id") != inner.get("trace_id"):
        return False
    if (outer.get("instrumentation_scope") or {}).get("name") == (inner.get("instrumentation_scope") or {}).get("name"):
        return False
    o_start, o_end = outer.get("start_time_unix_nano", 0), outer.get("end_time_unix_nano", 0)
    i_start, i_end = inner.get("start_time_unix_nano", 0), inner.get("end_time_unix_nano", 0)
    if not (o_start <= i_start and i_end <= o_end):
        return False
    if (o_start, o_end) == (i_start, i_end):
        return str(outer.get("span_id")) < str(inner.get("span_id"))
    return True
