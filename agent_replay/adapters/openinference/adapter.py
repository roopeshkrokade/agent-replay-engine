from agent_replay.adapters.otel import OTelSpanAdapter


class OpenInferenceAdapter(OTelSpanAdapter):
    """
    Kept for backwards compatibility. OpenInference is now one dialect handled by the
    framework-agnostic OTelSpanAdapter.
    """
