# ARCHITECTURE.md
**Project:** Agent Replay Engine
**Version:** 1.2.0

## 1. Core Philosophy & System Boundary

> **The Replay Engine is not a tracing system. It is not an observability platform. It is not an evaluation framework. Its responsibility begins after a trace has been produced.**

The Agent Replay Engine is a deterministic replay platform for GenAI workflows. It uses a compiler pipeline to transform standardized execution traces into a provider-agnostic Intermediate Representation (IR), compiles that representation into executable replay plans, and executes those plans through a deterministic runtime.

*   **Determinism over Fidelity:** Whenever there is a trade-off between perfectly reproducing the original telemetry and ensuring deterministic replay, the engine will always choose determinism.
*   **Compiler Purity:** The compiler pipeline is entirely side-effect-free.

## 2. Architectural Layers

```text
                  External Telemetry
                          │
                          ▼
                    Adapter Layer
                          │
                          ▼
                 Canonical Event Model
                          │
                          ▼
          Execution Graph (Intermediate Representation)
                          │
                          ▼
                 Compiler Pipeline (Pure)
                          │
                          ▼
             Replay Plan (Executable Instructions)
                          │
                          ▼
              Deterministic Replay Runtime
                          │
                          ▼
                    Application SDK

```

## 3. Architectural Invariants

1. **IR Immutability:** Once an `ExecutionGraph` is constructed, it is permanently read-only.
2. **Behavioral Equivalence:** Two semantically equivalent executions must compile into identical `ExecutionGraphs`, regardless of the telemetry provider.
3. **Deterministic Replay Plans:** Given an identical `ExecutionGraph` and `ReplaySession`, the Compiler must generate the exact same `ReplayPlan`.
4. **Stateless Runtime:** The VM owns only the active execution cursor.
5. **Sealed Adapters:** Trace Adapters parse proprietary telemetry, but the compiler and runtime must never know those formats exist.
6. **Separation of Matching and Execution:** The `Matcher` solely resolves incoming payloads. The `Executor` solely evaluates instructions.

## 4. Glossary

| Term | Meaning |
| --- | --- |
| **Trace** | The vendor-specific telemetry artifact (e.g., OpenInference JSON). |
| **Canonical Event** | A normalized lifecycle event independent of trace origin. |
| **Execution Graph** | The provider-agnostic, immutable workflow Intermediate Representation (IR). |
| **Replay Session** | The volatile, user-provided runtime configuration mapping. |
| **Replay Plan** | The compiled, immutable sequence of executable instructions (Bytecode). |
| **Replay Runtime** | The deterministic virtual machine that evaluates and executes instructions. |


