from typing import List, Dict
import uuid
from ir import (
    CanonicalEvent, EventKind, ExecutionGraph, ExecutionNode, ExecutionEdge,
    GraphId, NodeId, EdgeId, GraphMetadata, NodeMetadata, EdgeMetadata,
    NodeKind, EdgeKind, IR_SCHEMA_VERSION
)

class IRCompiler:
    """
    Transforms a flat stream of CanonicalEvents into an immutable ExecutionGraph (IR).
    This process is completely side-effect free.
    """
    
    # 🌟 NEW: Accept an optional graph_id parameter
    def compile(self, events: List[CanonicalEvent], graph_id: str = None) -> ExecutionGraph:
        nodes: Dict[NodeId, ExecutionNode] = {}
        edges: Dict[EdgeId, ExecutionEdge] = {}
        
        active_spans = {}
        completed_node_ids = []
        workflow_start_time = "unknown"
        
        for event in events:
            if event.kind == EventKind.WORKFLOW_START:
                workflow_start_time = event.timestamp
                continue
            elif event.kind == EventKind.WORKFLOW_END:
                continue
                
            base_id = event.id.replace("evt_", "").replace("_start", "").replace("_end", "")
            
            if event.kind in (EventKind.MODEL_START, EventKind.TOOL_START):
                active_spans[base_id] = event.payload
            
            elif event.kind in (EventKind.MODEL_END, EventKind.TOOL_END):
                start_payload = active_spans.pop(base_id, {})
                
                node_id = NodeId(f"n_{base_id}")
                node_kind = NodeKind.MODEL if event.kind == EventKind.MODEL_END else NodeKind.TOOL
                
                node = ExecutionNode(
                    id=node_id,
                    kind=node_kind,
                    input=start_payload.get("input", {}),
                    output=event.payload.get("output"),
                    metadata=NodeMetadata(attributes=start_payload.get("metadata", {}))
                )
                nodes[node_id] = node
                
                if completed_node_ids:
                    prev_node_id = completed_node_ids[-1]
                    edge_id = EdgeId(f"e_{prev_node_id}_to_{node_id}")
                    edge = ExecutionEdge(
                        id=edge_id,
                        source=prev_node_id,
                        target=node_id,
                        kind=EdgeKind.SEQUENTIAL,
                        metadata=EdgeMetadata()
                    )
                    edges[edge_id] = edge
                    
                completed_node_ids.append(node_id)

        # 🌟 Automatically generate a unique ID if one isn't provided
        final_id = graph_id if graph_id else f"g_compiled_{uuid.uuid4().hex[:8]}"

        graph_meta = GraphMetadata(
            schema_version=IR_SCHEMA_VERSION,
            source_id="compiled_trace",
            created_at=workflow_start_time,
            compiler_version="0.1.0"
        )
        
        return ExecutionGraph(
            id=GraphId(final_id),
            metadata=graph_meta,
            nodes=nodes,
            edges=edges
        )