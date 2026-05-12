"""
Aggregator — computes session-level summaries from extracted turn data.
"""
from collections import Counter

from parser.models import AnalyzedSession, SessionSummary


def compute_summary(session: AnalyzedSession) -> AnalyzedSession:
    """
    Compute aggregated summary metrics and attach to the session.

    Args:
        session: AnalyzedSession with turns already populated.

    Returns:
        The same session object with summary filled in.
    """
    summary = SessionSummary()
    summary.total_turns = len(session.turns)

    # Tool call counts
    tool_counter = Counter()
    total_tool_calls = 0
    for turn in session.turns:
        for tc in turn.tool_calls:
            tool_counter[tc.name] += 1
            total_tool_calls += 1

    summary.total_tool_calls = total_tool_calls
    summary.tool_call_counts = dict(tool_counter.most_common())

    # Token totals
    summary.total_input_tokens = sum(t.input_tokens for t in session.turns)
    summary.total_output_tokens = sum(t.output_tokens for t in session.turns)
    summary.total_tokens = summary.total_input_tokens + summary.total_output_tokens

    # Duration
    if session.turns:
        first_start = min(t.start_ts for t in session.turns if t.start_ts)
        last_end = max(t.end_ts for t in session.turns if t.end_ts)
        if first_start and last_end:
            summary.total_duration_ms = last_end - first_start
            summary.total_duration_sec = summary.total_duration_ms / 1000.0

    # Average TTFT
    ttfts = [t.ttft_ms for t in session.turns if t.ttft_ms > 0]
    if ttfts:
        summary.average_ttft_ms = sum(ttfts) / len(ttfts)

    session.summary = summary
    return session
