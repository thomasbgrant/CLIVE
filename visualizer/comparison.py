"""
Multi-session comparison visualizations using matplotlib.
"""
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from collections import OrderedDict

from parser.models import AnalyzedSession
from config import RESULTS_DIR


def _ensure_results_dir():
    os.makedirs(RESULTS_DIR, exist_ok=True)


def _session_label(session: AnalyzedSession) -> str:
    sid = session.metadata.session_id[:8]
    title = session.metadata.title or "Untitled"
    if len(title) > 30:
        title = title[:27] + "..."
    return f"{title}\n({sid})"


def _short_label(session: AnalyzedSession) -> str:
    sid = session.metadata.session_id[:8]
    title = session.metadata.title or "Untitled"
    if len(title) > 20:
        title = title[:17] + "..."
    return f"{title} ({sid})"


def compare_metrics_table(sessions: list[AnalyzedSession]):
    """Print a side-by-side comparison table to the console."""
    if not sessions:
        print("No sessions to compare.")
        return

    header = (
        f"{'Session':<40} {'Turns':>6} {'Tools':>6} "
        f"{'In Tok':>8} {'Out Tok':>8} {'Total Tok':>10} "
        f"{'Duration':>10} {'Avg TTFT':>10}"
    )
    print("\n" + "=" * len(header))
    print("SESSION COMPARISON")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for s in sessions:
        label = f"{(s.metadata.title or 'Untitled')[:28]} ({s.metadata.session_id[:8]})"
        dur = f"{s.summary.total_duration_sec:.1f}s"
        ttft = f"{s.summary.average_ttft_ms:.0f}ms" if s.summary.average_ttft_ms else "N/A"
        print(
            f"{label:<40} {s.summary.total_turns:>6} {s.summary.total_tool_calls:>6} "
            f"{s.summary.total_input_tokens:>8} {s.summary.total_output_tokens:>8} "
            f"{s.summary.total_tokens:>10} {dur:>10} {ttft:>10}"
        )

    print("=" * len(header) + "\n")


