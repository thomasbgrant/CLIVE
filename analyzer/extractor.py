"""
Extractor — builds structured Turn and ToolCall objects from raw parsed events.
"""
import re
from datetime import datetime, timezone

from config import WORKSPACE_STORAGE_ROOT, TOOL_RESULT_MAX_LENGTH
from parser.models import (
    ToolCall, LLMRequest, Turn, SessionMetadata, AnalyzedSession,
)
from parser.debug_log_parser import (
    parse_debug_log, extract_events_by_type,
    parse_tool_call_args, truncate_result,
)
from parser.session_state_parser import (
    parse_session_state, extract_context_files, extract_user_messages,
)
from analyzer.similarity import compute_jaccard_similarity

import os


def extract_session(session_info: dict) -> AnalyzedSession:
    """
    Full extraction pipeline: parse all data sources for a session and
    build an AnalyzedSession object.

    Args:
        session_info: Dict from session_finder (has paths, IDs, etc.)

    Returns:
        Fully populated AnalyzedSession.
    """
    session_id = session_info["session_id"]
    workspace_id = session_info["workspace_id"]
    workspace_dir = os.path.join(WORKSPACE_STORAGE_ROOT, workspace_id)
    main_jsonl_path = session_info["main_jsonl_path"]
    debug_log_dir = session_info["debug_log_dir"]

    # 1. Parse debug log events
    events = parse_debug_log(main_jsonl_path)

    # 2. Parse session state (for context files, user messages, title)
    state = parse_session_state(workspace_dir, session_id)
    context_files = extract_context_files(state)
    user_messages = extract_user_messages(state)

    # 3. Build metadata
    metadata = _build_metadata(events, session_info, state)

    # 4. Build turns from events
    turns = _build_turns(events, user_messages, context_files)

    # 5. Assemble
    session = AnalyzedSession(metadata=metadata, turns=turns)
    return session


def _build_metadata(
    events: list[dict], session_info: dict, state: dict
) -> SessionMetadata:
    """Build SessionMetadata from all available sources."""
    meta = SessionMetadata()
    meta.session_id = session_info["session_id"]
    meta.workspace_id = session_info["workspace_id"]
    meta.title = session_info.get("title", "") or state.get("title", "")
    meta.model = session_info.get("model", "") or state.get("model", "")

    # From session_start event
    start_events = extract_events_by_type(events, "session_start")
    if start_events:
        attrs = start_events[0].get("attrs", {})
        meta.copilot_version = attrs.get("copilotVersion", "")
        meta.vscode_version = attrs.get("vscodeVersion", "")
        if not meta.model:
            meta.model = attrs.get("model", "")

    # Creation date
    created_ms = session_info.get("created_at_ms", 0) or state.get("created_at_ms", 0)
    if not created_ms and events:
        created_ms = events[0].get("ts", 0)
    meta.created_at_ms = created_ms
    if created_ms:
        dt = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
        meta.created_at = dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    return meta


def _build_turns(
    events: list[dict],
    user_messages: list[dict],
    context_files: list[str],
) -> list[Turn]:
    """
    Build Turn objects by segmenting events between turn_start/turn_end boundaries.
    Falls back to grouping by user_message events if turn markers are absent.
    """
    # Find turn boundaries
    turn_starts = extract_events_by_type(events, "turn_start")
    turn_ends = extract_events_by_type(events, "turn_end")

    if turn_starts:
        return _build_turns_from_boundaries(
            events, turn_starts, turn_ends, user_messages, context_files
        )
    else:
        # No explicit turn markers — treat the whole session as one turn
        return _build_turns_fallback(events, user_messages, context_files)


def _build_turns_from_boundaries(
    events: list[dict],
    turn_starts: list[dict],
    turn_ends: list[dict],
    user_messages: list[dict],
    context_files: list[str],
) -> list[Turn]:
    """Build turns using turn_start/turn_end event boundaries."""
    # Map turn_end by turnId for lookup
    end_map = {}
    for te in turn_ends:
        tid = te.get("attrs", {}).get("turnId", te.get("name", "").split(":")[-1])
        end_map[tid] = te

    turns = []
    for i, ts_event in enumerate(turn_starts):
        turn_id = ts_event.get("attrs", {}).get(
            "turnId", ts_event.get("name", "").split(":")[-1]
        )
        start_ts = ts_event.get("ts", 0)

        te_event = end_map.get(turn_id)
        end_ts = te_event.get("ts", 0) if te_event else 0

        # If no end marker, use the start of next turn or last event
        if not end_ts:
            if i + 1 < len(turn_starts):
                end_ts = turn_starts[i + 1].get("ts", 0)
            elif events:
                last = events[-1]
                end_ts = last.get("ts", 0) + last.get("dur", 0)

        # Collect events within this turn's time range
        turn_events = [
            e for e in events
            if start_ts <= e.get("ts", 0) <= end_ts
            and e.get("type") not in ("turn_start", "turn_end")
        ]

        turn = _build_single_turn(
            turn_number=i + 1,
            turn_events=turn_events,
            user_messages=user_messages,
            context_files=context_files,
            turn_index=i,
            start_ts=start_ts,
            end_ts=end_ts,
        )
        turns.append(turn)

    return turns


