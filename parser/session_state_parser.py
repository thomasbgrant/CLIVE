"""
Session state parser — reads chatSessions/*.jsonl and chatEditingSessions/state.json
to extract session metadata, user messages, file attachments, and model info.
"""
import json
import os


def parse_session_state(workspace_dir: str, session_id: str) -> dict:
    """
    Parse session state to extract metadata, messages, and attachments.

    Tries chatEditingSessions/state.json first, then chatSessions/{id}.jsonl.

    Returns:
        Dict with keys: title, created_at_ms, model, requests, attachments, etc.
    """
    # Try consolidated state.json
    state_json = os.path.join(
        workspace_dir, "chatEditingSessions", session_id, "state.json"
    )
    if os.path.isfile(state_json):
        try:
            with open(state_json, "r", encoding="utf-8") as f:
                return _normalize_state(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass

    # Try chatSessions JSONL (incremental updates — take the last complete state)
    session_jsonl = os.path.join(workspace_dir, "chatSessions", f"{session_id}.jsonl")
    if os.path.isfile(session_jsonl):
        return _parse_session_jsonl(session_jsonl)

    return _empty_state()


def _parse_session_jsonl(filepath: str) -> dict:
    """
    Parse chatSessions/*.jsonl which uses incremental key-value log format.
    Each line is a JSON object that may update parts of the session state.
    We merge them all to reconstruct the final state.
    """
    merged = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if isinstance(data, dict):
                        _deep_merge(merged, data)
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass

    return _normalize_state(merged)


def _deep_merge(base: dict, update: dict):
    """Merge update into base, overwriting scalar values and merging dicts."""
    for key, value in update.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _normalize_state(data: dict) -> dict:
    """Normalize session state into a consistent structure."""
    state = _empty_state()

    state["title"] = data.get("customTitle", "")
    state["created_at_ms"] = data.get("creationDate", 0)
    state["session_id"] = data.get("sessionId", "")

    # Requests
    requests = data.get("requests", [])
    if isinstance(requests, list):
        state["requests"] = requests

    # Model from first request
    if state["requests"]:
        first_req = state["requests"][0]
        state["model"] = first_req.get("modelId", "")

    # Input state
    input_state = data.get("inputState", {})
    if isinstance(input_state, dict):
        # Attachments
        attachments = input_state.get("attachments", [])
        if isinstance(attachments, list):
            state["attachments"] = attachments

        # Selected model (fallback)
        if not state["model"]:
            sel_model = input_state.get("selectedModel", {})
            if isinstance(sel_model, dict):
                state["model"] = sel_model.get("id", "")

    return state


def _empty_state() -> dict:
    """Return an empty session state structure."""
    return {
        "title": "",
        "created_at_ms": 0,
        "session_id": "",
        "model": "",
        "requests": [],
        "attachments": [],
    }


def extract_context_files(state: dict) -> list[str]:
    """
    Extract file paths from session attachments.

    Returns:
        List of file paths (strings) attached to the session input.
    """
    files = []
    for att in state.get("attachments", []):
        if not isinstance(att, dict):
            continue
        kind = att.get("kind", "")
        if kind == "file":
            value = att.get("value", {})
            if isinstance(value, dict):
                fs_path = value.get("fsPath", "")
                if fs_path:
                    files.append(fs_path)
            elif isinstance(value, str):
                files.append(value)
        # Also capture the name if no path
        elif "name" in att and att["name"]:
            files.append(att["name"])
    return files


def extract_user_messages(state: dict) -> list[dict]:
    """
    Extract user messages from session requests.

    Returns:
        List of dicts with keys: request_id, timestamp, text, model
    """
    messages = []
    for req in state.get("requests", []):
        if not isinstance(req, dict):
            continue
        msg = req.get("message", {})
        text = ""
        if isinstance(msg, dict):
            text = msg.get("text", "")
        elif isinstance(msg, str):
            text = msg

        messages.append({
            "request_id": req.get("requestId", ""),
            "timestamp": req.get("timestamp", 0),
            "text": text,
            "model": req.get("modelId", ""),
        })
    return messages
