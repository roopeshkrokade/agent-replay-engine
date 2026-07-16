import argparse
from adapters.openinference.adapter import OpenInferenceAdapter
from compiler import IRCompiler, PlanCompiler, ReplaySession
from storage import LocalGraphStore
from runtime import ReplayVM

def compile_trace(args):
    print(f"📥 Parsing trace: {args.file}...")
    events = OpenInferenceAdapter().parse_file(args.file)
    
    print("⚙️  Compiling Execution Graph (IR)...")
    graph = IRCompiler().compile(events)
    
    print("💾 Saving to local store...")
    store = LocalGraphStore()
    saved_path = store.save(graph)
    
    print(f"✅ Success! Compiled graph '{graph.id}' saved to {saved_path}")

def simulate_replay(args):
    print(f"📂 Loading graph '{args.graph_id}' from store...")
    store = LocalGraphStore()
    
    try:
        graph = store.load(args.graph_id)
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return

    print("⚙️  Compiling Replay Plan (CACHE mode)...")
    plan = PlanCompiler().compile(graph, ReplaySession(mode="CACHE"))
    
    print("🚀 Booting Replay VM...\n")
    vm = ReplayVM(plan)
    
    print("--- SIMULATING EXECUTION ---")
    # For simulation, we push the expected inputs through the VM to verify it works
    for i, instruction in enumerate(plan.instructions, 1):
        expected_input = instruction.expected_input
        print(f"\n[Step {i}] App sends input: {expected_input}")
        
        result = vm.advance(expected_input)
        
        if result.success:
            print(f"✅ VM Resolved Node: {result.resolution.node_id}")
            print(f"📦 VM Returned Output: {result.output}")
        else:
            print(f"❌ VM Failed: {result.resolution.reason}")
            break
            
    print("\n🎉 Simulation complete.")

def main():
    parser = argparse.ArgumentParser(description="Agent Replay Engine CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Command 1: compile
    compile_parser = subparsers.add_parser("compile", help="Compile a raw trace into an IR graph")
    compile_parser.add_argument("file", type=str, help="Path to the raw trace JSON file")

    # Command 2: simulate
    simulate_parser = subparsers.add_parser("simulate", help="Simulate a replay from a compiled graph")
    simulate_parser.add_argument("graph_id", type=str, help="The ID of the compiled graph to replay (e.g., g_compiled_001)")

    args = parser.parse_args()

    if args.command == "compile":
        compile_trace(args)
    elif args.command == "simulate":
        simulate_replay(args)

if __name__ == "__main__":
    main()