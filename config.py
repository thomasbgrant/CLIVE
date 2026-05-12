"""
Configuration for Copilot Chat Log Analyzer.
"""
import os

# Default path to VS Code workspace storage
WORKSPACE_STORAGE_ROOT = os.path.join(
    os.environ.get("APPDATA", ""),
    "Code", "User", "workspaceStorage"
)

# Output directory for processed results and charts
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

# Maximum characters of tool call result to store (prevents huge memory usage)
TOOL_RESULT_MAX_LENGTH = 2000

# Date format for display
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Date format for filenames
FILENAME_DATETIME_FORMAT = "%Y-%m-%dT%H-%M-%S"
