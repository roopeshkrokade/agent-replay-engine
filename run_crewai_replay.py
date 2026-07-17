import litellm
import argparse
from crewai import LLM
from storage import SQLiteGraphStore
from compiler import PlanCompiler, ReplaySession
from runtime import ReplayVM
from env_utils import get_hf_token
# Import your actual app workflow function
from tests.test_real_crewai import run_multi_agent_workflow

def run_replay(graph_id: str = None):
    store = SQLiteGraphStore()
    
    # 🌟 NEW: Interactive selection if no graph_id is provided
    if not graph_id:
        graphs = store.list_graphs()
        if not graphs:
            print("❌ No graphs found in the database. Run the live agent first to record a trace!")
            return
        
        print("\n📋 Available Recorded Executions:")
        for idx, g in enumerate(graphs):
            # Display a nice numbered list with timestamps
            print(f"  [{idx + 1}] {g['id']}  (Recorded: {g['created_at']})")
            
        while True:
            choice = input("\n👉 Enter the number of the execution to replay (or 'q' to quit): ").strip()
            if choice.lower() == 'q':
                print("Exiting.")
                return
            try:
                selected_idx = int(choice) - 1
                if 0 <= selected_idx < len(graphs):
                    graph_id = graphs[selected_idx]["id"]
                    break
                else:
                    print(f"❌ Invalid selection. Please choose a number between 1 and {len(graphs)}.")
            except ValueError:
                print("❌ Please enter a valid number.")

    print(f"\n🚀 Booting Replay VM for {graph_id}...")
    
    # 1. Load the recorded "truth"
    try:
        loaded_graph = store.load(graph_id)
    except ValueError as e:
        print(f"❌ Error: {e}")
        return
        
    plan = PlanCompiler().compile(loaded_graph, ReplaySession(mode="CACHE"))
    vm = ReplayVM(plan)

    # 2. Define the Hydrator (The "Glue" between our raw data and CrewAI's objects)
    def hydrated_interceptor(*args, **kwargs):
        messages = kwargs.get("messages", [])
        prompt_snippet = {"prompt_snippet": messages[-1]["content"][-500:] if messages else ""}
        
        result = vm.advance(prompt_snippet)
        
        if not result.success:
            raise RuntimeError(f"Replay Divergence: {result.resolution.reason}")
            
        print(f"  ✨ [Replay Engine] Instant replay for node '{result.resolution.node_id}'")
        
        from litellm import ModelResponse
        return ModelResponse(**result.output)

    # 3. Patch the framework (LiteLLM)
    litellm.completion = hydrated_interceptor

    # 4. Run the actual App (CrewAI will render the UI normally)
    hf_token = get_hf_token()
    hf_llm = LLM(model="huggingface/Qwen/Qwen2.5-Coder-7B-Instruct", api_key=hf_token)
    run_multi_agent_workflow(hf_llm)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay a CrewAI execution from the database.")
    # nargs="?" makes the argument completely optional in the terminal
    parser.add_argument("graph_id", nargs="?", help="The ID of the graph to replay (optional).")
    args = parser.parse_args()
    
    run_replay(args.graph_id)