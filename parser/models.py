"""
Data models for Copilot Chat Log Analyzer.

All structured data flows through these dataclasses. To add new fields,
extend the relevant dataclass — no other code changes needed for storage/serialization.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import json


@dataclass
class ToolCall:
    """A single tool invocation within a turn."""
    name: str
    args: dict = field(default_factory=dict)
    result_summary: str = ""
    duration_ms: int = 0
    status: str = "ok"
    span_id: str = ""
    parent_span_id: str = ""
    timestamp_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LLMRequest:
    """A single LLM completion request within a turn."""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    ttft_ms: int = 0
    duration_ms: int = 0
    max_tokens: int = 0
    temperature: float = 0.0
    span_id: str = ""
    timestamp_ms: int = 0

    def __post_init__(self):
        self.total_tokens = self.input_tokens + self.output_tokens

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Turn:
    """One user message + agent response cycle."""
    turn_number: int = 0
    user_prompt: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    llm_requests: list[LLMRequest] = field(default_factory=list)
    context_files: list[str] = field(default_factory=list)
    files_accessed: list[str] = field(default_factory=list)
    context_text: str = ""
    context_similarity: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    ttft_ms: int = 0
    total_duration_ms: int = 0
    start_ts: int = 0
    end_ts: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        # Exclude bulky context_text from serialization — keep it lightweight
        d.pop("context_text", None)
        return d


@dataclass
class SessionMetadata:
    """Basic session-level information."""
    session_id: str = ""
    workspace_id: str = ""
    title: str = ""
    created_at: str = ""
    created_at_ms: int = 0
    model: str = ""
    model_vendor: str = ""
    copilot_version: str = ""
    vscode_version: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SessionSummary:
    """Aggregated metrics for the entire session."""
    total_turns: int = 0
    total_tool_calls: int = 0
    tool_call_counts: dict[str, int] = field(default_factory=dict)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_duration_ms: int = 0
    total_duration_sec: float = 0.0
    average_ttft_ms: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AnalyzedSession:
    """Complete analyzed session — the main output object."""
    metadata: SessionMetadata = field(default_factory=SessionMetadata)
    turns: list[Turn] = field(default_factory=list)
    summary: SessionSummary = field(default_factory=SessionSummary)

    def to_dict(self) -> dict:
        return {
            "metadata": self.metadata.to_dict(),
            "turns": [t.to_dict() for t in self.turns],
            "summary": self.summary.to_dict(),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: dict) -> "AnalyzedSession":
        """Reconstruct from a saved JSON dict."""
        metadata = SessionMetadata(**data.get("metadata", {}))
        turns = []
        for t in data.get("turns", []):
            tool_calls = [ToolCall(**tc) for tc in t.pop("tool_calls", [])]
            llm_requests = [LLMRequest(**lr) for lr in t.pop("llm_requests", [])]
            # Drop unknown keys that may appear from older/newer versions
            import inspect
            valid_keys = {f.name for f in __import__('dataclasses').fields(Turn)}
            t = {k: v for k, v in t.items() if k in valid_keys}
            turns.append(Turn(**t, tool_calls=tool_calls, llm_requests=llm_requests))
        summary_data = data.get("summary", {})
        summary = SessionSummary(**summary_data)
        return cls(metadata=metadata, turns=turns, summary=summary)

    @classmethod
    def from_json_file(cls, path: str) -> "AnalyzedSession":
        """Load from a saved JSON results file."""
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))
