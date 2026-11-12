"""Structured logging: JSON lines in production, readable console output in development.

Standard-library loggers (uvicorn, arq, ...) are routed through the same structlog pipeline,
so every line has the same shape. Use `structlog.get_logger()` in app code.
"""

import logging
import sys

import structlog
from structlog.types import Processor


def configure_logging(level: str = "INFO", *, json: bool = False) -> None:
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    renderer: Processor = (
        structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                *([structlog.processors.format_exc_info] if json else []),
                renderer,
            ],
        )
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    # Libraries such as uvicorn and arq install their own handlers; strip them so every line goes
    # through the root handler once, in one format.
    for name in [*logging.root.manager.loggerDict, "uvicorn", "uvicorn.error", "uvicorn.access"]:
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True
    # Access logs are replaced by the request-logging middleware in main.py.
    logging.getLogger("uvicorn.access").disabled = True
