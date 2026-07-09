"""Logging setup for desktop (file) and cloud (stdout) deployments."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from vaybooks.bms.infrastructure.config.paths import get_logs_dir
from vaybooks.bms.infrastructure.config.runtime import is_desktop

_CONFIGURED = False


def setup_logging(name: str = "vaybooks.bms", level: int = logging.INFO) -> logging.Logger:
    global _CONFIGURED
    logger = logging.getLogger(name)
    if _CONFIGURED:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if is_desktop():
        logs_dir = get_logs_dir()
        if logs_dir:
            logs_dir.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                logs_dir / "app.log",
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logging.getLogger("pymongo").setLevel(logging.WARNING)
    _CONFIGURED = True
    return logger


def get_log_file_paths() -> list[Path]:
    logs_dir = get_logs_dir()
    if not logs_dir or not logs_dir.exists():
        return []
    return sorted(logs_dir.glob("*.log"))


def tail_log_file(path: Path, max_lines: int = 200, level_filter: str | None = None) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if level_filter:
        level_filter = level_filter.upper()
        lines = [line for line in lines if f"[{level_filter}]" in line]
    return lines[-max_lines:]
