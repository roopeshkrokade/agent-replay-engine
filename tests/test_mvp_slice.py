import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
    
from adapters.openinference.adapter import OpenInferenceAdapter  # noqa: E402
from compiler import IRCompiler, PlanCompiler, ReplaySession  # noqa: E402
from runtime import ReplayVM  # noqa: E402

def test_full_vertical_slice():
    print("==========================================")
    print("🚀 BOOTING AGENT REPLAY ENGINE MVP")
    print("==========================================\n")

    # 1. INGESTION
    print("[1] Ingesting OpenInference Trace...")
    events = OpenInferenceAdapter().parse_file("sample_trace.json")
    
    # 2. IR COMPILATION
    print("[2] Compiling Execution Graph (IR)...")
    graph = IRCompiler().compile(events)
    
    # 3. PLAN COMPILATION
    print("[3] Compiling Replay Plan (Bytecode)...")
    plan = PlanCompiler().compile(graph, ReplaySession(mode="CACHE"))
    
    # 4. RUNTIME EXECUTION
    print("[4] Booting Replay VM...")
    vm = ReplayVM(plan)
    
    print("\n--- SIMULATING APPLICATION EXECUTION ---")
    
    # Simulate Call 1: The app asks the LLM for the weather
    call_1_input = {"role": "user", "content": "What is the weather in Tokyo?"}
    print(f"\nApp SDK intercepts LLM call with input: {call_1_input}")
    result_1 = vm.advance(call_1_input)
    
    if result_1.success:
        print(f"✅ VM Resolved Node: {result_1.resolution.node_id} (Matcher: {result_1.resolution.matcher_used})")
        print(f"📦 VM Returned Output: {result_1.output}")
    else:
        print(f"❌ VM Failed: {result_1.resolution.reason}")

    # Simulate Call 2: The app executes the tool call returned by the LLM
    call_2_input = {"loc": "Tokyo"}
    print(f"\nApp SDK intercepts Tool call with input: {call_2_input}")
    result_2 = vm.advance(call_2_input)
    
    if result_2.success:
        print(f"✅ VM Resolved Node: {result_2.resolution.node_id} (Matcher: {result_2.resolution.matcher_used})")
        print(f"📦 VM Returned Output: {result_2.output}")
    else:
        print(f"❌ VM Failed: {result_2.resolution.reason}")

    print("\n==========================================")
    print("🎉 VERTICAL SLICE COMPLETE")
    print("==========================================")

if __name__ == "__main__":
    test_full_vertical_slice()