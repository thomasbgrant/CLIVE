"""
Session finder — locates chat sessions by ID, latest, or lists all available.
"""
import os
import json
import glob
from datetime import datetime, timezone

from config import WORKSPACE_STORAGE_ROOT, DATETIME_FORMAT


def _get_workspace_dirs(workspace_id: str | None = None) -> list[str]:
    """Return workspace directory paths to search."""
    if workspace_id:
        path = os.path.join(WORKSPACE_STORAGE_ROOT, workspace_id)
        if os.path.isdir(path):
            return [path]
        return []
    # All workspace directories
    if not os.path.isdir(WORKSPACE_STORAGE_ROOT):
        return []
    return [
        os.path.join(WORKSPACE_STORAGE_ROOT, d)
        for d in os.listdir(WORKSPACE_STORAGE_ROOT)
        if os.path.isdir(os.path.join(WORKSPACE_STORAGE_ROOT, d))
    ]


def _get_workspace_name(workspace_dir: str) -> str:
    """Read workspace.json to get a human-readable workspace name."""
    ws_json = os.path.join(workspace_dir, "workspace.json")
    if os.path.isfile(ws_json):
        try:
            with open(ws_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            folder = data.get("folder", "")
            # Extract last path component as name
            return os.path.basename(folder.rstrip("/\\")) if folder else ""
        except (json.JSONDecodeError, OSError):
            pass
    return ""


def _find_debug_log_sessions(workspace_dir: str) -> list[dict]:
    """Find all sessions that have debug logs (main.jsonl) in a workspace."""
    debug_dir = os.path.join(workspace_dir, "GitHub.copilot-chat", "debug-logs")
    if not os.path.isdir(debug_dir):
        return []

    sessions = []
    workspace_id = os.path.basename(workspace_dir)

    for session_dir_name in os.listdir(debug_dir):
        session_dir = os.path.join(debug_dir, session_dir_name)
        main_jsonl = os.path.join(session_dir, "main.jsonl")
        if not os.path.isfile(main_jsonl):
            continue

        session_id = session_dir_name
        info = {
            "session_id": session_id,
            "workspace_id": workspace_id,
            "workspace_name": _get_workspace_name(workspace_dir),
            "main_jsonl_path": main_jsonl,
            "debug_log_dir": session_dir,
            "modified_time_ms": int(os.path.getmtime(main_jsonl) * 1000),
            "title": "",
            "model": "",
            "created_at_ms": 0,
            "created_at": "",
        }

        # Try to get title/model/date from session state
        _enrich_session_info(info, workspace_dir, session_id)

        sessions.append(info)

    return sessions


def _enrich_session_info(info: dict, workspace_dir: str, session_id: str):
    """Try to read session metadata from chatSessions or chatEditingSessions."""
    # Try chatEditingSessions/state.json first (consolidated)
    state_json = os.path.join(
        workspace_dir, "chatEditingSessions", session_id, "state.json"
    )
    if os.path.isfile(state_json):
        try:
            with open(state_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            _extract_state_fields(info, data)
            return
        except (json.JSONDecodeError, OSError):
            pass

    # Try chatSessions/{sessionId}.jsonl
    session_jsonl = os.path.join(workspace_dir, "chatSessions", f"{session_id}.jsonl")
    if os.path.isfile(session_jsonl):
        try:
            with open(session_jsonl, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        _extract_state_fields(info, data)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass

    # Fallback: read first few lines of main.jsonl for session_start
    if not info["created_at_ms"]:
        try:
            with open(info["main_jsonl_path"], "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i > 20:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        if event.get("type") == "session_start":
                            info["created_at_ms"] = event.get("ts", 0)
                            ts = info["created_at_ms"]
                            if ts:
                                dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                                info["created_at"] = dt.strftime(DATETIME_FORMAT)
                            break
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass


def _extract_state_fields(info: dict, data: dict):
    """Extract title, model, creation date from a session state dict."""
    if "customTitle" in data and data["customTitle"]:
        info["title"] = data["customTitle"]
    if "creationDate" in data and data["creationDate"]:
        info["created_at_ms"] = data["creationDate"]
        dt = datetime.fromtimestamp(data["creationDate"] / 1000, tz=timezone.utc)
        info["created_at"] = dt.strftime(DATETIME_FORMAT)
    # Get model from first request or inputState
    if "requests" in data and data["requests"]:
        first_req = data["requests"][0] if isinstance(data["requests"], list) else None
        if first_req and "modelId" in first_req:
            info["model"] = first_req["modelId"]
    if not info["model"] and "inputState" in data:
        sel = data["inputState"].get("selectedModel", {})
        if sel:
            info["model"] = sel.get("id", "")


def list_sessions(workspace_id: str | None = None) -> list[dict]:
    """
    List all available chat sessions with debug logs.

    Args:
        workspace_id: Optional workspace UUID to scope the search.

    Returns:
        List of session info dicts sorted by creation date (newest first).
    """
    all_sessions = []
    for ws_dir in _get_workspace_dirs(workspace_id):
        all_sessions.extend(_find_debug_log_sessions(ws_dir))

    # Sort by creation date (newest first), fall back to modified time
    all_sessions.sort(
        key=lambda s: s.get("created_at_ms") or s.get("modified_time_ms", 0),
        reverse=True,
    )
    return all_sessions


def find_session(session_id: str, workspace_id: str | None = None) -> dict | None:
    """
    Find a specific session by its ID.

    Args:
        session_id: The session UUID to find.
        workspace_id: Optional workspace UUID to narrow the search.

    Returns:
        Session info dict, or None if not found.
    """
    for ws_dir in _get_workspace_dirs(workspace_id):
        debug_dir = os.path.join(
            ws_dir, "GitHub.copilot-chat", "debug-logs", session_id
        )
        main_jsonl = os.path.join(debug_dir, "main.jsonl")
        if os.path.isfile(main_jsonl):
            ws_id = os.path.basename(ws_dir)
            info = {
                "session_id": session_id,
                "workspace_id": ws_id,
                "workspace_name": _get_workspace_name(ws_dir),
                "main_jsonl_path": main_jsonl,
                "debug_log_dir": debug_dir,
                "modified_time_ms": int(os.path.getmtime(main_jsonl) * 1000),
                "title": "",
                "model": "",
                "created_at_ms": 0,
                "created_at": "",
            }
            _enrich_session_info(info, ws_dir, session_id)
            return info
    return None


def find_latest_session(workspace_id: str | None = None) -> dict | None:
    """
    Find the most recent chat session.

    Args:
        workspace_id: Optional workspace UUID to scope the search.

    Returns:
        Session info dict for the latest session, or None.
    """
    sessions = list_sessions(workspace_id)
    return sessions[0] if sessions else None
