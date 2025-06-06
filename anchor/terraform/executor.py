import subprocess
import json
from pathlib import Path
from typing import Dict, Any
import os


class TerraformExecutor:
    """Wrapper around Terraform CLI for fmt, validate, plan, apply."""

    def __init__(self, working_dir: str):
        self.working_dir = working_dir

    def _run(self, args: list[str]) -> Dict[str, Any]:
        cmd = ["terraform", *args]
        env = os.environ.copy()
        
        # Only add credential variables for commands that actually use AWS
        if args and args[0] in ["plan", "apply", "destroy", "refresh", "import"]:
            # Add credential variables for these commands
            var_args = []
            if "DEST_AWS_ACCESS_KEY_ID" in os.environ:
                var_args.extend(["-var", f"aws_access_key={os.environ['DEST_AWS_ACCESS_KEY_ID']}"])
            if "DEST_AWS_SECRET_ACCESS_KEY" in os.environ:
                var_args.extend(["-var", f"aws_secret_key={os.environ['DEST_AWS_SECRET_ACCESS_KEY']}"])
            if "AWS_REGION" in os.environ:
                var_args.extend(["-var", f"aws_region={os.environ.get('AWS_REGION', 'us-east-1')}"])
            
            # Insert var args after the command but before any other args
            if var_args:
                cmd = ["terraform", args[0]] + var_args + args[1:]
            
            # Also set AWS environment variables for provider authentication
            env["AWS_ACCESS_KEY_ID"] = os.environ["DEST_AWS_ACCESS_KEY_ID"]
            env["AWS_SECRET_ACCESS_KEY"] = os.environ["DEST_AWS_SECRET_ACCESS_KEY"]
        
        proc = subprocess.run(cmd, cwd=self.working_dir, capture_output=True, text=True, env=env)
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }

    def fmt(self) -> Dict[str, Any]:
        return self._run(["fmt", "-recursive", "-check"])

    def init(self) -> Dict[str, Any]:
        return self._run(["init", "-input=false", "-upgrade"])

    def validate(self) -> Dict[str, Any]:
        return self._run(["validate", "-no-color"])

    def plan(self, out_file: str = "tfplan") -> Dict[str, Any]:
        return self._run(["plan", "-input=false", "-no-color", f"-out={out_file}"])

    def show_plan_json(self, plan_file: str = "tfplan") -> Dict[str, Any]:
        result = self._run(["show", "-json", plan_file])
        if result["returncode"] == 0:
            result["json"] = json.loads(result["stdout"])
        return result

    def apply(self, plan_file: str = "tfplan") -> Dict[str, Any]:
        return self._run(["apply", "-input=false", plan_file]) 