from storage import LocalGraphStore
from compiler import IRCompiler, PlanCompiler, ReplaySession
from runtime import ReplayVM
from sdk import ReplayInterceptor, LiveRecorder

# --- THE MOCK APPLICATION ---
class DummyOpenAI:
    def chat(self, messages: list) -> dict:
        return {"type": "tool_call", "name": "get_weather"}

    def call_tool(self, tool_name: str, **kwargs) -> str:
        return "72F (Live Data)"

def run_application_workflow(client: DummyOpenAI):
    print("  App: Asking LLM for weather...")
    response = client.chat(messages=[{"role": "user", "content": "What is the weather in Tokyo?"}])
    
    if isinstance(response, dict) and response.get("type") == "tool_call":
        print("  App: Executing requested tool...")
        tool_result = client.call_tool(tool_name=response["name"], loc="Tokyo")
        print(f"  App: Final Output -> {tool_result}")

# --- THE RECORD/REPLAY DEMO ---
def test_autolog_flow():
    # ---------------------------------------------------------
    # PHASE 1: RECORD LIVE EXECUTION
    # ---------------------------------------------------------
    print("==================================================")
    print("🔴 PHASE 1: RECORDING LIVE APP EXECUTION")
    print("==================================================")
    live_client = DummyOpenAI()
    recorder = LiveRecorder()
    
    # "Autolog" the client methods
    recorder.patch(live_client, "chat", lambda messages: messages[0], "MODEL")
    recorder.patch(live_client, "call_tool", lambda tool_name, **kwargs: kwargs, "TOOL")
    
    # Run app and record events
    run_application_workflow(live_client)
    
    # Compile the live events straight into our IR and save to disk
    events = recorder.finish()
    graph = IRCompiler().compile(events)
    store = LocalGraphStore()
    store.save(graph)
    print(f"\n💾 [System] Live execution compiled and saved to {graph.id}.json")


    # ---------------------------------------------------------
    # PHASE 2: REPLAY CACHED EXECUTION
    # ---------------------------------------------------------
    print("\n==================================================")
    print("🟢 PHASE 2: DETERMINISTIC REPLAY (NO NETWORK)")
    print("==================================================")
    replay_client = DummyOpenAI()
    
    # Load the graph we literally just recorded
    loaded_graph = store.load(graph.id)
    plan = PlanCompiler().compile(loaded_graph, ReplaySession(mode="CACHE"))
    vm = ReplayVM(plan)
    
    # Patch the client for Replay
    interceptor = ReplayInterceptor(vm)
    interceptor.patch(replay_client, "chat", lambda messages: messages[0]) 
    interceptor.patch(replay_client, "call_tool", lambda tool_name, **kwargs: kwargs)

    # Run the exact same app again!
    run_application_workflow(replay_client)

if __name__ == "__main__":
    test_autolog_flow()