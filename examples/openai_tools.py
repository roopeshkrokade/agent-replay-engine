"""
Plain OpenAI SDK tool-calling loop: no agent framework at all.

The OpenAI calls are recorded by the OpenInference OpenAI instrumentor (found by autolog());
the tool is recorded with a hand-written span using the OTel GenAI conventions.

    agent-replay serve                 # tracking server on :5000
    python examples/openai_tools.py    # record
    agent-replay replay <record_id>
"""
import json
import os

import agent_replay
from env_utils import get_hf_token

agent_replay.autolog()

from openai import OpenAI  # noqa: E402 - instrumentation is enabled first

# During replay agent-replay sets OPENAI_BASE_URL to its replay server, so read it from the env.
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://router.huggingface.co/v1")
MODEL = os.environ.get("EXAMPLE_MODEL", "Qwen/Qwen3-8B:nscale")  # must support tool calling

TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {"location": {"type": "string"}},
            "required": ["location"],
        },
    },
}]


def get_weather(location: str) -> str:
    print(f"    🛠️  [Tool Execution] Live fetching weather for {location}...")
    return f"The weather in {location} is 75F and sunny."


def run_weather_agent(client: OpenAI, model: str = MODEL, max_turns: int = 5) -> str:
    tracer = agent_replay.get_tracer("examples.openai_tools")
    messages = [{"role": "user", "content": "What is the weather in Tokyo? Use the get_weather tool."}]
    for _ in range(max_turns):
        response = client.chat.completions.create(model=model, messages=messages, tools=TOOLS)
        message = response.choices[0].message
        if not message.tool_calls:
            return message.content or ""
        messages.append(message.model_dump(exclude_none=True))
        for call in message.tool_calls:
            with tracer.start_as_current_span(f"execute_tool {call.function.name}") as span:
                span.set_attribute("gen_ai.operation.name", "execute_tool")
                span.set_attribute("gen_ai.tool.name", call.function.name)
                span.set_attribute("gen_ai.tool.call.id", call.id)
                span.set_attribute("gen_ai.tool.call.arguments", call.function.arguments)
                result = get_weather(**json.loads(call.function.arguments))
                span.set_attribute("gen_ai.tool.call.result", result)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
    return "Gave up after too many turns."


def main():
    client = OpenAI(base_url=BASE_URL, api_key=get_hf_token() or os.environ.get("OPENAI_API_KEY"))
    with agent_replay.start_run(agent_id="openai_weather_tools", agent_name="OpenAI Weather Tools"):
        answer = run_weather_agent(client)
    print(f"\n  App: Final Output -> {answer}")


if __name__ == "__main__":
    main()
