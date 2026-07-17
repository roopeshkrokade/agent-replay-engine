import litellm
import argparse
from crewai import LLM
from storage import SQLiteGraphStore
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

    print(f"\n🚀 Booting Replay VM for {record_id} in ALWAYS-RELAXED mode...")
    
    try:
        loaded_graph = store.load(record_id)
    except ValueError as e:
        print(f"❌ Error: {e}")
        return
        

    step_counter = {"current": 0}
    nodes_list = list(loaded_graph.nodes.values())

    def hydrated_interceptor(*args, **kwargs):
        from litellm import ModelResponse
        
        # 🌟 ALWAYS-RELAXED LOGIC: Ignore prompt differences, force sequence
        if step_counter["current"] < len(nodes_list):
            current_node = nodes_list[step_counter["current"]]
            step_counter["current"] += 1
            print(f"  ✨ [Relaxed Mode] Forcing cached response for step {step_counter['current']}")
            return ModelResponse(**current_node.output)
        else:
            raise RuntimeError("Replay Divergence: Agent requested more LLM calls than were recorded in this trace!")

    litellm.completion = hydrated_interceptor
    hf_token = get_hf_token()

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