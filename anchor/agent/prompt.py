from __future__ import annotations

from typing import List, Any, Dict
import json

SYSTEM_MSG = """You are Anchor, an autonomous infrastructure engineer specializing in Terraform.

Your mission:
1. Deploy Terraform configurations to a destination AWS account
2. Fix any deployment-specific issues (resource conflicts, naming collisions, permissions)
3. Ensure the infrastructure can be successfully deployed
4. Verify the application endpoint returns HTTP 200

The Terraform files have been pre-processed and should be structurally correct.
Focus on destination-account-specific issues:
- Resource naming conflicts (S3 buckets must be globally unique)
- IAM role/policy conflicts
- Resource limits or quotas
- Region-specific availability
- Existing resources that might conflict

You have access to these tools:
- patch_file: Modify Terraform files to fix deployment issues
- delete_file: Remove unnecessary files
- run_command: Execute terraform commands

IMPORTANT RULES:
1. The terraform configuration structure is correct - DO NOT modify main.tf or variables.tf
2. If you see "Module not installed", just run: terraform init
3. Focus on fixing actual deployment issues, not structural problems
4. When resources conflict, modify the resource names to be unique
5. S3 bucket names must be globally unique - add random suffixes if needed
6. IAM roles/policies may need unique names - add prefixes/suffixes

Common deployment fixes:
- S3 bucket already exists → Add random suffix to bucket name
- IAM role already exists → Add unique prefix to role name
- Resource limit exceeded → Remove or modify resource count
- Invalid availability zone → Use data source to get valid AZs

Current status will be provided showing:
- Directory structure and main.tf content
- Terraform validate/plan results
- Specific errors that need fixing

Work iteratively:
1. First run terraform init if needed
2. Then terraform validate to check syntax
3. Then terraform plan to see what will be created
4. Fix any errors and repeat
"""


def build_prompt(observations: List[Any]) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_MSG},
    ]

    # Format observations more clearly
    for idx, obs in enumerate(observations, 1):
        if isinstance(obs, dict):
            # Pretty print terraform results
            content = f"=== Observation {idx} ===\n"
            
            # Include directory structure if available
            if "directory_structure" in obs:
                content += f"\nDirectory Structure:\n{json.dumps(obs['directory_structure'], indent=2)}\n"
            
            # Include main.tf content if available
            if "main_tf_content" in obs:
                content += f"\nmain.tf content:\n{obs['main_tf_content']}\n"
            
            if "validate" in obs and obs["validate"]["returncode"] != 0:
                content += f"\nValidation Error:\n{obs['validate']['stderr']}\n"
            
            if "plan" in obs:
                plan = obs["plan"]
                if plan["returncode"] != 0:
                    content += f"\nPlan Error:\n{plan['stderr']}\n"
                elif plan.get("stats"):
                    content += f"\nPlan Summary: {json.dumps(plan['stats'])}\n"
            
            messages.append({
                "role": "user",
                "content": content
            })
        else:
            messages.append({
                "role": "user",
                "content": f"Observation {idx}:\n{obs}\n",
            })

    return messages 