# Copilot Chat Log Analyzer — Requirements Specification

## 1. Project Overview

### 1.1 Purpose

A standalone Python tool for parsing, analyzing, and visualizing VS Code Copilot Chat debug logs. The tool is used for **testing, monitoring, and measuring the abilities of AI agents** that use custom MCP server tools (developed separately for Cegal Prizm / Petrel software).

This tool is **read-only** — it does not modify any log files or interact with MCP servers. It only consumes the chat logs and session data that VS Code Copilot Chat already produces.

### 1.2 Context

The developer is a data scientist building custom MCP server tools in a separate workspace. This analyzer serves as a **test harness** to objectively evaluate agent behavior: what tools were called, in what order, how much compute was used, and how long operations took. Results should support iterative improvement of the MCP tools and agent instructions.

### 1.3 Language & Environment

- **Language**: Python 3.10+
- **Platform**: Windows (paths use backslashes; the tool should handle this)
- **Dependencies**: Standard scientific Python stack (pandas, matplotlib/plotly, etc.)
- **Deployment**: Local CLI tool, run from this project directory

---

## 2. Data Source

### 2.1 Root Location

All data lives under the VS Code workspace storage directory:

```
C:\Users\thomas.grant\AppData\Roaming\Code\User\workspaceStorage\
```

This directory contains multiple **workspace folders**, each identified by a UUID (e.g., `de20fe11bc4648ce43f991ef48fb20bf`). Each workspace folder corresponds to a VS Code workspace the user has opened.

### 2.2 Directory Structure Per Workspace

```
{workspace-uuid}/
├── workspace.json                          # Workspace name & folder paths
├── chatSessions/
│   └── {sessionId}.jsonl                   # Session state (messages, attachments, metadata)
├── chatEditingSessions/
│   └── {sessionId}/
│       └── state.json                      # Consolidated session state
└── GitHub.copilot-chat/
    └── debug-logs/
        └── {sessionId}/
            ├── main.jsonl                  # PRIMARY: Full event stream (all events)
            ├── title-{uuid}.jsonl          # Title-generation events (can ignore)
            ├── models.json                 # Available models list
            ├── system_prompt_0.json        # System prompt sent to LLM
            └── tools_0.json               # Tool definitions available to agent
```

### 2.3 Key Files

| File | Format | Purpose |
|------|--------|---------|
| `debug-logs/{sessionId}/main.jsonl` | JSONL | **Primary data source.** Contains all events: tool calls, LLM requests, token usage, timing, user messages. One JSON object per line. |
| `chatSessions/{sessionId}.jsonl` | JSONL | Session-level state with user messages, response text, file attachments, and model selection. Uses incremental key-value log format. |
| `chatEditingSessions/{sessionId}/state.json` | JSON | Consolidated session state (mirrors chatSessions data). Contains `requests[]` array with full message history. |
| `debug-logs/{sessionId}/models.json` | JSON | Array of available model objects with capabilities, token limits, and billing multipliers. |
| `debug-logs/{sessionId}/system_prompt_0.json` | JSON | System prompt content sent to the LLM (`{ "content": "..." }`). |
| `debug-logs/{sessionId}/tools_0.json` | JSON | Array of tool definitions (name, description, parameter schema). |

---

## 3. Data Schemas

### 3.1 Debug Log Events (`main.jsonl`)

Each line in `main.jsonl` is a JSON object with this base structure:

```json
{
  "ts": 1775849560328,
  "dur": 0,
  "sid": "538a658e-1248-4d00-b633-b18af781674a",
  "type": "user_message",
  "name": "read_file",
  "spanId": "0000000000000009",
  "parentSpanId": "0000000000000003",
  "status": "ok",
  "attrs": { }
}
```

**Base fields (present on every event):**

