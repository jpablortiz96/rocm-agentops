"""Optional log collector for AMD live signal intake."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def collect_logs(log_paths: list[str], max_lines: int = 400) -> Dict[str, Any]:
    """Read configured log files if present."""
    if not log_paths:
        return {"available": False, "reason": "No log paths configured", "entries": []}

    entries: list[dict[str, str]] = []
    missing_paths: list[str] = []
    for raw_path in log_paths:
        path = Path(raw_path).expanduser()
        if not path.exists():
            missing_paths.append(str(path))
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            tail = lines[-max_lines:]
            entries.append({"path": str(path), "content": "\n".join(tail)})
        except OSError:
            missing_paths.append(str(path))

    if not entries:
        return {
            "available": False,
            "reason": "Configured logs were not readable",
            "entries": [],
            "missing_paths": missing_paths,
        }

    return {"available": True, "entries": entries, "missing_paths": missing_paths}
