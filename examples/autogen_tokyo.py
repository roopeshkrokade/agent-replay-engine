"""
AG2 (AutoGen) two-agent chat, recorded through OpenTelemetry. AG2 talks to the model through its
native OpenAI client, so no LiteLLM bridge is needed.

    uv sync --extra autogen
    agent-replay serve                   # tracking server on :5000
    python examples/autogen_tokyo.py     # record
Replay from the UI, or: agent-replay replay <record_id>
"""
import os

import agent_replay
from env_utils import get_hf_token

agent_replay.autolog()

from autogen import ConversableAgent, UserProxyAgent  # noqa: E402 - instrumentation is enabled first

# During replay agent-replay sets OPENAI_BASE_URL to its replay server, so read it from the env.
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://router.huggingface.co/v1")
MODEL = os.environ.get("EXAMPLE_MODEL", "Qwen/Qwen3-8B:nscale")  # must support tool calling


def run_autogen_workflow(api_key: str) -> None:
    print("  App: Booting AutoGen...")
    llm_config = {
        "config_list": [{"model": MODEL, "base_url": BASE_URL, "api_key": api_key, "api_type": "openai"}],
        "cache_seed": None,  # AG2's disk cache would hide calls from both recording and replay
    }
    assistant = ConversableAgent(
        name="Tokyo_Expert",
        system_message="You are a helpful travel expert for Tokyo. Provide concise, 1-sentence answers.",
        llm_config=llm_config,
    )
    user_proxy = UserProxyAgent(
        name="User",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1,
        is_termination_msg=lambda x: True,
        code_execution_config=False,
    )
    print("  App: Initiating Chat...")
    user_proxy.initiate_chat(
        assistant,
        message="What is the absolute best neighborhood for a first-time visitor to stay in Tokyo?",
    )


def main():
    with agent_replay.start_run(agent_id="autogen_tokyo_expert", agent_name="AutoGen Tokyo Travel Expert"):
        run_autogen_workflow(get_hf_token() or os.environ.get("OPENAI_API_KEY"))


if __name__ == "__main__":
    main()