| Field | Type | Description |
|-------|------|-------------|
| `ts` | int (ms epoch) | Event timestamp in milliseconds since Unix epoch |
| `dur` | int (ms) | Event duration in milliseconds (0 = instant) |
| `sid` | string (UUID) | Session ID |
| `type` | string | Event category (see table below) |
| `name` | string | Descriptive event name (e.g., tool name for tool_call) |
| `spanId` | string (hex) | Unique event identifier |
| `parentSpanId` | string (hex) | Parent event ID (forms a call tree) |
| `status` | string | `"ok"` or `"error"` |
| `attrs` | object | Event-specific payload (varies by type) |

### 3.2 Event Types

| `type` | `name` example | Key `attrs` fields | What to extract |
|--------|----------------|-------------------|-----------------|
| `session_start` | `session_start` | `copilotVersion`, `vscodeVersion` | Session metadata |
| `user_message` | `user_message` | `content` (user's text) | User prompt text |
| `turn_start` | `turn_start:0` | `turnId` | Turn boundary (start) |
| `turn_end` | `turn_end:0` | `turnId` | Turn boundary (end) |
| `tool_call` | `read_file`, `grep_search`, etc. | `args` (JSON string), `result` (string) | Tool name, arguments, result, duration |
| `llm_request` | `chat:claude-opus-4.6` | `model`, `inputTokens`, `outputTokens`, `ttft`, `maxTokens`, `temperature` | Token usage, model, latency |
| `agent_response` | `agent_response` | `response` (JSON string of parts) | Agent output text and tool calls |
| `discovery` | `discovery` | `details` (loaded agents, skills, tools) | Context setup information |
| `generic` | varies | varies | System-level events |

### 3.3 Important Parsing Notes

- **Tool call `args`**: Stored as a JSON **string** inside `attrs.args`. Requires double-parsing: first parse the JSONL line, then parse the `args` string value as JSON.
  ```json
  "args": "{\"filePath\":\"c:\\\\Users\\\\...\",\"startLine\":1,\"endLine\":50}"
  ```
- **Windows paths**: Backslashes are double-escaped in JSON strings. Handle `\\\\` → `\\` → `\`.
- **Span tree**: `parentSpanId` links child events to parents. The user message span is typically the root; tool calls and LLM requests are children.
- **Incomplete sessions**: If VS Code crashes, JSONL may be truncated. Always wrap JSON parsing in try/except per line.

### 3.4 Session State (`chatSessions/*.jsonl` / `state.json`)

The `state.json` or the consolidated state from `chatSessions/*.jsonl` contains:

```json
{
  "version": 3,
  "creationDate": 1775848827111,
  "customTitle": "Session Title",
  "sessionId": "538a658e-...",
  "requests": [
    {
      "requestId": "request_5a966141-...",
      "timestamp": 1775849557983,
      "agent": { "name": "agent", "extensionVersion": "0.43.0" },
      "modelId": "copilot/claude-opus-4.6",
      "message": { "text": "user message text", "parts": [...] },
      "response": [...]
    }
  ],
  "inputState": {
    "attachments": [
      {
        "kind": "file",
        "name": "myfile.md",
        "value": { "fsPath": "c:\\path\\to\\myfile.md" }
      }
    ],
    "selectedModel": { "id": "claude-opus-4.6", "name": "Claude Opus 4.6" }
  }
}
```

### 3.5 Models Configuration (`models.json`)

```json
{
  "id": "claude-opus-4.6",
  "name": "Claude Opus 4.6",
  "vendor": "Anthropic",
  "family": "claude-opus-4.6",
  "capabilities": {
    "limits": { "max_context_window_tokens": 200000, "max_output_tokens": 32000 },
    "supports": { "tool_calls": true, "streaming": true, "vision": true }
  },
  "billing": { "is_premium": true, "multiplier": 3 }
}
```

---

## 4. Functional Requirements

### 4.1 Session Selection

The user must be able to:

1. **Select by session ID**: Provide a specific UUID to analyze a known session.
2. **Select latest session**: Automatically find and analyze the most recent session (by `creationDate` or most recent `main.jsonl` modification time).
3. **Select by workspace**: Optionally scope the search to a specific workspace UUID. If not specified, search across all workspaces.
4. **List available sessions**: Show a table of available sessions with ID, title, date, model, and workspace — so the user can pick one.

### 4.2 Data Extraction — Per Session

Extract and structure the following from each analyzed session:

#### 4.2.1 Session Metadata
- Session ID
- Workspace ID
- Session title (from `customTitle` or auto-generated)
- Creation date/time
- Model used (name, vendor, family)
- Copilot extension version
- VS Code version

#### 4.2.2 Per-Turn Data (a "turn" = one user message + agent response cycle)
- **Turn number** (sequential, starting from 1)
- **User prompt text** (from `user_message` event or `requests[].message.text`)
- **Tool calls** — ordered list of:
  - Tool name
  - Arguments (parsed from JSON string)
  - Result summary (first N characters or status)
  - Duration (ms)
  - Success/failure status
- **Context files used** — list of file paths attached or referenced (from `inputState.attachments` and `variableData`)
- **Token usage**:
  - Input tokens
  - Output tokens
  - Total tokens
- **Timing**:
  - Time to first token (TTFT) in ms
  - Total turn duration in ms (from `turn_start` to `turn_end`, or from first to last event in that turn's span tree)
- **LLM request details**:
  - Model name
  - Max tokens setting
  - Temperature

#### 4.2.3 Session Summary (aggregated)
- Total number of turns
- Total number of tool calls
- List of unique tools used (with call counts)
- Total input tokens / output tokens / combined
- Total session duration (ms and seconds)
- Average TTFT across turns

### 4.3 Extensibility

The data extraction must be designed so that **new fields can be added later** without restructuring the code. Use a dictionary/dataclass-based approach where new attributes can be added to the extraction pipeline with minimal changes.

### 4.4 Output Formats

Processed session data must be exportable in formats suitable for analysis:

1. **JSON file** — Full structured output (for programmatic re-use).
2. **Console summary** — Human-readable text summary printed to terminal.
3. **pandas DataFrame** — For interactive analysis in notebooks or scripts. One row per turn, with session metadata repeated or in a separate summary object.

Processed results should be saved to a `results/` directory within this project, named by session ID and timestamp (e.g., `results/538a658e_2026-04-10T14-30-00.json`).

---

## 5. Visualization Requirements

### 5.1 Single-Session Visualizations

Provide the following charts/views for a single analyzed session:

1. **Turn Timeline** — Horizontal timeline showing events over time (tool calls, LLM requests) with duration bars. Shows the sequence and parallelism of operations.
2. **Token Usage Bar Chart** — Stacked bar chart per turn showing input vs. output tokens.
3. **Tool Call Summary** — Bar chart of tool call frequency (how many times each tool was called).
4. **Tool Call Sequence** — Ordered list or Gantt-style chart showing tool calls in execution order with durations.
5. **Timing Breakdown** — Per-turn breakdown showing TTFT, tool execution time, and total turn time.

### 5.2 Multi-Session Comparison

Support loading multiple processed session results and comparing them:

1. **Side-by-Side Metrics Table** — Compare key metrics (total tokens, duration, tool call count, TTFT) across sessions in a table.
2. **Token Usage Comparison** — Grouped bar chart comparing input/output tokens across sessions.
3. **Duration Comparison** — Bar chart comparing total session durations.
4. **Tool Usage Heatmap** — Matrix showing which tools each session used and how many times.
5. **Trend Analysis** — If sessions are ordered chronologically (e.g., iterating on MCP tools), plot metrics over time to show improvement trends.

### 5.3 Visualization Implementation

- Use **matplotlib** for static charts (default) and/or **plotly** for interactive HTML charts.
- All charts should have clear titles, axis labels, and legends.
- Charts should be saveable to `results/` as PNG or HTML files.
- Provide a simple function-based API so charts can be generated from a script or notebook.

---

## 6. Architecture & Project Structure

### 6.1 Proposed Directory Layout

```
log_debugging/
├── requirements_log_debugging.md       # This file
├── README.md                           # Usage instructions
├── config.py                           # Configuration (paths, defaults)
├── main.py                             # CLI entry point
├── parser/
│   ├── __init__.py
│   ├── session_finder.py               # Find sessions by ID, latest, or list all
│   ├── debug_log_parser.py             # Parse main.jsonl (events, spans, tool calls)
│   ├── session_state_parser.py         # Parse chatSessions/*.jsonl and state.json
│   └── models.py                       # Data classes for Session, Turn, ToolCall, etc.
├── analyzer/
│   ├── __init__.py
│   ├── extractor.py                    # Extract structured data from parsed events
│   └── aggregator.py                   # Compute session-level summaries
├── visualizer/
│   ├── __init__.py
│   ├── single_session.py               # Charts for one session
│   └── comparison.py                   # Charts comparing multiple sessions
├── results/                            # Output directory for processed data & charts
│   └── .gitkeep
└── tests/
    ├── __init__.py
    └── test_parser.py                  # Unit tests for parsing logic
```

### 6.2 Key Design Principles

1. **Separation of concerns**: Parsing, analysis, and visualization are separate modules.
2. **Data classes over dicts**: Use Python dataclasses (or Pydantic models) for `Session`, `Turn`, `ToolCall`, `LLMRequest`, `TokenUsage`, `TimingInfo` — gives type safety and easy serialization.
3. **Extensibility**: New fields are added by extending the dataclass and the corresponding extraction function. No shotgun surgery.
4. **Graceful error handling**: Malformed JSONL lines are skipped with a warning (not a crash). Missing files produce clear error messages.
5. **Immutable raw data**: Never write to the workspace storage directory. All outputs go to `results/`.

### 6.3 Configuration (`config.py`)

```python
# Default path to VS Code workspace storage
WORKSPACE_STORAGE_ROOT = r"C:\Users\thomas.grant\AppData\Roaming\Code\User\workspaceStorage"

# Output directory for processed results
RESULTS_DIR = "results"

# Maximum characters of tool result to store (to avoid huge memory usage)
TOOL_RESULT_MAX_LENGTH = 2000
```

These should be overridable via CLI arguments.

---

## 7. CLI Interface

### 7.1 Commands

```bash
# List all available sessions across workspaces
python main.py list

# List sessions for a specific workspace
python main.py list --workspace de20fe11bc4648ce43f991ef48fb20bf

# Analyze the latest session
python main.py analyze --latest

# Analyze a specific session by ID
python main.py analyze --session 538a658e-1248-4d00-b633-b18af781674a

# Analyze and generate visualizations
python main.py analyze --latest --visualize

# Compare multiple processed sessions
python main.py compare results/session1.json results/session2.json

# Compare all sessions in results directory
python main.py compare --all
```

### 7.2 Output

- **`list`**: Prints a table (session ID, title, date, model, workspace, turn count).
- **`analyze`**: Prints a console summary and saves a JSON file to `results/`.
- **`analyze --visualize`**: Additionally generates and saves charts.
- **`compare`**: Generates comparison charts and a summary table.

---

## 8. Non-Functional Requirements

- **Read-only**: The tool must never write to or modify the workspace storage directory.
- **Performance**: Should handle sessions with hundreds of tool calls and tens of thousands of JSONL lines without significant delay (< 5 seconds for parsing).
- **Error resilience**: Gracefully handle truncated JSONL, missing files, unexpected event types, and schema changes.
- **No external services**: Fully offline, no API calls, no network access.
- **Reproducible**: Given the same session ID, always produces the same output.

---

## 9. Future Considerations (Out of Scope for v1, but design for)

- **Automated test harness**: Run a predefined prompt against an agent, then automatically analyze the resulting session log.
- **MCP tool-specific analysis**: Filter and report specifically on custom MCP tool calls (vs. built-in tools like `read_file`).
- **Cost estimation**: Use `billing.multiplier` from `models.json` to estimate API cost per session.
- **Notebook integration**: Provide a Jupyter notebook template for interactive exploration of processed session data.
- **Regression tracking**: Compare current session metrics against a saved baseline to detect performance regressions in MCP tools.