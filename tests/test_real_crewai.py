import litellm
import time
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
    
from storage import SQLiteGraphStore  # noqa: E402
from compiler import IRCompiler, PlanCompiler, ReplaySession  # noqa: E402
from runtime import ReplayVM  # noqa: E402
from sdk import LiveRecorder  # noqa: E402
from env_utils import get_hf_token  # noqa: E402

# 1. SETUP THE REAL LLM
hf_token = get_hf_token()
if not hf_token:
    raise ValueError("🚨 Please set the HF_TOKEN environment variable or add it to .env.")

hf_llm = LLM(
    model="huggingface/Qwen/Qwen2.5-Coder-7B-Instruct",
    api_key=hf_token
)

# 2. DEFINE A CUSTOM TOOL
@tool("Get Weather")
def get_weather(location: str) -> str:
    """Useful to get the current weather for a given location."""
    print(f"    🛠️  [Tool Execution] Live fetching weather for {location}...")
    return f"The weather in {location} is 75F and sunny."

# 3. THE MULTI-AGENT APP
def run_multi_agent_workflow(llm):
    print("  App: Booting Multi-Agent CrewAI...")
    researcher = Agent(
        role='Weather Researcher',
        goal='Find the current weather for a given city using your tools.',
        backstory='You are a meticulous meteorologist.',
        tools=[get_weather],
        verbose=True,
        allow_delegation=False,
        llm=llm
    )
    planner = Agent(
        role='Activity Planner',
        goal='Plan a single outdoor activity based on the provided weather.',
        backstory='You are an enthusiastic travel guide.',
        verbose=True,
        allow_delegation=False,
        llm=llm
    )
    research_task = Task(description='Get the weather for Tokyo.', expected_output='The current temperature and condition.', agent=researcher)
    plan_task = Task(description='Based on the weather from the researcher, suggest one brief outdoor activity in Tokyo.', expected_output='A one-sentence activity suggestion.', agent=planner)
    
    crew = Crew(agents=[researcher, planner], tasks=[research_task, plan_task], verbose=True)
    result = crew.kickoff()
    print(f"\n  App: CrewAI Final Output -> {result.raw}")

# 4. THE REPLAY ENGINE DEMO
def test_crewai_autolog():
    # ---------------------------------------------------------
    # PHASE 1: RECORD LIVE EXECUTION
    # ---------------------------------------------------------
    print("==================================================")
    print("🔴 PHASE 1: RECORDING MULTI-AGENT EXECUTION")
    print("==================================================")
    
    recorder = LiveRecorder()
    
    def extract_messages(*args, **kwargs):
        messages = kwargs.get("messages", [])
        # Normalizing to avoid divergence
        content = messages[-1]["content"] if messages else ""
        return {"prompt_snippet": content[-500:]}

    recorder.patch(litellm, "completion", extract_messages, "MODEL")
    
    run_multi_agent_workflow(hf_llm)
    
    # Compile and Save with unique ID
    events = recorder.finish()
    unique_id = f"crewai_run_{int(time.time())}"
    graph = IRCompiler().compile(events, graph_id=unique_id)
    store = SQLiteGraphStore()
    store.save(graph)
    print(f"\n💾 [System] Multi-Agent execution saved as: {graph.id}")

    # ---------------------------------------------------------
    # PHASE 2: DETERMINISTIC REPLAY
    # ---------------------------------------------------------
    print("\n==================================================")
    print(f"🟢 PHASE 2: REPLAYING {graph.id} (ZERO NETWORK)")
    print("==================================================")
    
    loaded_graph = store.load(graph.id)
    plan = PlanCompiler().compile(loaded_graph, ReplaySession(mode="CACHE"))
    vm = ReplayVM(plan)
    
    def hydrated_interceptor(*args, **kwargs):
        vm_input = extract_messages(*args, **kwargs)
        result = vm.advance(vm_input)
        
        if not result.success:
            # We explicitly print what the VM received to help debug mismatches
            print(f"DEBUG: VM received: {vm_input}")
            raise RuntimeError(f"Replay Divergence: {result.resolution.reason}")
            
        print(f"  ✨ [Replay Engine] Instant replay node match: '{result.resolution.node_id}'")
        
        from litellm import ModelResponse
        return ModelResponse(**result.output)

    litellm.completion = hydrated_interceptor
    run_multi_agent_workflow(hf_llm)

if __name__ == "__main__":
    test_crewai_autolog()