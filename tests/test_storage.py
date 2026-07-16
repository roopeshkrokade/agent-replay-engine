import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
    
from adapters.openinference.adapter import OpenInferenceAdapter  # noqa: E402
from compiler import IRCompiler  # noqa: E402
from storage import LocalGraphStore  # noqa: E402


def test_store_uses_repo_relative_default_path(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    store = LocalGraphStore()
    graph = store.load("g_compiled_001")

    assert graph.id == "g_compiled_001"


def test_persistence():
    print("1. Compiling trace into IR...")
    events = OpenInferenceAdapter().parse_file("sample_trace.json")
    original_graph = IRCompiler().compile(events)

    print("2. Saving graph to disk...")
    store = LocalGraphStore()
    saved_path = store.save(original_graph)
    print(f"   -> Graph saved to: {saved_path}")

    print("3. Loading graph from disk...")
    loaded_graph = store.load(original_graph.id)
    print(f"   -> Graph loaded successfully: {loaded_graph.id}")

    # Verify data integrity
    assert original_graph.id == loaded_graph.id
    assert len(original_graph.nodes) == len(loaded_graph.nodes)
    assert original_graph.nodes["n_span_1"].kind == loaded_graph.nodes["n_span_1"].kind
    
    print("✅ Success! The Execution Graph is fully persistent.")

if __name__ == "__main__":
    test_persistence()