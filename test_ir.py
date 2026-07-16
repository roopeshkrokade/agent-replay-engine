import json
import dataclasses
from enum import Enum
from ir import (
    IR_SCHEMA_VERSION, GraphId, NodeId, EdgeId,
    NodeKind, EdgeKind, GraphMetadata, NodeMetadata, EdgeMetadata,
    ExecutionNode, ExecutionEdge, ExecutionGraph
)

# Helper to serialize Enums to their string names (e.g., NodeKind.MODEL -> "MODEL")
class IREncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.name
        return super().default(obj)

def test_graph_serialization():
    print("1. Instantiating IR components...")
    
    # 1. Metadata
    graph_meta = GraphMetadata(
        schema_version=IR_SCHEMA_VERSION,
        source_id="trace_001",
        created_at="2026-07-16T12:00:00Z",
        compiler_version="0.1.0"
    )

    # 2. Nodes
    node_1 = ExecutionNode(
        id=NodeId("n_1"),
        kind=NodeKind.MODEL,
        input={"role": "user", "content": "What is the weather in Tokyo?"},
        output={"type": "tool_call", "name": "get_weather"},
        metadata=NodeMetadata(attributes={"provider": "openai", "model": "gpt-4o"})
    )

    node_2 = ExecutionNode(
        id=NodeId("n_2"),
        kind=NodeKind.TOOL,
        input={"loc": "Tokyo"},
        output={"result": "72F"},
        metadata=NodeMetadata(attributes={"tool_name": "get_weather"})
    )

    # 3. Edges
    edge_1 = ExecutionEdge(
        id=EdgeId("e_1"),
        source=NodeId("n_1"),
        target=NodeId("n_2"),
        kind=EdgeKind.SEQUENTIAL,
        metadata=EdgeMetadata()
    )

    # 4. Assemble Graph
    graph = ExecutionGraph(
        id=GraphId("g_001"),
        metadata=graph_meta,
        nodes={n.id: n for n in [node_1, node_2]},
        edges={e.id: e for e in [edge_1]}
    )

    print("2. Graph built successfully in memory. Serializing to JSON...")
    
    # Convert dataclass to dict, then to JSON string
    graph_dict = dataclasses.asdict(graph)
    json_output = json.dumps(graph_dict, indent=2, cls=IREncoder)
    
    print("\n--- SERIALIZED EXECUTION GRAPH ---")
    print(json_output)
    print("----------------------------------\n")
    print("✅ Success! The IR contract is solid.")

if __name__ == "__main__":
    test_graph_serialization()