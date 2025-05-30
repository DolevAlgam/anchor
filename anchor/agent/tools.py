import json
import logging
from pathlib import Path
from typing import Dict, Any

# In the future, import Workspace type for type hints

class Tool:
    """Simple representation of a callable tool exposed to the LLM (OpenAI function format)."""

    def __init__(self, func, name: str, description: str, parameters: Dict[str, Any]):
        self.func = func
        self.name = name
        self.description = description
        # OpenAI expects a wrapper with type "function" and inner function object
        self.schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        }

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)


def patch_file(path: str, diff: str, workspace):
    """Apply a UNIX style patch string to a file in workspace."""
    file_path = Path(workspace.root) / path
    original = file_path.read_text()
    # TODO: more robust patching; for now just overwrite with diff content
    file_path.write_text(diff)
    return f"Patched {path} (len={len(diff)})"


def delete_file(path: str, workspace):
    file_path = Path(workspace.root) / path
    if file_path.exists():
        file_path.unlink()
        return f"Deleted {path}"
    return f"{path} not found"


def run_command(cmd: str, workspace):
    import subprocess, shlex
    completed = subprocess.run(shlex.split(cmd), cwd=workspace.root, capture_output=True, text=True)
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }

# Map tool names to Tool instances
TOOL_MAP: Dict[str, Tool] = {
    "patch_file": Tool(
        patch_file,
        name="patch_file",
        description="Apply a patch (replace file content) to a file in the repo.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to file relative to repo root"},
                "diff": {"type": "string", "description": "New contents of the file."},
            },
            "required": ["path", "diff"],
        },
    ),
    "delete_file": Tool(
        delete_file,
        name="delete_file",
        description="Delete a file from the repo.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        },
    ),
    "run_command": Tool(
        run_command,
        name="run_command",
        description="Execute a shell command inside the workspace.",
        parameters={
            "type": "object",
            "properties": {
                "cmd": {"type": "string"},
            },
            "required": ["cmd"],
        },
    ),
}


def apply_llm_actions(response, workspace, tool_map: Dict[str, Tool], logger: logging.Logger) -> bool:
    """Execute function calls returned by the LLM response.

    Returns True if the model indicated the overall task is finished.
    """
    # openai v1 response structure
    for choice in response.choices:
        msg = choice.message
        if getattr(msg, "tool_calls", None):
            for call in msg.tool_calls:
                tool_name = call.function.name
                handler = tool_map.get(tool_name)
                if not handler:
                    logger.warning("Tool %s not registered", tool_name)
                    continue
                args = json.loads(call.function.arguments)
                result = handler(**args, workspace=workspace)
                logger.info("Tool %s returned: %s", tool_name, result)
        if msg.content and msg.content.strip().lower().startswith("finished"):
            # model signals done
            return True
    return False 