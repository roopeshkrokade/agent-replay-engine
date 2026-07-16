import json
from pathlib import Path
from ir import (
    ExecutionGraph, GraphMetadata, ExecutionNode, ExecutionEdge,
    GraphId, NodeId, EdgeId, NodeKind, EdgeKind, NodeMetadata, EdgeMetadata
)
from .encoder import IRJSONEncoder

class LocalGraphStore:
    """
    Saves and loads ExecutionGraphs to local disk.
    Acts as the persistent repository for compiled IR.
    """
    def __init__(self, base_dir: str | Path | None = None):
        if base_dir is None:
            base_dir = Path(__file__).resolve().parents[1] / ".replay_engine" / "graphs"
        else:
            base_dir = Path(base_dir)
            if not base_dir.is_absolute():
                base_dir = Path(__file__).resolve().parents[1] / base_dir

        self.base_dir = base_dir.resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, graph: ExecutionGraph) -> Path:
        """Serializes the ExecutionGraph to a JSON file."""
        file_path = self.base_dir / f"{graph.id}.json"
        with open(file_path, "w") as f:
            json.dump(graph, f, cls=IRJSONEncoder, indent=2)
        return file_path

    def load(self, graph_id: str) -> ExecutionGraph:
        """Deserializes a JSON file back into a pure ExecutionGraph."""
        file_path = self.base_dir / f"{graph_id}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Graph {graph_id} not found at {file_path}")

        with open(file_path, "r") as f:
            data = json.load(f)

        # 1. Rehydrate Metadata
        meta = GraphMetadata(**data["metadata"])

        # 2. Rehydrate Nodes
        nodes = {}
        for n_id, n_data in data["nodes"].items():
            n_data["id"] = NodeId(n_data["id"])
            n_data["kind"] = NodeKind[n_data["kind"]]
            n_data["metadata"] = NodeMetadata(**n_data["metadata"])
            nodes[NodeId(n_id)] = ExecutionNode(**n_data)

        # 3. Rehydrate Edges
        edges = {}
        for e_id, e_data in data["edges"].items():
            e_data["id"] = EdgeId(e_data["id"])
            e_data["source"] = NodeId(e_data["source"])
            e_data["target"] = NodeId(e_data["target"])
            e_data["kind"] = EdgeKind[e_data["kind"]]
            e_data["metadata"] = EdgeMetadata(**e_data["metadata"])
            edges[EdgeId(e_id)] = ExecutionEdge(**e_data)

        # 4. Return Immutable Graph
        return ExecutionGraph(
            id=GraphId(data["id"]),
            metadata=meta,
            nodes=nodes,
            edges=edges
        )