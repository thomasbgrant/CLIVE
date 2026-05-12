"""
Copilot Chat Log Analyzer — CLI entry point.

Usage:
    python main.py list [--workspace WORKSPACE_ID]
    python main.py analyze --latest [--workspace WORKSPACE_ID] [--visualize] [--show]
    python main.py analyze --session SESSION_ID [--workspace WORKSPACE_ID] [--visualize] [--show]
    python main.py compare FILE1.json FILE2.json ... [--show]
    python main.py compare --all [--show]
"""
import argparse
import json
import os
import sys
import glob
from datetime import datetime

from config import RESULTS_DIR, FILENAME_DATETIME_FORMAT
from parser.session_finder import list_sessions, find_session, find_latest_session
from parser.models import AnalyzedSession
from analyzer.extractor import extract_session
from analyzer.aggregator import compute_summary
from analyzer.redaction import redact_text
from visualizer.single_session import plot_all as plot_single
from visualizer.comparison import compare_all


def cmd_list(args):
    """List available chat sessions."""
    sessions = list_sessions(workspace_id=args.workspace)

    if not sessions:
        print("No sessions found.")
        return

    # Print table header
    header = (
        f"{'#':<4} {'Session ID':<38} {'Title':<35} "
        f"{'Date':<22} {'Model':<25} {'Workspace':<15}"
    )
    print(header)
    print("-" * len(header))

    for i, s in enumerate(sessions, 1):
        title = (s["title"] or "—")[:33]
        date = s["created_at"] or "—"
        model = (s["model"] or "—")[:23]
        ws = s["workspace_name"][:13] or s["workspace_id"][:13]
        print(
            f"{i:<4} {s['session_id']:<38} {title:<35} "
            f"{date:<22} {model:<25} {ws:<15}"
        )

    print(f"\nTotal: {len(sessions)} sessions")


def cmd_analyze(args):
    """Analyze a specific or the latest session."""
    # Find the session
    if args.session:
        session_info = find_session(args.session, workspace_id=args.workspace)
        if not session_info:
            print(f"ERROR: Session '{args.session}' not found.", file=sys.stderr)
            sys.exit(1)
    elif args.latest:
        session_info = find_latest_session(workspace_id=args.workspace)
        if not session_info:
            print("ERROR: No sessions found.", file=sys.stderr)
            sys.exit(1)
    else:
        print("ERROR: Specify --session SESSION_ID or --latest.", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing session: {session_info['session_id']}")
    print(f"  Title:     {redact_text(session_info.get('title', '—'))}")
    print(f"  Workspace: {session_info['workspace_id']}")
    print(f"  Log file:  {redact_text(session_info['main_jsonl_path'])}")
    print()

    # Extract and aggregate
    session = extract_session(session_info)
    session = compute_summary(session)

    # Print console summary
    _print_summary(session)

    # Save JSON results
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime(FILENAME_DATETIME_FORMAT)
    filename = f"{session.metadata.session_id[:8]}_{timestamp}.json"
    output_path = os.path.join(RESULTS_DIR, filename)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(session.to_json())
    print(f"\nResults saved: {output_path}")

    # Visualizations
    if args.visualize:
        print("\nGenerating visualizations...")
        plot_single(session, save=True, show=args.show)


def cmd_compare(args):
    """Compare multiple processed session results."""
    if args.all:
        # Load all JSON files from results directory
        pattern = os.path.join(RESULTS_DIR, "*.json")
        files = sorted(glob.glob(pattern))
        if not files:
            print(f"No result files found in {RESULTS_DIR}/")
            sys.exit(1)
        print(f"Found {len(files)} result files in {RESULTS_DIR}/")
    else:
        files = args.files
        if not files or len(files) < 2:
            print("ERROR: Provide at least 2 result JSON files to compare.", file=sys.stderr)
            sys.exit(1)

    # Load sessions
    sessions = []
    for f in files:
        if not os.path.isfile(f):
            print(f"WARNING: File not found, skipping: {f}", file=sys.stderr)
            continue
        try:
            session = AnalyzedSession.from_json_file(f)
            sessions.append(session)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"WARNING: Failed to load {f}: {e}", file=sys.stderr)

    if len(sessions) < 2:
        print("ERROR: Need at least 2 valid sessions to compare.", file=sys.stderr)
        sys.exit(1)

    print(f"Comparing {len(sessions)} sessions...\n")
    compare_all(sessions, save=True, show=args.show)


