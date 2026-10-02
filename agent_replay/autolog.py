"""
autolog(): record any agent framework through OpenTelemetry, with no monkey-patching of our own.

Every instrumentor installed in the environment (OpenInference, OpenLLMetry, opentelemetry-
instrumentation-*) registers under the standard `opentelemetry_instrumentor` entry point.
We discover them there and point them at a TracerProvider that exports to the tracking server,
so the engine itself never names a framework.
"""
import atexit
import logging
import os
import threading
from importlib.metadata import entry_points
from typing import Any, Iterable, List, Optional

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanLimits, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ALWAYS_ON

from . import tracking

logger = logging.getLogger(__name__)

INSTRUMENTOR_ENTRY_POINT_GROUP = "opentelemetry_instrumentor"
RUN_ID_ATTRIBUTE = "agent_replay.run_id"

# Replay needs every byte: no truncation and no attribute/event caps.
REPLAY_SPAN_LIMITS = SpanLimits(
    max_attributes=SpanLimits.UNSET,
    max_events=SpanLimits.UNSET,
    max_links=SpanLimits.UNSET,
    max_span_attributes=SpanLimits.UNSET,
    max_event_attributes=SpanLimits.UNSET,
    max_link_attributes=SpanLimits.UNSET,
    max_attribute_length=SpanLimits.UNSET,
    max_span_attribute_length=SpanLimits.UNSET,
)

# Instrumentors following the OTel GenAI conventions keep message content off by default.
CONTENT_CAPTURE_ENV = {"OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "true"}

_lock = threading.Lock()
_provider: Optional[TracerProvider] = None
_instrumentors: List[Any] = []
instrumented: List[str] = []


class RunTagProcessor(SpanProcessor):
    """Stamps each span with the run it belongs to, so the server can group them."""

    def on_start(self, span: Span, parent_context: Optional[otel_context.Context] = None) -> None:
        run = tracking.current_run()
        run.span_count += 1
        span.set_attribute(RUN_ID_ATTRIBUTE, run.run_id)

    def on_end(self, span: ReadableSpan) -> None:
        pass


def autolog(
    disable: bool = False,
    include: Optional[Iterable[str]] = None,
    exclude: Iterable[str] = (),
    service_name: Optional[str] = None,
) -> List[str]:
    """
    Enable recording for every installed OTel instrumentor. Returns the instrumentors enabled.

    include / exclude filter by entry-point name (e.g. "crewai", "openai").
    """
    global _provider
    if disable:
        _disable()
        return []

    with _lock:
        if _provider is not None:
            return list(instrumented)

        for key, value in CONTENT_CAPTURE_ENV.items():
            os.environ.setdefault(key, value)

        provider = TracerProvider(
            resource=Resource.create({"service.name": service_name or tracking.current_run().agent_id}),
            sampler=ALWAYS_ON,
            span_limits=REPLAY_SPAN_LIMITS,
        )
        provider.add_span_processor(RunTagProcessor())
        provider.add_span_processor(BatchSpanProcessor(
            OTLPSpanExporter(endpoint=f"{tracking.get_tracking_uri()}/v1/traces", headers=tracking.auth_headers())
        ))
        _provider = provider

        # Let the app's own manual spans land in the same trace when it has no provider of its own.
        if isinstance(trace.get_tracer_provider(), trace.ProxyTracerProvider):
            trace.set_tracer_provider(provider)

        _instrument_installed(provider, set(include) if include is not None else None, set(exclude))
        atexit.register(_shutdown)
        logger.info("agent-replay autolog enabled: %s", instrumented or "no instrumentors found")
        return list(instrumented)


def flush(timeout_millis: int = 30000) -> None:
    if _provider is not None:
        _provider.force_flush(timeout_millis)


def get_tracer(name: str = "agent_replay"):
    """A tracer on the recording provider, for apps that add their own spans."""
    if _provider is None:
        raise RuntimeError("Call agent_replay.autolog() first.")
    return _provider.get_tracer(name)


def _instrument_installed(provider: TracerProvider, include, exclude) -> None:
    for ep in entry_points(group=INSTRUMENTOR_ENTRY_POINT_GROUP):
        if (include is not None and ep.name not in include) or ep.name in exclude:
            continue
        try:
            instrumentor = ep.load()()
        except Exception as exc:  # noqa: BLE001 - a broken optional instrumentor must not stop recording
            logger.debug("Skipping instrumentor %s: %s", ep.name, exc)
            continue
        if instrumentor.is_instrumented_by_opentelemetry:
            continue  # already owned by someone else in this process
        try:
            # BaseInstrumentor skips itself when its target library is not installed.
            instrumentor.instrument(tracer_provider=provider)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Instrumentor %s failed: %s", ep.name, exc)
            continue
        if instrumentor.is_instrumented_by_opentelemetry:
            instrumented.append(ep.name)
            _instrumentors.append(instrumentor)


def _disable() -> None:
    global _provider
    with _lock:
        for instrumentor in _instrumentors:
            try:
                instrumentor.uninstrument()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to uninstrument %s: %s", type(instrumentor).__name__, exc)
        _instrumentors.clear()
        instrumented.clear()
        provider, _provider = _provider, None
    if provider is not None:
        provider.shutdown()


def _shutdown() -> None:
    try:
        tracking.end_run()
        tracking.end_implicit_run()
    except Exception as exc:  # noqa: BLE001 - never fail interpreter exit
        logger.warning("agent-replay could not finalise the run: %s", exc)
    _disable()
