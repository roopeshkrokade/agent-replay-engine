"""
Multi-agent CrewAI workflow, recorded through OpenTelemetry.

Nothing here is specific to agent-replay except autolog() and start_run(): the CrewAI and
OpenAI OpenInference instrumentors are discovered automatically.

    uv sync --extra crewai
    agent-replay serve                    # tracking server on :5000
    python examples/crewai_weather.py     # record
Replay from the UI, or: agent-replay replay <record_id>
"""

import os

import agent_replay
from env_utils import get_hf_token

os.environ.setdefault(
    "CREWAI_DISABLE_TELEMETRY", "true"
)  # keep replays free of third-party calls
agent_replay.autolog()

from crewai import LLM, Agent, Crew, Task  # noqa: E402 - instrumentation is enabled first
from crewai.tools import tool  # noqa: E402 - instrumentation is enabled first

# OpenAI-compatible endpoint. Reading the base URL from the environment is the one integration
# requirement: during replay agent-replay points OPENAI_BASE_URL at its replay server.
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://router.huggingface.co/v1")
MODEL = os.environ.get(
    "EXAMPLE_MODEL", "Qwen/Qwen3-8B:nscale"
)  # must support tool calling


def build_llm() -> LLM:
    # provider="openai" selects CrewAI's native OpenAI-compatible client for any model name.
    return LLM(
        model=MODEL,
        provider="openai",
        base_url=BASE_URL,
        api_key=get_hf_token() or os.environ.get("OPENAI_API_KEY"),
    )


@tool("Get Weather")
def get_weather(location: str) -> str:
    """Useful to get the current weather for a given location. Always use this to check weather."""
    print(f"    🛠️  [Tool Execution] Live fetching weather for {location}...")
    return f"The weather in {location} is 75F and sunny."


def run_multi_agent_workflow(llm: LLM) -> str:
    print("  App: Booting Multi-Agent CrewAI...")
    researcher = Agent(
        role="Weather Researcher",
        goal="Find the current weather for a given city using your tools.",
        backstory="You are a meticulous meteorologist. You MUST use the Get Weather tool to answer.",
        tools=[get_weather],
        verbose=True,
        allow_delegation=False,
        llm=llm,
    )
    planner = Agent(
        role="Activity Planner",
        goal="Plan a single outdoor activity based on the provided weather.",
        backstory="You are an enthusiastic travel guide.",
        verbose=True,
        allow_delegation=False,
        llm=llm,
    )
    research_task = Task(
        description="Get the weather for Tokyo.",
        expected_output="The current temperature and condition.",
        agent=researcher,
    )
    plan_task = Task(
        description="Based on the weather from the researcher, suggest one brief outdoor activity in Tokyo.",
        expected_output="A one-sentence activity suggestion.",
        agent=planner,
    )
    crew = Crew(
        agents=[researcher, planner], tasks=[research_task, plan_task], verbose=True
    )
    result = crew.kickoff()
    print(f"\n  App: CrewAI Final Output -> {result.raw}")
    return result.raw


def main():
    with agent_replay.start_run(
        agent_id="tokyo_weather_planner", agent_name="Tokyo Activity Planner Crew"
    ):
        run_multi_agent_workflow(build_llm())


if __name__ == "__main__":
    main()
