import os
import litellm
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
from storage import LocalGraphStore
from compiler import IRCompiler, PlanCompiler, ReplaySession
from runtime import ReplayVM
from sdk import LiveRecorder

# 1. SETUP THE REAL LLM
hf_token = os.environ.get("HF_TOKEN")
if not hf_token:
    raise ValueError("🚨 Please set the HF_TOKEN environment variable before running.")

hf_llm = LLM(
    model="huggingface/Qwen/Qwen2.5-Coder-7B-Instruct",
    api_key=hf_token
)

# 2. DEFINE A CUSTOM TOOL
@tool("Get Weather")
def get_weather(location: str) -> str:
    """Useful to get the current weather for a given location. Always use this to check weather."""
    print(f"    🛠️  [Tool Execution] Live fetching weather for {location}...")
    return f"The weather in {location} is 75F and sunny."

# 3. THE MULTI-AGENT APP
def run_multi_agent_workflow(llm):
    print("  App: Booting Multi-Agent CrewAI...")
    
    # Agent 1: The Researcher (Has access to the tool)
    researcher = Agent(
        role='Weather Researcher',
        goal='Find the current weather for a given city using your tools.',
        backstory='You are a meticulous meteorologist. You MUST use the Get Weather tool to answer.',
        tools=[get_weather],
        verbose=True, # Turned on so you can see the ReAct loop in the terminal
        allow_delegation=False,
        llm=llm
    )
    
    # Agent 2: The Planner (Takes Researcher's output and does something with it)
    planner = Agent(
        role='Activity Planner',
        goal='Plan a single outdoor activity based on the provided weather.',
        backstory='You are an enthusiastic travel guide.',
        verbose=True,
        allow_delegation=False,
        llm=llm
    )
    
    # Task 1: Research
    research_task = Task(
        description='Get the weather for Tokyo.',
        expected_output='The current temperature and condition.',
        agent=researcher
    )
    
    # Task 2: Plan (CrewAI automatically passes Task 1's output into Task 2)
    plan_task = Task(
        description='Based on the weather from the researcher, suggest one brief outdoor activity in Tokyo.',
        expected_output='A one-sentence activity suggestion.',
        agent=planner
    )
    
    crew = Crew(
        agents=[researcher, planner], 
        tasks=[research_task, plan_task], 
        verbose=True
    )
    
    result = crew.kickoff()
    print(f"\n  App: CrewAI Final Output -> {result.raw}")


# 4. THE REPLAY ENGINE DEMO
def test_crewai_autolog():
    # ---------------------------------------------------------
    # PHASE 1: RECORD LIVE EXECUTION (REAL NETWORK CALLS)
    # ---------------------------------------------------------
    print("==================================================")
    print("🔴 PHASE 1: RECORDING MULTI-AGENT EXECUTION")
    print("==================================================")
    
    recorder = LiveRecorder()
    
    def extract_messages(*args, **kwargs):
        messages = kwargs.get("messages", [])
        # We grab the last 500 characters of the prompt to identify the step.
        # This avoids ExactMatcher failures if CrewAI injects dynamic timestamps into the prompt headers.
        last_msg = messages[-1]["content"] if messages else ""
        return {"prompt_snippet": last_msg[-500:]}

    # Attach the Security Camera
    recorder.patch(litellm, "completion", extract_messages, "MODEL")
    
    # Run the multi-agent workflow
    run_multi_agent_workflow(hf_llm)
    
    # Compile and Save
    events = recorder.finish()
    graph = IRCompiler().compile(events)
    store = LocalGraphStore()
    store.save(graph)
    print(f"\n💾 [System] Multi-Agent execution compiled to {graph.id}.json")

    # ---------------------------------------------------------
    # PHASE 2: DETERMINISTIC REPLAY (NO NETWORK)
    # ---------------------------------------------------------
    print("\n==================================================")
    print("🟢 PHASE 2: REPLAYING CREWAI (ZERO NETWORK CALLS)")
    print("==================================================")
    
    loaded_graph = store.load(graph.id)
    plan = PlanCompiler().compile(loaded_graph, ReplaySession(mode="CACHE"))
    vm = ReplayVM(plan)
    
    def hydrated_interceptor(*args, **kwargs):
        vm_input = extract_messages(*args, **kwargs)
        result = vm.advance(vm_input)
        
        if not result.success:
            raise RuntimeError(f"Replay Divergence: {result.resolution.reason}")
            
        print(f"  ✨ [Interceptor] Returning cached HuggingFace response for node '{result.resolution.node_id}'")
        
        from litellm import ModelResponse
        return ModelResponse(**result.output)

    # Monkey-patch litellm directly with our custom hydrator
    litellm.completion = hydrated_interceptor

    # Run the EXACT same CrewAI setup again. 
    run_multi_agent_workflow(hf_llm)

if __name__ == "__main__":
    test_crewai_autolog()