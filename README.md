# Agent Replay Engine

**A deterministic replay platform for GenAI workflows.**

## What is it?
Modern GenAI applications are difficult to test because the same workflow may produce different outputs across executions. Existing tracing systems (like LangSmith or MLflow) capture *what happened*, but they are not designed to deterministically *replay* those executions for regression testing or model comparison.

The Agent Replay Engine records agent runs as standard OpenTelemetry spans and replays them deterministically. It works with any agent framework that has OTel instrumentation; the engine contains no framework-specific code and does not monkey-patch your LLM client.

## Quickstart

```bash
uv sync --all-extras                             # engine + example frameworks (CrewAI, AG2) and their instrumentors
(cd frontend && npm ci && npm run build)         # build the dashboard into the package (once, or after UI changes)
agent-replay serve                               # dashboard + API on http://localhost:5000
```

Like `mlflow server`, one process on port 5000 serves the React dashboard at `/`, the REST API under `/api`
(interactive docs at `/docs`), the OTLP span receiver at `/v1/traces`, and the replay endpoint under `/replay`.
For UI development run `npm run dev` in `frontend/`; it proxies `/api` to the server on :5000.

Add two lines to your agent (MLflow-style):

```python
import agent_replay
agent_replay.autolog()        # enables every installed OTel instrumentor

with agent_replay.start_run(agent_id="weather_bot", agent_name="Weather Bot"):
    crew.kickoff()            # any framework
```

Each run is stored as a new version (`weather_bot_v1.0.0`, `v2.0.0`, ...). Replay it from the UI's Replay button, or:

```bash
agent-replay replay weather_bot_v1.0.0                  # RELAXED: serve responses by position
agent-replay replay weather_bot_v1.0.0 --match STRICT   # requests must equal the recording
agent-replay replay weather_bot_v1.0.0 --fault 2:503    # inject a failure on model call 2
```

or in-process:

```python
with agent_replay.replay("weather_bot_v1.0.0") as session:
    build_and_run_agent()     # create LLM clients inside the block
print(session.report["divergences"])
```

Working examples: [examples/openai_tools.py](examples/openai_tools.py) (plain OpenAI SDK), [examples/crewai_weather.py](examples/crewai_weather.py), [examples/autogen_tokyo.py](examples/autogen_tokyo.py).

### Integration requirements
1. **An OTel instrumentor for your framework or LLM client** (e.g. `openinference-instrumentation-crewai`, `openinference-instrumentation-openai`). `autolog()` discovers installed instrumentors through the standard `opentelemetry_instrumentor` entry point. Apps in other languages can export OTLP/HTTP directly to `http://localhost:5000/v1/traces`.
2. **The LLM endpoint must come from the environment.** During replay the engine sets `OPENAI_BASE_URL` / `OPENAI_API_BASE` and `ANTHROPIC_BASE_URL` to its replay endpoint (and dummy API keys if none are set). Clients that hardcode their base URL bypass replay.

### What replay serves

| API | Endpoint | Streaming |
|---|---|---|
| OpenAI Chat Completions | `/replay/{session}/v1/chat/completions` | yes |
| OpenAI Responses | `/replay/{session}/v1/responses` | yes |
| Anthropic Messages | `/replay/{session}/v1/messages` | yes |
| OpenAI Embeddings | `/replay/{session}/v1/embeddings` | n/a (float or base64) |

* **Matching:** each request gets the unserved recorded call with the same conversation, so concurrent or reordered calls receive their own responses. If nothing matches, RELAXED serves the next recorded call and reports a warning; STRICT fails the call with expected/got.
* **Recorded errors are replayed:** a call that failed while recording (e.g. HTTP 429) fails again with the same status and body, marked `x-should-retry: false` so the SDK raises it once, as the app originally saw it.
* **Faults:** `--fault 2:503` fails call 2 once (clients retry it); `--fault 2:500:persistent` fails every attempt.
* **Tools** re-execute during replay; their spans are compared with the recording and changes are reported.

