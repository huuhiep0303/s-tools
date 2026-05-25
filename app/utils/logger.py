import json
import logging
import sys
from datetime import datetime
from typing import Any

# Log level ordering
_LEVELS = ["DEBUG", "INFO", "WARN", "ERROR"]

def _level_rank(level: str) -> int:
    return _LEVELS.index(level) if level in _LEVELS else 1


class Logger:
    def __init__(self, min_level: str = "INFO"):
        self.min_level = min_level

    def _should_log(self, level: str) -> bool:
        return _level_rank(level) >= _level_rank(self.min_level)

    def _write(self, level: str, component: str, operation: str, message: str, context: dict | None = None):
        if not self._should_log(level):
            return
        entry: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "component": component,
            "operation": operation,
            "message": message,
        }
        if context:
            # Serialise exceptions to string
            ctx = {}
            for k, v in context.items():
                if isinstance(v, Exception):
                    ctx[k] = f"{type(v).__name__}: {v}"
                else:
                    ctx[k] = v
            entry["context"] = ctx
        line = json.dumps(entry, ensure_ascii=False)
        stream = sys.stderr if level in ("ERROR", "WARN") else sys.stdout
        print(line, file=stream)

    def log_info(self, component: str, operation: str, message: str, context: dict | None = None):
        self._write("INFO", component, operation, message, context)

    def log_warn(self, component: str, operation: str, message: str, context: dict | None = None):
        self._write("WARN", component, operation, message, context)

    def log_error(self, component: str, operation: str, message: str, context: dict | None = None):
        self._write("ERROR", component, operation, message, context)

    def log_debug(self, component: str, operation: str, message: str, context: dict | None = None):
        self._write("DEBUG", component, operation, message, context)


import os
logger = Logger(min_level=os.getenv("LOG_LEVEL", "INFO"))
