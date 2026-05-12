"""
Single-session visualizations using matplotlib.
"""
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.ticker import MaxNLocator

from parser.models import AnalyzedSession
from config import RESULTS_DIR


# Consistent color palette
COLORS = {
    "input_tokens": "#4C72B0",
    "output_tokens": "#DD8452",
    "ttft": "#55A868",
    "tool_duration": "#C44E52",
    "turn_duration": "#8172B3",
    "tool_call": "#937860",
    "similarity": "#D65F5F",
}


def _ensure_results_dir():
    os.makedirs(RESULTS_DIR, exist_ok=True)


def _session_label(session: AnalyzedSession) -> str:
    sid = session.metadata.session_id[:8]
    title = session.metadata.title or "Untitled"
    return f"{title} ({sid})"


def plot_token_usage(session: AnalyzedSession, save: bool = True, show: bool = False):
    """Stacked bar chart of input vs output tokens per turn."""
    if not session.turns:
        return

    turns = session.turns
    x = np.arange(len(turns))
    input_tokens = [t.input_tokens for t in turns]
    output_tokens = [t.output_tokens for t in turns]

    fig, ax = plt.subplots(figsize=(max(8, len(turns) * 1.2), 5))
    ax.bar(x, input_tokens, label="Input Tokens", color=COLORS["input_tokens"])
    ax.bar(x, output_tokens, bottom=input_tokens, label="Output Tokens",
           color=COLORS["output_tokens"])

    ax.set_xlabel("Turn")
    ax.set_ylabel("Tokens")
    ax.set_title(f"Token Usage per Turn — {_session_label(session)}")
    ax.set_xticks(x)
    ax.set_xticklabels([f"Turn {t.turn_number}" for t in turns], rotation=45, ha="right")
    ax.legend()
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    plt.tight_layout()

    if save:
        _ensure_results_dir()
        path = os.path.join(
            RESULTS_DIR,
            f"{session.metadata.session_id[:8]}_token_usage.png"
        )
        fig.savefig(path, dpi=150)
        print(f"Saved: {path}")

    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_tool_call_summary(session: AnalyzedSession, save: bool = True, show: bool = False):
    """Bar chart of tool call frequency."""
    if not session.summary.tool_call_counts:
        return

    tools = list(session.summary.tool_call_counts.keys())
    counts = list(session.summary.tool_call_counts.values())

    fig, ax = plt.subplots(figsize=(max(8, len(tools) * 0.8), 5))
    bars = ax.barh(tools, counts, color=COLORS["tool_call"])
    ax.set_xlabel("Number of Calls")
    ax.set_title(f"Tool Call Frequency — {_session_label(session)}")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))

    # Add count labels on bars
    for bar, count in zip(bars, counts):
        ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                str(count), va="center", fontsize=9)

    plt.tight_layout()

    if save:
        _ensure_results_dir()
        path = os.path.join(
            RESULTS_DIR,
            f"{session.metadata.session_id[:8]}_tool_frequency.png"
        )
        fig.savefig(path, dpi=150)
        print(f"Saved: {path}")

    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_tool_call_sequence(session: AnalyzedSession, save: bool = True, show: bool = False):
    """Gantt-style chart showing tool calls in execution order with durations."""
    # Collect all tool calls across turns with absolute timestamps
    all_calls = []
    for turn in session.turns:
        for tc in turn.tool_calls:
            all_calls.append(tc)

    if not all_calls:
        return

    # Use first event timestamp as reference
    ref_ts = min(tc.timestamp_ms for tc in all_calls if tc.timestamp_ms > 0)
    if ref_ts == 0 and all_calls:
        ref_ts = all_calls[0].timestamp_ms

    fig, ax = plt.subplots(figsize=(12, max(4, len(all_calls) * 0.4)))

    y_labels = []
    for i, tc in enumerate(all_calls):
        start = (tc.timestamp_ms - ref_ts) / 1000.0  # seconds from start
        dur = max(tc.duration_ms / 1000.0, 0.05)  # min width for visibility
        color = COLORS["tool_call"] if tc.status == "ok" else COLORS["tool_duration"]
        ax.barh(i, dur, left=start, height=0.6, color=color, alpha=0.8)
        y_labels.append(f"{tc.name}")

    ax.set_yticks(range(len(y_labels)))
    ax.set_yticklabels(y_labels, fontsize=8)
    ax.set_xlabel("Time (seconds from session start)")
    ax.set_title(f"Tool Call Sequence — {_session_label(session)}")
    ax.invert_yaxis()
    plt.tight_layout()

    if save:
        _ensure_results_dir()
        path = os.path.join(
            RESULTS_DIR,
            f"{session.metadata.session_id[:8]}_tool_sequence.png"
        )
        fig.savefig(path, dpi=150)
        print(f"Saved: {path}")

    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_timing_breakdown(session: AnalyzedSession, save: bool = True, show: bool = False):
    """Per-turn breakdown showing TTFT, tool execution time, and total turn time."""
    if not session.turns:
        return

    turns = session.turns
    x = np.arange(len(turns))

    ttfts = [t.ttft_ms / 1000.0 for t in turns]
    tool_times = [
        sum(tc.duration_ms for tc in t.tool_calls) / 1000.0 for t in turns
    ]
    total_times = [t.total_duration_ms / 1000.0 for t in turns]

    fig, ax = plt.subplots(figsize=(max(8, len(turns) * 1.5), 5))
    width = 0.25

    ax.bar(x - width, ttfts, width, label="TTFT", color=COLORS["ttft"])
    ax.bar(x, tool_times, width, label="Tool Execution", color=COLORS["tool_duration"])
    ax.bar(x + width, total_times, width, label="Total Turn", color=COLORS["turn_duration"])

    ax.set_xlabel("Turn")
    ax.set_ylabel("Time (seconds)")
    ax.set_title(f"Timing Breakdown — {_session_label(session)}")
    ax.set_xticks(x)
    ax.set_xticklabels([f"Turn {t.turn_number}" for t in turns])
    ax.legend()
    plt.tight_layout()

    if save:
        _ensure_results_dir()
        path = os.path.join(
            RESULTS_DIR,
            f"{session.metadata.session_id[:8]}_timing.png"
        )
        fig.savefig(path, dpi=150)
        print(f"Saved: {path}")

    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_turn_timeline(session: AnalyzedSession, save: bool = True, show: bool = False):
    """
    Horizontal timeline showing all events (tool calls, LLM requests) with
    duration bars. Shows sequence and parallelism.
    """
    # Gather all timed events
    all_events = []
    for turn in session.turns:
        for tc in turn.tool_calls:
            all_events.append({
                "label": f"[Tool] {tc.name}",
                "start_ms": tc.timestamp_ms,
                "dur_ms": tc.duration_ms,
                "type": "tool",
                "turn": turn.turn_number,
            })
        for lr in turn.llm_requests:
            all_events.append({
                "label": f"[LLM] {lr.model}",
                "start_ms": lr.timestamp_ms,
                "dur_ms": lr.duration_ms,
                "type": "llm",
                "turn": turn.turn_number,
            })

    if not all_events:
        return

    ref_ts = min(e["start_ms"] for e in all_events if e["start_ms"] > 0)

    fig, ax = plt.subplots(figsize=(14, max(4, len(all_events) * 0.35)))

    colors = {"tool": COLORS["tool_call"], "llm": COLORS["input_tokens"]}
    y_labels = []

    for i, ev in enumerate(all_events):
        start_sec = (ev["start_ms"] - ref_ts) / 1000.0
        dur_sec = max(ev["dur_ms"] / 1000.0, 0.05)
        ax.barh(i, dur_sec, left=start_sec, height=0.6,
                color=colors.get(ev["type"], "#999999"), alpha=0.8)
        y_labels.append(f"T{ev['turn']}: {ev['label']}")

    ax.set_yticks(range(len(y_labels)))
    ax.set_yticklabels(y_labels, fontsize=7)
    ax.set_xlabel("Time (seconds from session start)")
    ax.set_title(f"Event Timeline — {_session_label(session)}")
    ax.invert_yaxis()

    # Legend
    tool_patch = mpatches.Patch(color=colors["tool"], label="Tool Call")
    llm_patch = mpatches.Patch(color=colors["llm"], label="LLM Request")
    ax.legend(handles=[tool_patch, llm_patch], loc="lower right")

    plt.tight_layout()

    if save:
        _ensure_results_dir()
        path = os.path.join(
            RESULTS_DIR,
            f"{session.metadata.session_id[:8]}_timeline.png"
        )
        fig.savefig(path, dpi=150)
        print(f"Saved: {path}")

    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_all(session: AnalyzedSession, save: bool = True, show: bool = False):
    """Generate all single-session visualizations."""
    plot_token_usage(session, save=save, show=show)
    plot_tool_call_summary(session, save=save, show=show)
    plot_tool_call_sequence(session, save=save, show=show)
    plot_timing_breakdown(session, save=save, show=show)
    plot_turn_timeline(session, save=save, show=show)
    plot_context_similarity(session, save=save, show=show)