def _build_turns_fallback(
    events: list[dict],
    user_messages: list[dict],
    context_files: list[str],
) -> list[Turn]:
    """Fallback: treat entire event list as a single turn."""
    if not events:
        return []

    start_ts = events[0].get("ts", 0)
    last = events[-1]
    end_ts = last.get("ts", 0) + last.get("dur", 0)

    non_meta = [
        e for e in events
        if e.get("type") not in ("session_start", "turn_start", "turn_end")
    ]

    turn = _build_single_turn(
        turn_number=1,
        turn_events=non_meta,
        user_messages=user_messages,
        context_files=context_files,
        turn_index=0,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    return [turn]


def _build_single_turn(
    turn_number: int,
    turn_events: list[dict],
    user_messages: list[dict],
    context_files: list[str],
    turn_index: int,
    start_ts: int,
    end_ts: int,
) -> Turn:
    """Construct a Turn object from a set of events belonging to one turn."""
    turn = Turn(turn_number=turn_number, start_ts=start_ts, end_ts=end_ts)
    turn.total_duration_ms = end_ts - start_ts if end_ts > start_ts else 0

    # User prompt
    user_msg_events = [e for e in turn_events if e.get("type") == "user_message"]
    if user_msg_events:
        turn.user_prompt = user_msg_events[0].get("attrs", {}).get("content", "")
    elif turn_index < len(user_messages):
        turn.user_prompt = user_messages[turn_index].get("text", "")

    # Context files (shared across turns for now — from session state)
    turn.context_files = context_files

    # Tool calls
    tool_events = [e for e in turn_events if e.get("type") == "tool_call"]
    for te in tool_events:
        attrs = te.get("attrs", {})
        args = parse_tool_call_args(attrs.get("args", ""))
        result = truncate_result(attrs.get("result", ""))
        tc = ToolCall(
            name=te.get("name", "unknown"),
            args=args,
            result_summary=result,
            duration_ms=te.get("dur", 0),
            status=te.get("status", "ok"),
            span_id=te.get("spanId", ""),
            parent_span_id=te.get("parentSpanId", ""),
            timestamp_ms=te.get("ts", 0),
        )
        turn.tool_calls.append(tc)

    # ----- Files accessed (extracted from tool call arguments) -----
    turn.files_accessed = _extract_files_accessed(turn.tool_calls)

    # ----- Context text (aggregated tool results = what the agent actually read) -----
    context_parts = []
    for tc in turn.tool_calls:
        if tc.result_summary and tc.status == "ok":
            context_parts.append(tc.result_summary)
    turn.context_text = "\n".join(context_parts)

    # ----- Context–prompt similarity -----
    if turn.user_prompt and turn.context_text:
        turn.context_similarity = compute_jaccard_similarity(
            turn.user_prompt, turn.context_text
        )

    # LLM requests
    llm_events = [e for e in turn_events if e.get("type") == "llm_request"]
    for le in llm_events:
        attrs = le.get("attrs", {})
        lr = LLMRequest(
            model=attrs.get("model", ""),
            input_tokens=attrs.get("inputTokens", 0),
            output_tokens=attrs.get("outputTokens", 0),
            ttft_ms=attrs.get("ttft", 0),
            duration_ms=le.get("dur", 0),
            max_tokens=attrs.get("maxTokens", 0),
            temperature=attrs.get("temperature", 0.0),
            span_id=le.get("spanId", ""),
            timestamp_ms=le.get("ts", 0),
        )
        turn.llm_requests.append(lr)

    # Aggregate token counts for the turn
    turn.input_tokens = sum(lr.input_tokens for lr in turn.llm_requests)
    turn.output_tokens = sum(lr.output_tokens for lr in turn.llm_requests)
    turn.total_tokens = turn.input_tokens + turn.output_tokens

    # TTFT: use the first LLM request's TTFT
    if turn.llm_requests:
        turn.ttft_ms = turn.llm_requests[0].ttft_ms

    return turn


# Tools that access files — map tool name to the arg key containing the file path
_FILE_ACCESS_TOOLS = {
    "read_file": "filePath",
    "file_search": "query",          # query is a glob, but captures what was searched
    "grep_search": "includePattern",  # optional — may not have a file path
    "semantic_search": "query",       # no file path, but captures the search
    "replace_string_in_file": "filePath",
    "create_file": "filePath",
    "read_notebook_cell_output": "filePath",
    "edit_notebook_file": "filePath",
    "multi_replace_string_in_file": None,  # has nested replacements
}


def _extract_files_accessed(tool_calls: list[ToolCall]) -> list[str]:
    """
    Extract file paths that were accessed/read/written during a turn,
    derived from tool call arguments.

    Returns deduplicated list preserving first-seen order.
    """
    seen = set()
    files = []

    for tc in tool_calls:
        # Direct file path argument
        arg_key = _FILE_ACCESS_TOOLS.get(tc.name)
        if arg_key and arg_key in tc.args:
            path = str(tc.args[arg_key])
            if path and path not in seen:
                seen.add(path)
                files.append(path)

        # multi_replace_string_in_file has nested replacements array
        if tc.name == "multi_replace_string_in_file":
            for repl in tc.args.get("replacements", []):
                if isinstance(repl, dict):
                    path = repl.get("filePath", "")
                    if path and path not in seen:
                        seen.add(path)
                        files.append(path)

        # grep_search may also have an includePattern that's a file path
        if tc.name == "grep_search" and "includePattern" not in tc.args:
            # Still record the query as context about what was searched
            query = tc.args.get("query", "")
            if query:
                entry = f"[grep: {query}]"
                if entry not in seen:
                    seen.add(entry)
                    files.append(entry)

        # semantic_search records the query
        if tc.name == "semantic_search":
            query = tc.args.get("query", "")
            if query:
                entry = f"[search: {query}]"
                if entry not in seen:
                    seen.add(entry)
                    files.append(entry)

    return files

    return turn
