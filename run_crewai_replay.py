import litellm
import argparse
from crewai import LLM
from storage import LocalGraphStore
from compiler import PlanCompiler, ReplaySession
from runtime import ReplayVM
from env_utils import get_hf_token
# Import your actual app workflow function
from test_real_crewai import run_multi_agent_workflow

def run_replay(graph_id: str):
    print(f"🚀 Booting Replay VM for {graph_id}...")
    
    # 1. Load the recorded "truth"
    store = LocalGraphStore()
    loaded_graph = store.load(graph_id)
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
    parser = argparse.ArgumentParser()
    parser.add_argument("graph_id", help="The ID of the graph to replay")
    args = parser.parse_args()
    
    run_replay(args.graph_id)