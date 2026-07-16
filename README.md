# Agent Replay Engine

**A deterministic replay platform for GenAI workflows.**

## What is it?
Modern GenAI applications are difficult to test because the same workflow may produce different outputs across executions. Existing tracing systems (like LangSmith or MLflow) capture *what happened*, but they are not designed to deterministically *replay* those executions for regression testing or model comparison.

The Agent Replay Engine enables deterministic replay of AI agent workflows using execution traces that have already been collected by existing observability systems. 

## How it Works
Internally, the engine behaves like a compiler and a virtual machine. It completely isolates telemetry formats from execution mechanics:

1. **Adapters:** Translate external traces (e.g., OpenInference) into Canonical Events.
2. **IR Compiler:** Builds an immutable `ExecutionGraph` (Intermediate Representation) from the events.
3. **Plan Compiler:** Merges the IR with user-defined policies to create a `ReplayPlan` (Bytecode).
4. **Deterministic Runtime:** A stateless VM that intercepts application SDK calls and deterministically returns the historical state.

```text
Trace -> Adapter -> Execution Graph (IR) -> Replay Plan -> Runtime

```

## Intended Users

* AI Platform Engineers
* Infrastructure Engineers
* LLM Application Developers
* CI/CD Platform Teams

## Architectural Boundaries & Non-Goals

🚨 **We are NOT an observability platform.** We do not capture raw application telemetry, manage prompt templates, or track token costs. Our job begins *after* the trace is produced.

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed compiler pipelines, subsystem contracts, and invariants.

## Current Status

🚧 **Early Prototype**
Current focus:

* OpenInference trace adaptation
* IR Compilation and Graph Serialization
* Stateless deterministic Replay VM

