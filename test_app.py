from storage import LocalGraphStore
from compiler import PlanCompiler, ReplaySession
from runtime import ReplayVM
from sdk.interceptor import ReplayInterceptor

# --- 1. THE MOCK APPLICATION SDK ---
class DummyOpenAI:
    """Simulates a third-party library that normally makes live network calls."""
    def chat(self, messages: list) -> dict:
        print("    🌐 [Network] Making live API call to OpenAI...")
        return {"type": "message", "content": "Live response from the internet"}

    def call_tool(self, tool_name: str, **kwargs) -> str:
        print(f"    ⚙️ [Network] Executing live tool '{tool_name}'...")
        return "Live tool result"

def run_application_workflow(client: DummyOpenAI):
    """A standard LLM app workflow that knows nothing about the Replay Engine."""
    print("  App: Asking LLM for weather...")
    response = client.chat(messages=[{"role": "user", "content": "What is the weather in Tokyo?"}])
    print(f"  App: LLM returned -> {response}\n")
    
    if isinstance(response, dict) and response.get("type") == "tool_call":
        print("  App: Executing requested tool...")
        tool_result = client.call_tool(tool_name=response["name"], loc="Tokyo")
        print(f"  App: Tool returned -> {tool_result}")

# --- 2. THE INTERCEPTION DEMO ---
def test_sdk_interception():
    client = DummyOpenAI()
    
    print("==================================================")
    print("🔴 RUNNING APP (LIVE MODE - NO REPLAY ENGINE)")
    print("==================================================")
    run_application_workflow(client)
    
    print("\n==================================================")
    print("🟢 INJECTING REPLAY ENGINE (CACHE MODE)")
    print("==================================================")
    
    # 1. Boot the VM from our persistent storage
    graph = LocalGraphStore().load("g_compiled_001")
    plan = PlanCompiler().compile(graph, ReplaySession(mode="CACHE"))
    vm = ReplayVM(plan)
    
    # 2. Patch the client! 
    # The lambda functions map the SDK arguments to the dictionaries our VM expects.
    interceptor = ReplayInterceptor(vm)
    interceptor.patch(client, "chat", lambda messages: messages[0]) 
    interceptor.patch(client, "call_tool", lambda tool_name, **kwargs: kwargs)

    # 3. Run the exact same application code. It should never hit the "Network" prints.
    run_application_workflow(client)

if __name__ == "__main__":
    test_sdk_interception()