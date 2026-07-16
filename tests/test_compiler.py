import json
import dataclasses
from enum import Enum
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
    
from adapters.openinference.adapter import OpenInferenceAdapter  # noqa: E402
from compiler.ir_compiler import IRCompiler  # noqa: E402

# JSON Helper to handle Enums cleanly
class IREncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.name
        return super().default(obj)

def test_compiler_pipeline():
    print("1. Parsing external trace via Adapter...")
    adapter = OpenInferenceAdapter()
    events = adapter.parse_file("sample_trace.json")
    print(f"   -> Emitted {len(events)} CanonicalEvents.")

    print("\n2. Compiling events into ExecutionGraph (IR)...")
    compiler = IRCompiler()
    graph = compiler.compile(events)
    
    print("   -> Graph built successfully.")
    
    print("\n--- COMPILED EXECUTION GRAPH ---")
    graph_dict = dataclasses.asdict(graph)
    print(json.dumps(graph_dict, indent=2, cls=IREncoder))
    print("--------------------------------\n")
    
    print("✅ Success! The Trace -> Adapter -> Compiler -> IR pipeline is fully operational.")

if __name__ == "__main__":
    test_compiler_pipeline()