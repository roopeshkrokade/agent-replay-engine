import sys
from pathlib import Path
import litellm
from env_utils import get_hf_token

# Ensure root directory is in the path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autogen import ConversableAgent, UserProxyAgent  # noqa: E402
from storage.db import SQLiteGraphStore  # noqa: E402
from compiler import IRCompiler  # noqa: E402
from sdk import LiveRecorder  # noqa: E402

# ---------------------------------------------------------
# 1. THE BRIDGE: Route AutoGen to LiteLLM
# ---------------------------------------------------------
class LiteLLMClient:
    """A custom client that forces AutoGen to use LiteLLM for routing."""
    def __init__(self, config, **kwargs):
        self.model = config.get("model", "huggingface/Qwen/Qwen2.5-Coder-7B-Instruct")
        self.api_key = config.get("api_key")

    def create(self, params):
        messages = params.get("messages", [])
        response = litellm.completion(
            model=self.model,
            messages=messages,
            api_key=self.api_key
        )
        # Add a cost attribute to satisfy AutoGen's internal trackers
        response.cost = 0.0
        return response

    def message_retrieval(self, response):
        return [choice.message.content for choice in response.choices]

    def cost(self, response) -> float:
        return getattr(response, "cost", 0.0)

    @staticmethod
    def get_usage(response):
        return {}

# ---------------------------------------------------------
# 2. THE AUTOGEN WORKFLOW
# ---------------------------------------------------------
def run_autogen_workflow(hf_token):
    print("  App: Booting AutoGen...")
    
    config_list = [{
        "model": "huggingface/Qwen/Qwen2.5-Coder-7B-Instruct",
        "api_key": hf_token,
        "model_client_cls": "LiteLLMClient"
    }]

    # Create the AI Agent
    assistant = ConversableAgent(
        name="Tokyo_Expert",
        system_message="You are a helpful travel expert for Tokyo. Provide concise, 1-sentence answers.",
        llm_config={"config_list": config_list},
    )
    # Register our custom bridge client
    assistant.register_model_client(model_client_cls=LiteLLMClient)

    # Create the User Agent (Simulates the human triggering the chat)
    user_proxy = UserProxyAgent(
        name="User",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1, # Stop after 1 exchange
        is_termination_msg=lambda x: True
    )

    print("  App: Initiating Chat...")
    user_proxy.initiate_chat(
        assistant,
        message="What is the absolute best neighborhood for a first-time visitor to stay in Tokyo?"
    )

# ---------------------------------------------------------
# 3. LIVE RECORDING SCRIPT (Identical to CrewAI implementation)
# ---------------------------------------------------------
def main():
    store = SQLiteGraphStore()
    
    agent_id = "autogen_tokyo_expert"
    agent_name = "AutoGen Tokyo Travel Expert"

    print("==================================================")
    print(f"🔴 RECORDING LIVE EXECUTION: {agent_name}")
    print("==================================================")

    recorder = LiveRecorder()
    
    def extract_messages(*args, **kwargs):
        messages = kwargs.get("messages", [])
        last_msg = messages[-1]["content"] if messages else ""
        return {"prompt_snippet": last_msg[-500:]}

    # Patch LiteLLM - because of our Bridge, AutoGen gets caught in this net!
    recorder.patch(litellm, "completion", extract_messages, "MODEL")
    
    hf_token = get_hf_token()
    if not hf_token:
        raise ValueError("HF_TOKEN missing from environment.")
        
    run_autogen_workflow(hf_token)
    
    events = recorder.finish()
    graph = IRCompiler().compile(events)
    
    record_id = store.save(graph, agent_id=agent_id, agent_name=agent_name)
    print(f"\n💾 [System] Agent execution preserved in history as: {record_id}")

if __name__ == "__main__":
    main()