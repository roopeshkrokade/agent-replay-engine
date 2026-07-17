import time
import litellm
from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool
from storage import SQLiteGraphStore
from compiler import IRCompiler
from sdk import LiveRecorder
from env_utils import get_hf_token

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
    
    # Agent 2: The Planner
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
    
    # Task 2: Plan
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
    
    # Generate a UNIQUE ID for this specific execution
    timestamp = int(time.time())
    graph_id = f"WeatherAgent_v{timestamp}"

    print("==================================================")
    print(f"🔴 RECORDING NEW LIVE EXECUTION: {graph_id}")
    print("==================================================")

    recorder = LiveRecorder()
    
    def extract_messages(*args, **kwargs):
        messages = kwargs.get("messages", [])
        # We grab the last 500 characters of the prompt to identify the step.
        last_msg = messages[-1]["content"] if messages else ""
        return {"prompt_snippet": last_msg[-500:]}

    # Attach the Security Camera
    recorder.patch(litellm, "completion", extract_messages, "MODEL")
    
    # Execute the Real Agent Workflow
    run_multi_agent_workflow(hf_llm)
    
    # Compile the events into a Graph with the unique ID
    # No dataclasses.replace hack needed anymore!
    events = recorder.finish()
    graph = IRCompiler().compile(events, graph_id=graph_id)
    
    store.save(graph)
    print(f"\n💾 [System] Agent execution preserved in history as: {graph.id}")

if __name__ == "__main__":
    main()