def _print_summary(session: AnalyzedSession):
    """Print a human-readable session summary to the console."""
    m = session.metadata
    s = session.summary

    print("=" * 70)
    print("SESSION ANALYSIS SUMMARY")
    print("=" * 70)
    print(f"  Session ID:      {m.session_id}")
    print(f"  Title:           {m.title or '—'}")
    print(f"  Created:         {m.created_at}")
    print(f"  Model:           {m.model}")
    print(f"  Copilot Version: {m.copilot_version}")
    print(f"  VS Code Version: {m.vscode_version}")
    print()
    print(f"  Total Turns:         {s.total_turns}")
    print(f"  Total Tool Calls:    {s.total_tool_calls}")
    print(f"  Total Input Tokens:  {s.total_input_tokens:,}")
    print(f"  Total Output Tokens: {s.total_output_tokens:,}")
    print(f"  Total Tokens:        {s.total_tokens:,}")
    print(f"  Total Duration:      {s.total_duration_sec:.1f}s ({s.total_duration_ms:,}ms)")
    print(f"  Average TTFT:        {s.average_ttft_ms:.0f}ms")

    if s.tool_call_counts:
        print()
        print("  Tool Call Breakdown:")
        for tool_name, count in s.tool_call_counts.items():
            print(f"    {tool_name:<35} {count:>4}x")

    # Per-turn detail
    for turn in session.turns:
        print()
        print(f"  --- Turn {turn.turn_number} ---")
        prompt_preview = turn.user_prompt[:100]
        if len(turn.user_prompt) > 100:
            prompt_preview += "..."
        print(f"  Prompt:    {prompt_preview}")
        print(f"  Tokens:    {turn.input_tokens:,} in / {turn.output_tokens:,} out / {turn.total_tokens:,} total")
        print(f"  TTFT:      {turn.ttft_ms}ms")
        print(f"  Duration:  {turn.total_duration_ms:,}ms ({turn.total_duration_ms / 1000:.1f}s)")
        print(f"  Tools ({len(turn.tool_calls)}):")
        for tc in turn.tool_calls:
            status_marker = "OK" if tc.status == "ok" else "FAIL"
            print(f"    [{status_marker}] {tc.name} ({tc.duration_ms}ms)")

        if turn.files_accessed:
            print(f"  Files Accessed ({len(turn.files_accessed)}):")
            for fa in turn.files_accessed:
                print(f"    {redact_text(fa)}")

        if turn.context_files:
            print(f"  Context Files ({len(turn.context_files)}):")
            for cf in turn.context_files:
                print(f"    {redact_text(cf)}")

        print(f"  Context–Prompt Similarity: {turn.context_similarity:.4f} (Jaccard)")

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Copilot Chat Log Analyzer — parse, analyze, and visualize chat session logs."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list
    list_parser = subparsers.add_parser("list", help="List available chat sessions")
    list_parser.add_argument("--workspace", "-w", help="Scope to a specific workspace UUID")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a chat session")
    analyze_parser.add_argument("--session", "-s", help="Session UUID to analyze")
    analyze_parser.add_argument("--latest", "-l", action="store_true", help="Analyze the most recent session")
    analyze_parser.add_argument("--workspace", "-w", help="Scope to a specific workspace UUID")
    analyze_parser.add_argument("--visualize", "-v", action="store_true", help="Generate visualization charts")
    analyze_parser.add_argument("--show", action="store_true", help="Display charts interactively (in addition to saving)")

    # compare
    compare_parser = subparsers.add_parser("compare", help="Compare multiple sessions")
    compare_parser.add_argument("files", nargs="*", help="Result JSON files to compare")
    compare_parser.add_argument("--all", "-a", action="store_true", help="Compare all results in results/ directory")
    compare_parser.add_argument("--show", action="store_true", help="Display charts interactively")

    args = parser.parse_args()

    if args.command == "list":
        cmd_list(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "compare":
        cmd_compare(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
