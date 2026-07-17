import litellm
import argparse
from crewai import LLM
from storage import SQLiteGraphStore
from compiler import PlanCompiler, ReplaySession
from runtime import ReplayVM
from env_utils import get_hf_token

# 🌟 IMPORT BOTH APPS
from run_live_crewai import run_multi_agent_workflow
from run_live_autogen import run_autogen_workflow

def run_replay(record_id: str = None):
    store = SQLiteGraphStore()
    
    if not record_id:
        unique_agents = store.get_unique_agents()
        if not unique_agents:
            print("❌ No executions found in the database.")
            return
        
        all_records = []
        for agent in unique_agents:
            all_records.extend(store.get_agent_history(agent["agent_id"]))
        
        all_records.sort(key=lambda x: x["last_execution_timestamp"], reverse=True)
        
        print("\n📋 Available Recorded Executions:")
        for idx, r in enumerate(all_records):
            print(f"  [{idx + 1}] {r['record_id']}  (Executed: {r['last_execution_timestamp']})")
            
        while True:
            choice = input("\n👉 Enter the number of the execution to replay (or 'q' to quit): ").strip()
            if choice.lower() == 'q':
                return
            try:
                selected_idx = int(choice) - 1
                if 0 <= selected_idx < len(all_records):
                    record_id = all_records[selected_idx]["record_id"]
                    break
                else:
                    print("❌ Invalid selection.")
            except ValueError:
                print("❌ Enter a valid number.")

    print(f"\n🚀 Booting Replay VM for {record_id}...")
    
    try:
        loaded_graph = store.load(record_id)
    except ValueError as e:
        print(f"❌ Error: {e}")
        return
        
    plan = PlanCompiler().compile(loaded_graph, ReplaySession(mode="CACHE"))
    vm = ReplayVM(plan)

    def hydrated_interceptor(*args, **kwargs):
        messages = kwargs.get("messages", [])
        prompt_snippet = {"prompt_snippet": messages[-1]["content"][-500:] if messages else ""}
        result = vm.advance(prompt_snippet)
        
        if not result.success:
            raise RuntimeError(f"Replay Divergence: {result.resolution.reason}")
            
        print(f"  ✨ [Replay Engine] Instant replay for node '{result.resolution.node_id}'")
        from litellm import ModelResponse
        return ModelResponse(**result.output)

    litellm.completion = hydrated_interceptor
    hf_token = get_hf_token()

    # 🌟 ROUTER: Boot the correct framework based on the agent ID!
    if "autogen" in record_id:
        run_autogen_workflow(hf_token)
    else:
        hf_llm = LLM(model="huggingface/Qwen/Qwen2.5-Coder-7B-Instruct", api_key=hf_token)
        run_multi_agent_workflow(hf_llm)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Universal Replay Engine.")
    parser.add_argument("record_id", nargs="?", help="The record ID to replay.")
    args = parser.parse_args()
    run_replay(args.record_id)