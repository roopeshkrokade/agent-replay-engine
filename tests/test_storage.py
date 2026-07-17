import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
    
from storage import SQLiteGraphStore  # noqa: E402
from compiler import IRCompiler  # noqa: E402
from adapters.openinference import OpenInferenceAdapter  # noqa: E402

def test_persistence():
    """Ensure complex graphs can be saved to SQLite and hydrated back to Python objects."""
    print("1. Compiling trace into IR...")
    events = OpenInferenceAdapter().parse_file("sample_trace.json")
    original_graph = IRCompiler().compile(events)
    
    print("2. Saving graph to SQLite...")
    store = SQLiteGraphStore()
    store.save(original_graph)
    
    print("3. Loading graph from SQLite...")
    loaded_graph = store.load(original_graph.id)
    
    # Verify data integrity
    assert original_graph.id == loaded_graph.id
    assert len(original_graph.nodes) == len(loaded_graph.nodes)
    
    # Verify deep hydration (Enums should be restored)
    assert original_graph.nodes["n_span_1"].kind == loaded_graph.nodes["n_span_1"].kind

def test_store_uses_repo_relative_default_path(monkeypatch, tmp_path):
    """Ensure the SQLite DB creates the required nested directories."""
    monkeypatch.chdir(tmp_path)
    
    store = SQLiteGraphStore()
    
    assert os.path.exists(".agent-replay/traces.db")
    assert store.engine is not None  # Silences the linter by using the variable