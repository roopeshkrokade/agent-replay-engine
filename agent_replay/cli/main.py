import argparse
import json
import sys
from pathlib import Path

from agent_replay.adapters.otel import OTelSpanAdapter
from agent_replay.tracking import get_tracking_uri, post_json
from agent_replay.compiler import IRCompiler, PlanCompiler, ReplaySession
from agent_replay.storage import SQLiteGraphStore
from agent_replay.runtime import ReplayVM

def compile_trace(args):
    print(f"📥 Parsing trace: {args.file}...")
    events = OTelSpanAdapter().parse_file(args.file)

    print("⚙️  Compiling Execution Graph (IR)...")
    graph = IRCompiler().compile(events)

    print("💾 Saving to local store...")
    store = SQLiteGraphStore()
    agent_id = args.agent_id or Path(args.file).stem
    record_id = store.save(graph, agent_id=agent_id, agent_name=args.agent_name or agent_id)

    print(f"✅ Success! Compiled graph '{graph.id}' saved as {record_id}")

def simulate_replay(args):
    print(f"📂 Loading graph '{args.graph_id}' from store...")
    store = SQLiteGraphStore()

    try:
        graph = store.load(args.graph_id)
    except ValueError as e:
        print(f"❌ Error: {e}")
        return

    print("⚙️  Compiling Replay Plan (CACHE mode)...")
    plan = PlanCompiler().compile(graph, ReplaySession(mode="CACHE"))

    print("🚀 Booting Replay VM...\n")
    vm = ReplayVM(plan)

    print("--- SIMULATING EXECUTION ---")
    # For simulation, we push the expected inputs through the VM to verify it works
    for i, instruction in enumerate(plan.instructions, 1):
        expected_input = instruction.expected_input
        print(f"\n[Step {i}] App sends input: {expected_input}")

        result = vm.advance(expected_input)

        if result.success:
            print(f"✅ VM Resolved Node: {result.resolution.node_id}")
            print(f"📦 VM Returned Output: {result.output}")
        else:
            print(f"❌ VM Failed: {result.resolution.reason}")
            break

    print("\n🎉 Simulation complete.")

def replay_record(args):
    """Ask the tracking server to re-run a recorded agent against its recording."""
    faults = [_parse_fault(f) for f in args.fault]
    print(f"🚀 Replaying {args.record_id} via {get_tracking_uri()} ({args.match} match)...")
    result = post_json(
        f"/api/runs/{args.record_id}/replay",
        {"match": args.match, "faults": faults, "timeout": args.timeout},
        timeout=args.timeout + 30,
    )
    print(result.get("logs", ""))
    print(f"\n{'✅' if result.get('status') == 'success' else '❌'} {result.get('message')}")
    if args.json:
        print(json.dumps(result.get("report", {}), indent=2, default=str))
    sys.exit(0 if result.get("status") == "success" else 1)

def set_entrypoint(args):
    """Attach the command to re-run, for records made before the OTel migration or interactively."""
    command = args.command_line[1:] if args.command_line[:1] == ["--"] else args.command_line
    if not command:
        sys.exit("Give the command after --, e.g. agent-replay set-entrypoint REC -- python examples/crewai_weather.py")
    result = post_json(f"/api/runs/{args.record_id}/entrypoint",
                       {"argv": command, "cwd": str(Path.cwd())}, method="PUT")
    print(f"✅ {args.record_id} will replay with: {result['entrypoint']['executable']} "
          f"{' '.join(result['entrypoint']['argv'])}  (cwd {result['entrypoint']['cwd']})")

def recompile(args):
    result = post_json(f"/api/runs/{args.record_id}/recompile", {})
    print(f"✅ Recompiled {result['record_id']} from its raw spans ({result['nodes']} nodes)")

def serve(args):
    from agent_replay.server.app import serve as run_server
    run_server(host=args.host, port=args.port)

def _parse_fault(spec: str) -> dict:
    """STEP[:STATUS][:persistent], e.g. 2 or 2:503 or 3:500:persistent"""
    parts = spec.split(":")
    fault = {"step": int(parts[0])}
    if len(parts) > 1 and parts[1]:
        fault["status"] = int(parts[1])
    if len(parts) > 2:
        fault["persistent"] = parts[2].lower() == "persistent"
    return fault

def main():
    parser = argparse.ArgumentParser(description="Agent Replay Engine CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="Run the tracking server (UI, OTLP receiver, replay endpoint)")
    serve_parser.add_argument("--host", default=None, help="Bind address (default 127.0.0.1)")
    serve_parser.add_argument("--port", type=int, default=None, help="Port (default 5000)")

    replay_parser = subparsers.add_parser("replay", help="Re-run a recorded agent against its recording")
    replay_parser.add_argument("record_id", type=str, help="Record to replay, e.g. tokyo_weather_planner_v1.0.0")
    replay_parser.add_argument("--match", choices=["RELAXED", "STRICT"], default="RELAXED")
    replay_parser.add_argument("--fault", action="append", default=[], metavar="STEP[:STATUS][:persistent]",
                               help="Inject a failure on a model call, e.g. --fault 2:503")
    replay_parser.add_argument("--timeout", type=float, default=600)
    replay_parser.add_argument("--json", action="store_true", help="Print the full replay report")

    entry_parser = subparsers.add_parser("set-entrypoint", help="Set the command a record is replayed with")
    entry_parser.add_argument("record_id", type=str)
    entry_parser.add_argument("command_line", nargs=argparse.REMAINDER, help="-- python path/to/agent.py [args]")

    recompile_parser = subparsers.add_parser("recompile", help="Rebuild a record's graph from its stored spans")
    recompile_parser.add_argument("record_id", type=str)

    # Command: compile
    compile_parser = subparsers.add_parser("compile", help="Compile an OTel span JSON export into an IR graph")
    compile_parser.add_argument("file", type=str, help="Path to the raw trace JSON file")
    compile_parser.add_argument("--agent-id", default=None)
    compile_parser.add_argument("--agent-name", default=None)

    # Command: simulate
    simulate_parser = subparsers.add_parser("simulate", help="Simulate a replay from a compiled graph")
    simulate_parser.add_argument("graph_id", type=str, help="The record ID to replay (e.g., weather_bot_v1.0.0)")

    args = parser.parse_args()

    if args.command == "compile":
        compile_trace(args)
    elif args.command == "simulate":
        simulate_replay(args)
    elif args.command == "replay":
        replay_record(args)
    elif args.command == "serve":
        serve(args)
    elif args.command == "set-entrypoint":
        set_entrypoint(args)
    elif args.command == "recompile":
        recompile(args)

if __name__ == "__main__":
    main()
