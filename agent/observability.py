from __future__ import annotations

import os
from typing import Any


def configure_telemetry(app: Any | None = None) -> None:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": "placementgap"}))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
        trace.set_tracer_provider(provider)
        if app is not None:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app)
    except ImportError:
        return


def span_for(name: str, attributes: dict[str, Any] | None = None) -> Any:
    try:
        from opentelemetry import trace

        return trace.get_tracer("placementgap").start_as_current_span(name, attributes=attributes or {})
    except ImportError:
        from contextlib import nullcontext

        return nullcontext()