### Older records and maintenance

```bash
agent-replay set-entrypoint tokyo_weather_planner_v1.0.0 -- python examples/crewai_weather.py   # make a record replayable from the UI
agent-replay recompile tokyo_weather_planner_v1.0.0    # rebuild a graph from its stored spans after an engine upgrade
```
Raw spans are kept with their record (and deleted with it). Spans no record refers to, such as abandoned runs, are pruned after `AGENT_REPLAY_SPAN_RETENTION_HOURS` (default 24).

### Security

The replay API re-runs recorded commands, so the server:
* only answers requests addressed to `localhost` (blocks DNS-rebinding pages); add names with `AGENT_REPLAY_ALLOWED_HOSTS`,
* requires a bearer token for `/api` and OTLP when `AGENT_REPLAY_TOKEN` is set. The SDK, CLI and replayed agents send it from the same variable, and the dashboard asks for it once,
* refuses to bind a non-loopback address (`--host 0.0.0.0`) unless a token is set.

## How it Works

```text
Record:  app + autolog() ──OTLP──▶ /v1/traces ──▶ raw spans ──▶ Adapter ──▶ IR Compiler ──▶ versioned graph
Replay:  app (OPENAI_BASE_URL=/replay/{session}/v1) ──▶ Replay VM ──▶ recorded completions
         tools run live; their spans are diffed against the recording
```

1. **Recording:** framework instrumentors emit OTel spans; the engine stores them raw, grouped by run.
2. **Adapters:** classify spans with the GenAI semantic conventions (OpenInference or OTel `gen_ai.*`, not `SpanKind`) and normalise model I/O to the OpenAI chat-completion format.
3. **IR Compiler:** builds an immutable `ExecutionGraph`: the span tree from `parent_span_id`, plus the ordered replay points. Outer framework LLM spans that wrap a provider call are deduplicated, and spans with dropped data are marked non-replayable.
4. **Plan Compiler + Replay Scheduler:** serve each model and embedding request from the recording, matched by content (RELAXED or STRICT, optional fault injection), and report divergences: changed requests, over/under-execution, and changed tool calls or results. The dashboard shows them with expected/got side by side.

## Project Layout

```text
agent_replay/            installable package (`uv sync` installs it and the `agent-replay` CLI)
  __init__.py            client API: autolog, start_run, end_run, replay, set_tracking_uri
  autolog.py tracking.py replay.py
  adapters/otel/         OTel spans -> canonical events (OpenInference & GenAI dialects)
  ir/                    immutable execution graph model
  compiler/              IR compiler and replay plan compiler
  runtime/               replay VM, matchers, tool divergence diff
  storage/               SQLite store for graphs and raw spans
  server/                tracking server: API, OTLP receiver, replay gateway
  server/ui/             built dashboard (generated by `npm run build`, gitignored, shipped in the wheel)
  cli/                   `agent-replay serve | replay | compile | simulate`
examples/                runnable agents (plain OpenAI SDK, CrewAI, AG2)
tests/                   pytest suite; fixtures/ holds sample span exports
frontend/                React dashboard source (Vite)
```

## Intended Users

* AI Platform Engineers
* Infrastructure Engineers
* LLM Application Developers
* CI/CD Platform Teams

## Architectural Boundaries & Non-Goals

🚨 **We are NOT an observability platform.** We do not instrument applications ourselves, manage prompt templates, or track token costs. Telemetry comes from standard OTel instrumentation; our job is to turn it into a replayable execution graph.

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed compiler pipelines, subsystem contracts, and invariants.

## Current Status

🚧 **Prototype**

* Recording through any OTel instrumentation (OpenInference and OTel GenAI conventions)
* Replay of OpenAI Chat Completions, Responses and Embeddings, and Anthropic Messages, including streaming and recorded errors
* Tools re-execute during replay and are diffed, not stubbed
* Not yet: OpenAI Realtime/Assistants, image and audio endpoints, Gemini and Bedrock wire formats
