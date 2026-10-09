"""Reading configuration from the environment (and a local `.env` file)."""

import os
from pathlib import Path


def load_dotenv(path: Path) -> None:
    """Put `KEY=value` lines of a file into the environment; real variables win."""
    if not path.exists() or os.environ.get("DJANGO_READ_DOT_ENV", "true").lower() == "false":
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def text(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    return default if value is None or value == "" else value.lower() in ("1", "true", "yes", "on")


def number(name: str, default: int) -> int:
    return int(os.environ.get(name) or default)


def items(name: str, default: str = "") -> list[str]:
    """A comma-separated list."""
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def rate(name: str, default: str) -> str | None:
    """A throttle rate such as `30/min`; an empty value switches the limit off."""
    return os.environ.get(name, default) or None
