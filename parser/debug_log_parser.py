"""
Debug log parser — parses main.jsonl event streams into structured data.
"""
import json
import os
from typing import Generator

from config import TOOL_RESULT_MAX_LENGTH


def parse_jsonl(filepath: str) -> Generator[dict, None, None]:
    """
    Parse a JSONL file line by line, yielding valid JSON objects.
    Skips malformed lines with a warning printed to stderr.
    """
    if not os.path.isfile(filepath):
        return

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                import sys
                print(
                    f"WARNING: Skipping malformed JSON at {filepath}:{line_num}",
                    file=sys.stderr,
                )


def parse_debug_log(main_jsonl_path: str) -> list[dict]:
    """
    Parse the main.jsonl debug log into a list of event dicts.

    Args:
        main_jsonl_path: Absolute path to the main.jsonl file.

    Returns:
        List of event dicts, sorted by timestamp.
    """
    events = list(parse_jsonl(main_jsonl_path))
    events.sort(key=lambda e: e.get("ts", 0))
    return events


def extract_events_by_type(events: list[dict], event_type: str) -> list[dict]:
    """Filter events by their 'type' field."""
    return [e for e in events if e.get("type") == event_type]


def parse_tool_call_args(args_str: str) -> dict:
    """
    Parse tool call arguments from JSON string.
    Handles the double-encoded JSON strings found in debug logs.
    """
    if not args_str:
        return {}
    try:
        parsed = json.loads(args_str)
        if isinstance(parsed, dict):
            return parsed
        return {"raw": parsed}
    except (json.JSONDecodeError, TypeError):
        return {"raw": str(args_str)}


def truncate_result(result: str, max_length: int = TOOL_RESULT_MAX_LENGTH) -> str:
    """Truncate a tool result string to max_length characters."""
    if not result:
        return ""
    if len(result) <= max_length:
        return result
    return result[:max_length] + f"... [truncated, {len(result)} chars total]"


def load_models_config(debug_log_dir: str) -> list[dict]:
    """Load models.json from the session's debug log directory."""
    path = os.path.join(debug_log_dir, "models.json")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def load_system_prompt(debug_log_dir: str) -> str:
    """Load system_prompt_0.json content."""
    path = os.path.join(debug_log_dir, "system_prompt_0.json")
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("content", "")
    except (json.JSONDecodeError, OSError):
        return ""


def load_tools_config(debug_log_dir: str) -> list[dict]:
    """Load tools_0.json — the tool definitions available to the agent."""
    path = os.path.join(debug_log_dir, "tools_0.json")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []
