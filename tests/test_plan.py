from agent_replay.adapters.openinference.adapter import OpenInferenceAdapter
from agent_replay.compiler import IRCompiler, PlanCompiler, ReplaySession
from tests import SAMPLE_TRACE

def test_plan_compilation():
    print("1. [Adapter] Parsing external trace...")
    adapter = OpenInferenceAdapter()
    events = adapter.parse_file(SAMPLE_TRACE)

    print("2. [IR Compiler] Building ExecutionGraph...")
    ir_compiler = IRCompiler()
    graph = ir_compiler.compile(events)
    
    print("3. [Plan Compiler] Generating ReplayPlan (Bytecode)...")
    session = ReplaySession(mode="CACHE")
    plan_compiler = PlanCompiler()
    plan = plan_compiler.compile(graph, session)
    
    print(f"\n--- REPLAY PLAN FOR GRAPH: {plan.graph_id} ---")
    for i, instruction in enumerate(plan.instructions, 1):
        print(f"Step {i}: {instruction.kind.name} (Node: {instruction.node_id})")
        print(f"  -> Expects: {instruction.expected_input}")
        print(f"  -> Returns: {instruction.output_to_return}")
    print("-------------------------------------------------\n")
    
    print("✅ Success! The bytecode is ready for the VM.")

if __name__ == "__main__":
    test_plan_compilation()