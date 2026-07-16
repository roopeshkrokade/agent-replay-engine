from adapters.openinference.adapter import OpenInferenceAdapter
from compiler import IRCompiler
from storage import LocalGraphStore

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