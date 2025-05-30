import json
import tempfile
from pathlib import Path
from typing import Dict, Any
import subprocess
import os

from .terraform.executor import TerraformExecutor
from .terraform.parser import plan_stats


class Workspace:
    """Physical checkout where Terraform lives and commands run."""

    def __init__(self, root: str):
        self.root = root
        self.tf = TerraformExecutor(root)

    def snapshot(self) -> Dict[str, Any]:
        """Return observation dict for agent prompt."""
        fmt_res = self.tf.fmt()
        init_res = self.tf.init()
        val_res = self.tf.validate()
        plan_res = self.tf.plan()
        plan_json = self.tf.show_plan_json().get("json", {}) if plan_res["returncode"] == 0 else {}
        return {
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

    def _run_terraform(self, *args) -> subprocess.CompletedProcess:
        """Execute `terraform` command in workspace path."""
        # Use destination AWS credentials for terraform operations
        env = os.environ.copy()
        if "DEST_AWS_ACCESS_KEY_ID" in os.environ:
            env["AWS_ACCESS_KEY_ID"] = os.environ["DEST_AWS_ACCESS_KEY_ID"]
            env["AWS_SECRET_ACCESS_KEY"] = os.environ["DEST_AWS_SECRET_ACCESS_KEY"]
        return subprocess.run(["terraform"] + list(args), cwd=self.root, capture_output=True, text=True, env=env) 