from adapters.openinference.adapter import OpenInferenceAdapter

def test_adapter_parsing():
    print("1. Initializing OpenInference Adapter...")
    adapter = OpenInferenceAdapter()
    
    print("2. Parsing sample_trace.json into Canonical Events...")
    events = adapter.parse_file("sample_trace.json")
    
    print("\n--- CANONICAL EVENT STREAM ---")
    for event in events:
        print(f"[{event.timestamp}] {event.kind.name} (id: {event.id})")
        if "input" in event.payload:
            print(f"    Input: {event.payload['input']}")
        if "output" in event.payload:
            print(f"    Output: {event.payload['output']}")
    print("------------------------------\n")
    
    print(f"✅ Success! Parsed {len(events)} Canonical Events.")

if __name__ == "__main__":
    test_adapter_parsing()