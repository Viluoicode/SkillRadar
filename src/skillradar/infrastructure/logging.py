"""Logging setup. Libraries call ``logging.getLogger(__name__)`` directly; the composition
root (CLI / flow) calls :func:`configure_logging` once to install handlers."""

from __future__ import annotations

import logging
import os

_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=os.environ.get("SKILLRADAR_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    _CONFIGURED = True
