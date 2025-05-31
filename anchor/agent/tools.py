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
    if not file_path.exists():
        return f"Error: File {path} does not exist"
    original = file_path.read_text()
    # TODO: more robust patching; for now just overwrite with diff content
    file_path.write_text(diff)
    return f"Patched {path} (original: {len(original)} chars, new: {len(diff)} chars)"


def delete_file(path: str, workspace):
    file_path = Path(workspace.root) / path
    if file_path.exists():
        file_path.unlink()
        return f"Deleted {path}"
    return f"{path} not found"


def run_command(cmd: str, workspace):
    import subprocess, shlex, os
    try:
        # Parse command safely
        cmd_parts = shlex.split(cmd)
        
        # If it's a terraform command that needs AWS credentials, add them
        if len(cmd_parts) >= 2 and cmd_parts[0] == "terraform" and cmd_parts[1] in ["plan", "apply", "destroy", "refresh", "import"]:
            # Insert credential variables after the terraform command
            var_args = []
            if "DEST_AWS_ACCESS_KEY_ID" in os.environ:
                var_args.extend(["-var", f"aws_access_key={os.environ['DEST_AWS_ACCESS_KEY_ID']}"])
            if "DEST_AWS_SECRET_ACCESS_KEY" in os.environ:
                var_args.extend(["-var", f"aws_secret_key={os.environ['DEST_AWS_SECRET_ACCESS_KEY']}"])
            if "AWS_REGION" in os.environ:
                var_args.extend(["-var", f"aws_region={os.environ.get('AWS_REGION', 'us-east-1')}"])
            
            if var_args:
                # Insert variables after the command (e.g., "terraform plan" -> "terraform plan -var ... -var ...")
                cmd_parts = cmd_parts[:2] + var_args + cmd_parts[2:]
        
        completed = subprocess.run(cmd_parts, cwd=workspace.root, capture_output=True, text=True, timeout=30)
        return {
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:] if completed.stdout else "",
            "stderr": completed.stderr[-4000:] if completed.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": "Command timed out after 30 seconds"
        }
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"Error running command: {str(e)}"
        }

# Map tool names to Tool instances
TOOL_MAP: Dict[str, Tool] = {
    "patch_file": Tool(
        patch_file,
        name="patch_file",
        description="""Replace the entire contents of a file. Use this to fix errors in Terraform files.
        
IMPORTANT: This replaces the ENTIRE file content, not just parts of it.
Example usage: To fix a syntax error in main.tf, provide the complete corrected file content.
Note: Cannot create new files - use only for existing files.""",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string", 
                    "description": "Path to file relative to repo root (e.g., 'ecs/us-east-1/provider.tf')"
                },
                "diff": {
                    "type": "string", 
                    "description": "The complete new contents of the file. Must be valid Terraform syntax."
                },
            },
            "required": ["path", "diff"],
        },
    ),
    "delete_file": Tool(
        delete_file,
        name="delete_file",
        description="""Delete a file from the repository. Use sparingly - only for truly unnecessary files.
        
WARNING: Cannot be undone. Only delete files that are causing errors and cannot be fixed.
Example: Removing duplicate provider configurations.""",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to file relative to repo root"
                },
            },
            "required": ["path"],
        },
    ),
    "run_command": Tool(
        run_command,
        name="run_command",
        description="""Execute a shell command in the workspace. Common commands:
        
Terraform commands:
- 'terraform init' - Initialize modules and backend (run this FIRST if modules present)
- 'terraform validate' - Check syntax (run after init)
- 'terraform plan' - Preview changes
- 'terraform fmt' - Format files

AWS CLI commands (any AWS CLI command can be run):
- 'aws sts get-caller-identity' - Verify AWS credentials
- 'aws s3 ls' - List S3 buckets
- 'aws ec2 describe-instances' - List EC2 instances
- 'aws rds describe-db-instances' - List RDS instances
- 'aws lambda list-functions' - List Lambda functions
- 'aws iam list-roles' - List IAM roles
- 'aws cloudformation list-stacks' - List CloudFormation stacks
- 'aws elbv2 describe-load-balancers' - List ALBs/NLBs
- 'aws eks list-clusters' - List EKS clusters
- 'aws dynamodb list-tables' - List DynamoDB tables
- 'aws secretsmanager list-secrets' - List Secrets Manager secrets

The command runs with a 30-second timeout and returns stdout/stderr.""",
        parameters={
            "type": "object",
            "properties": {
                "cmd": {
                    "type": "string",
                    "description": "Shell command to execute (e.g., 'terraform init', 'aws sts get-caller-identity')"
                },
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