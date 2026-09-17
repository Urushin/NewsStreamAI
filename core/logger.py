"""
NewsStreamAI — Structured Logger
"""
import sys
from datetime import datetime

class Logger:
    @staticmethod
    def _log(level: str, prefix: str, msg: str):
        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{now}] [{level}] {prefix} {msg}", file=sys.stdout, flush=True)

    @classmethod
    def debug(cls, msg: str):
        pass

    @classmethod
    def info(cls, msg: str):
        cls._log("INFO", "🔹", msg)

    @classmethod
    def success(cls, msg: str):
        cls._log("OK", "✅", msg)

    @classmethod
    def warning(cls, msg: str):
        cls._log("WARN", "⚠️", msg)

    @classmethod
    def error(cls, msg: str):
        cls._log("ERROR", "❌", msg)

    @classmethod
    def alert(cls, msg: str):
        cls._log("ALERT", "🚨", msg)

logger = Logger()