def plot_context_similarity(
    session: AnalyzedSession, save: bool = True, show: bool = False
):
    """
    Line chart of context-vs-prompt similarity score at each turn.
    Shows how relevant the retrieved context is to the user's request.

    Higher score = more vocabulary overlap between prompt and context.
    Low scores may indicate the agent is reading irrelevant files.
    """
    if not session.turns:
        return

    turns = session.turns
    x = [t.turn_number for t in turns]
    scores = [t.context_similarity for t in turns]

    # Skip if all zeros (no context was retrieved)
    if all(s == 0.0 for s in scores):
        return

    fig, ax = plt.subplots(figsize=(max(8, len(turns) * 1.2), 5))

    ax.plot(x, scores, "o-", color=COLORS["similarity"], linewidth=2, markersize=8)

    # Annotate each point with the score
    for xi, score in zip(x, scores):
        ax.annotate(
            f"{score:.3f}",
            (xi, score),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
            fontsize=9,
        )

    ax.set_xlabel("Turn Number")
    ax.set_ylabel("Jaccard Similarity")
    ax.set_title(f"Context–Prompt Similarity per Turn — {_session_label(session)}")
    ax.set_ylim(-0.05, max(max(scores) * 1.2, 0.15))
    ax.set_xticks(x)
    ax.set_xticklabels([f"Turn {t}" for t in x])
    ax.axhline(y=0, color="grey", linewidth=0.5, linestyle="--")
    ax.grid(True, alpha=0.3)

    # Add interpretation guide
    ax.text(
        0.98, 0.02,
        "Higher = more prompt–context overlap\nLow = potentially noisy context",
        transform=ax.transAxes,
        fontsize=8,
        va="bottom",
        ha="right",
        style="italic",
        color="grey",
    )

    plt.tight_layout()

    if save:
        _ensure_results_dir()
        path = os.path.join(
            RESULTS_DIR,
            f"{session.metadata.session_id[:8]}_context_similarity.png",
        )
        fig.savefig(path, dpi=150)
        print(f"Saved: {path}")

    if show:
        plt.show()
    else:
        plt.close(fig)
