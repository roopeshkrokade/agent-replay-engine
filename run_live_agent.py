import litellm
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
    
from storage import SQLiteGraphStore  # noqa: E402
from compiler import IRCompiler  # noqa: E402
from sdk import LiveRecorder  # noqa: E402
from env_utils import get_hf_token  # noqa: E402

# 1. SETUP THE REAL LLM
hf_token = get_hf_token()
if not hf_token:
    raise ValueError("🚨 Please set the HF_TOKEN environment variable or add it to .env before running.")

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
        verbose=True, 
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


# 4. LIVE RECORDING SCRIPT
def main():
    store = SQLiteGraphStore()
    
    # Define the Agent identity metadata for version tracking
    agent_id = "tokyo_weather_planner"
    agent_name = "Tokyo Activity Planner Crew"

    print("==================================================")
    print(f"🔴 RECORDING NEW LIVE EXECUTION: {agent_name}")
    print("==================================================")

    recorder = LiveRecorder()
    
    def extract_messages(*args, **kwargs):
        messages = kwargs.get("messages", [])
        last_msg = messages[-1]["content"] if messages else ""
        return {"prompt_snippet": last_msg[-500:]}

    # Attach the Security Camera
    recorder.patch(litellm, "completion", extract_messages, "MODEL")
    
    # Run the multi-agent workflow
    run_multi_agent_workflow(hf_llm)
    
    # Compile the execution trace graph
    events = recorder.finish()
    graph = IRCompiler().compile(events)
    
    # Pass the tracking metadata to the updated store method
    record_id = store.save(graph, agent_id=agent_id, agent_name=agent_name)
    print(f"\n💾 [System] Agent execution preserved in history as: {record_id}")

if __name__ == "__main__":
    main()