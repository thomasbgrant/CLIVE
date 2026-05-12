# Chat Log Inspect, View and Evaluate (C.L.I.V.E.)

A Python CLI tool for parsing, analyzing, and visualizing VS Code Copilot Chat debug logs. Built for testing and measuring AI agent performance with custom MCP server tools.

## Example use 1: 
When adding a new feature such as a custom skill to a project, you want to find out if that addition of the skill:
- reduces the number of unneccessary tools calls 
- makes the agent loop run faster / slower
- increases / decreases the number of tokens used

## Example use 2:
My agent runs forever and i dont know what it is doing? It either cannot work out the answer or gets stuck. I want to see:
- what tools were called
- what order tools were called in
- how long each tool took to run

These kinds of questions are hard and time consuming to answer from *eye-balling* agent json logs. **CLIVE** allows you to quickly get a breakdown of tool, time, and token use for a chat session - helping you answer if the changes you made to the MCP tools, skills or other components have made you agent better or worse. 

Agent logic through tool calling order is hard to debug by traditional means - it is stochastic and variable. CLIVE shows you quickly how many times a tool was called and the order of the tool calls as well as how long each tool took to run.

## Prerequisites: Enable Copilot Chat Debug Logging

This tool reads debug log files that VS Code only writes when debug logging is explicitly enabled. **You must enable this in every VS Code window you want to capture logs from.**

### Option A: Command Palette (per window)

1. Open the VS Code window where you'll run the chat session you want to analyze.
2. Press `Ctrl+Shift+P` to open the Command Palette.
3. Type `Debug: Enable Debug Logging for Copilot Chat` and select it.
4. You should see a notification confirming logging is enabled.

### Option B: VS Code Settings (persistent)

1. Press `Ctrl+,` to open Settings.
2. Search for `copilot debug`.
3. Check **GitHub > Copilot > Chat: Debug Log** to enable it.

Or add this directly to your `settings.json` (`Ctrl+Shift+P` → `Preferences: Open User Settings (JSON)`):

```json
"github.copilot.chat.debugLog": true
```

Setting this in **User** settings applies it to all windows. Setting it in **Workspace** settings applies only to that project.

### Important notes

- **Reload required for existing windows.** If you change the setting while a VS Code window is already open, you must reload that window (`Ctrl+Shift+P` → `Developer: Reload Window`) for logging to take effect. Windows opened *after* the setting change will pick it up automatically.
- **Each window logs independently.** Debug logs are stored per workspace under `%APPDATA%\Code\User\workspaceStorage\{workspace_id}\GitHub.copilot-chat\debug-logs\{session_id}\main.jsonl`. If a window wasn't logging when the chat happened, there is nothing to analyze.
- **Verify logging is active.** After enabling, start a chat and then check that the `debug-logs` folder exists in your workspace storage:
  ```
  dir "%APPDATA%\Code\User\workspaceStorage" /AD /B
  ```
  Then for a specific workspace:
  ```
  dir "%APPDATA%\Code\User\workspaceStorage\{workspace_id}\GitHub.copilot-chat\debug-logs" /AD /B
  ```

## Setup

```bash
pip install -r requirements.txt
```

**Dependencies** (standard Python libraries only):
- `numpy` — numerical operations
- `matplotlib` — chart generation
- `pandas` — data analysis (available for notebook/script use)
- `json`, `os`, `argparse`, `glob`, `datetime`, `dataclasses` — all from Python stdlib

## Usage

All commands are run from the `log_debugging/` directory.

### List available sessions

```bash
# All sessions across all workspaces
python main.py list

# Sessions from a specific workspace
python main.py list --workspace de20fe11bc4648ce43f991ef48fb20bf
```

### Analyze a session

```bash
# Analyze the most recent session
python main.py analyze --latest

# Analyze a specific session by ID
python main.py analyze --session 538a658e-1248-4d00-b633-b18af781674a

# Analyze with visualization charts
python main.py analyze --latest --visualize

# Also display charts interactively (not just save)
python main.py analyze --latest --visualize --show
```

### Compare sessions

```bash
# Compare specific result files
python main.py compare results/538a658e_2026-04-10T14-30-00.json results/other.json

# Compare all results in the results/ directory
python main.py compare --all
```

## Output

- **Console**: Human-readable summary printed to terminal
- **JSON**: Structured results saved to `results/{session_id}_{timestamp}.json`
- **Charts**: PNG files saved to `results/` when `--visualize` is used

### Single-session charts
- Token usage per turn (stacked bar)
- Tool call frequency (horizontal bar)
- Tool call sequence (Gantt chart)
- Timing breakdown (TTFT, tool time, total)
- Event timeline (all events with durations)

### Comparison charts
- Token usage comparison (grouped bar)
- Duration comparison (bar)
- Tool usage heatmap (matrix)
- Trend analysis (line plots over time)

## Project Structure

```
log_debugging/
├── main.py                     # CLI entry point
├── config.py                   # Configuration (paths, defaults)
├── requirements.txt            # Python dependencies
├── parser/
│   ├── models.py               # Data classes (Session, Turn, ToolCall, etc.)
│   ├── session_finder.py       # Find sessions by ID, latest, or list all
│   ├── debug_log_parser.py     # Parse main.jsonl event streams
│   └── session_state_parser.py # Parse session state (messages, attachments)
├── analyzer/
│   ├── extractor.py            # Build structured data from raw events
│   └── aggregator.py           # Compute session-level summaries
├── visualizer/
│   ├── single_session.py       # Charts for one session
│   └── comparison.py           # Charts comparing multiple sessions
└── results/                    # Output directory (JSON + PNG)
```

## Data Source

Reads from VS Code workspace storage at:
```
%APPDATA%\Code\User\workspaceStorage\
```

The tool is **read-only** — it never modifies log files.