def plot_token_comparison(
    sessions: list[AnalyzedSession], save: bool = True, show: bool = False
):
    """Grouped bar chart comparing input/output tokens across sessions."""
    if not sessions:
        return

    labels = [_session_label(s) for s in sessions]
    input_tokens = [s.summary.total_input_tokens for s in sessions]
    output_tokens = [s.summary.total_output_tokens for s in sessions]

    x = np.arange(len(sessions))
    width = 0.35

    fig, ax = plt.subplots(figsize=(max(8, len(sessions) * 2), 5))
    ax.bar(x - width / 2, input_tokens, width, label="Input Tokens", color="#4C72B0")
    ax.bar(x + width / 2, output_tokens, width, label="Output Tokens", color="#DD8452")

    ax.set_ylabel("Tokens")
    ax.set_title("Token Usage Comparison")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.legend()
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    plt.tight_layout()

    if save:
        _ensure_results_dir()
        path = os.path.join(RESULTS_DIR, "comparison_tokens.png")
        fig.savefig(path, dpi=150)
        print(f"Saved: {path}")

    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_duration_comparison(
    sessions: list[AnalyzedSession], save: bool = True, show: bool = False
):
    """Bar chart comparing total session durations."""
    if not sessions:
        return

    labels = [_session_label(s) for s in sessions]
    durations = [s.summary.total_duration_sec for s in sessions]

    fig, ax = plt.subplots(figsize=(max(8, len(sessions) * 2), 5))
    bars = ax.bar(labels, durations, color="#8172B3")

    for bar, dur in zip(bars, durations):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
            f"{dur:.1f}s", ha="center", va="bottom", fontsize=9,
        )

    ax.set_ylabel("Duration (seconds)")
    ax.set_title("Session Duration Comparison")
    plt.xticks(fontsize=8)
    plt.tight_layout()

    if save:
        _ensure_results_dir()
        path = os.path.join(RESULTS_DIR, "comparison_duration.png")
        fig.savefig(path, dpi=150)
        print(f"Saved: {path}")

    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_tool_usage_heatmap(
    sessions: list[AnalyzedSession], save: bool = True, show: bool = False
):
    """Heatmap showing which tools each session used and how many times."""
    if not sessions:
        return

    # Collect all unique tools across sessions
    all_tools = OrderedDict()
    for s in sessions:
        for tool_name in s.summary.tool_call_counts:
            all_tools[tool_name] = None
    tool_names = list(all_tools.keys())

    if not tool_names:
        return

    # Build matrix: rows = tools, cols = sessions
    matrix = np.zeros((len(tool_names), len(sessions)))
    for j, s in enumerate(sessions):
        for i, tool in enumerate(tool_names):
            matrix[i, j] = s.summary.tool_call_counts.get(tool, 0)

    fig, ax = plt.subplots(
        figsize=(max(8, len(sessions) * 2), max(4, len(tool_names) * 0.4))
    )
    im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto")

    ax.set_xticks(np.arange(len(sessions)))
    ax.set_xticklabels([_short_label(s) for s in sessions], fontsize=8, rotation=45, ha="right")
    ax.set_yticks(np.arange(len(tool_names)))
    ax.set_yticklabels(tool_names, fontsize=8)

    # Annotate cells with counts
    for i in range(len(tool_names)):
        for j in range(len(sessions)):
            val = int(matrix[i, j])
            if val > 0:
                ax.text(j, i, str(val), ha="center", va="center", fontsize=8,
                        color="white" if val > matrix.max() * 0.6 else "black")

    ax.set_title("Tool Usage Heatmap")
    fig.colorbar(im, ax=ax, label="Call Count")
    plt.tight_layout()

    if save:
        _ensure_results_dir()
        path = os.path.join(RESULTS_DIR, "comparison_tool_heatmap.png")
        fig.savefig(path, dpi=150)
        print(f"Saved: {path}")

    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_trend_analysis(
    sessions: list[AnalyzedSession], save: bool = True, show: bool = False
):
    """
    Plot key metrics over time (sessions ordered chronologically).
    Useful for tracking improvement as MCP tools are iterated.
    """
    if len(sessions) < 2:
        return

    # Sort by creation date
    sorted_sessions = sorted(sessions, key=lambda s: s.metadata.created_at_ms)
    labels = [_short_label(s) for s in sorted_sessions]
    x = np.arange(len(sorted_sessions))

    total_tokens = [s.summary.total_tokens for s in sorted_sessions]
    durations = [s.summary.total_duration_sec for s in sorted_sessions]
    tool_counts = [s.summary.total_tool_calls for s in sorted_sessions]
    ttfts = [s.summary.average_ttft_ms for s in sorted_sessions]

    fig, axes = plt.subplots(2, 2, figsize=(14, 8))

    # Total tokens over time
    axes[0, 0].plot(x, total_tokens, "o-", color="#4C72B0")
    axes[0, 0].set_title("Total Tokens")
    axes[0, 0].set_ylabel("Tokens")

    # Duration over time
    axes[0, 1].plot(x, durations, "s-", color="#8172B3")
    axes[0, 1].set_title("Session Duration")
    axes[0, 1].set_ylabel("Seconds")

    # Tool calls over time
    axes[1, 0].plot(x, tool_counts, "^-", color="#937860")
    axes[1, 0].set_title("Total Tool Calls")
    axes[1, 0].set_ylabel("Count")

    # TTFT over time
    axes[1, 1].plot(x, ttfts, "d-", color="#55A868")
    axes[1, 1].set_title("Average TTFT")
    axes[1, 1].set_ylabel("ms")

    for ax in axes.flat:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=7, rotation=45, ha="right")
        ax.grid(True, alpha=0.3)

    fig.suptitle("Session Metrics Trend Analysis", fontsize=13)
    plt.tight_layout()

    if save:
        _ensure_results_dir()
        path = os.path.join(RESULTS_DIR, "comparison_trends.png")
        fig.savefig(path, dpi=150)
        print(f"Saved: {path}")

    if show:
        plt.show()
    else:
        plt.close(fig)


def compare_all(
    sessions: list[AnalyzedSession], save: bool = True, show: bool = False
):
    """Run all comparison visualizations."""
    compare_metrics_table(sessions)
    plot_token_comparison(sessions, save=save, show=show)
    plot_duration_comparison(sessions, save=save, show=show)
    plot_tool_usage_heatmap(sessions, save=save, show=show)
    plot_trend_analysis(sessions, save=save, show=show)
