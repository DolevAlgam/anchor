import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List
import subprocess
import os

from .terraform.executor import TerraformExecutor
from .terraform.parser import plan_stats


class Workspace:
    """Physical checkout where Terraform lives and commands run."""

    def __init__(self, root: str):
        self.root = root
        self.tf = TerraformExecutor(root)

    def _get_directory_structure(self, max_depth: int = 3) -> Dict[str, Any]:
        """Get directory structure up to max_depth levels."""
        structure = {}
        root_path = Path(self.root)
        
        def build_tree(path: Path, current_depth: int = 0) -> Dict[str, Any]:
            if current_depth >= max_depth:
                return {}
            
            tree = {}
            try:
                for item in sorted(path.iterdir()):
                    if item.name.startswith('.'):
                        continue
                    if item.is_dir():
                        tree[item.name + '/'] = build_tree(item, current_depth + 1)
                    else:
                        tree[item.name] = 'file'
            except PermissionError:
                pass
            return tree
        
        return build_tree(root_path)

    def _get_main_tf_content(self) -> str:
        """Get the content of main.tf if it exists."""
        main_tf = Path(self.root) / "main.tf"
        if main_tf.exists():
            try:
                return main_tf.read_text()
            except Exception:
                return "Error reading main.tf"
        return "main.tf not found"

    def snapshot(self) -> Dict[str, Any]:
        """Return observation dict for agent prompt."""
        fmt_res = self.tf.fmt()
        init_res = self.tf.init()
        val_res = self.tf.validate()
        plan_res = self.tf.plan()
        plan_json = self.tf.show_plan_json().get("json", {}) if plan_res["returncode"] == 0 else {}
        
        # Add directory structure and main.tf content for better context
        return {
            "directory_structure": self._get_directory_structure(),
            "main_tf_content": self._get_main_tf_content(),
            "fmt": fmt_res,
            "validate": val_res,
            "plan": {
                "returncode": plan_res["returncode"],
                "stderr": plan_res["stderr"][-2000:],
                "stats": plan_stats(plan_json) if plan_json else {},
            },
        }

    @classmethod
    def temp(cls, repo_path: str) -> "Workspace":
        temp_dir = tempfile.mkdtemp(prefix="anchor_ws_")
        # shallow copy / symlink? for now operate in place
        return cls(repo_path) 