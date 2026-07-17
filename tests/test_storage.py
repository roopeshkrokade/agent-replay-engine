from adapters.openinference.adapter import OpenInferenceAdapter
from compiler.ir_compiler import IRCompiler
from storage.db import SQLiteGraphStore

def test_persistence():
    """Ensure complex graphs can be saved to SQLite and hydrated back to Python objects."""
    print("1. Compiling trace into IR...")
    events = OpenInferenceAdapter().parse_file("sample_trace.json")
    original_graph = IRCompiler().compile(events)
    
    print("2. Saving graph to SQLite...")
    store = SQLiteGraphStore()
    # 🌟 FIX: Add the required Agent Identity arguments and capture the new versioned record_id
    record_id = store.save(original_graph, agent_id="test_storage_agent", agent_name="Test Storage Agent")
    
    print("3. Loading graph from SQLite...")
    # 🌟 FIX: Load using the versioned record_id
    loaded_graph = store.load(record_id)
    
    assert loaded_graph.id == original_graph.id
    assert len(loaded_graph.nodes) == len(original_graph.nodes)
    assert len(loaded_graph.edges) == len(original_graph.edges)