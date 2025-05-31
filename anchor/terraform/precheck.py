"""Pre-check workflows for Terraform configurations.

Following Anthropic's best practices: use simple, deterministic workflows
before resorting to autonomous agents.
"""
import logging
from pathlib import Path
from typing import Dict, List, Tuple
import re

LOGGER = logging.getLogger("anchor.terraform.precheck")


def check_module_structure(terraform_dir: Path) -> List[Dict[str, str]]:
    """Check for common module structure issues."""
    issues = []
    
    # Check if main.tf exists
    main_tf = terraform_dir / "main.tf"
    if not main_tf.exists():
        issues.append({
            "file": "main.tf",
            "issue": "Missing main.tf file",
            "fix": "Run terraformer import first"
        })
        return issues
    
    # Check if modules are referenced
    main_content = main_tf.read_text()
    module_pattern = r'module\s+"([^"]+)"\s*{\s*source\s*=\s*"([^"]+)"'
    modules = re.findall(module_pattern, main_content)
    
    for module_name, module_source in modules:
        # Check if module directory exists
        if module_source.startswith("./"):
            module_path = terraform_dir / module_source[2:]
            if not module_path.exists():
                issues.append({
                    "file": "main.tf",
                    "issue": f"Module '{module_name}' references non-existent path: {module_source}",
                    "fix": f"Check if path {module_source} exists or correct the source path"
                })
    
    return issues


def check_required_files(terraform_dir: Path) -> List[Dict[str, str]]:
    """Check for required Terraform files."""
    issues = []
    required_files = {
        "variables.tf": "Variable definitions for AWS credentials",
        "provider.tf": "AWS provider configuration",
        "backend.tf": "Terraform state backend configuration"
    }
    
    for filename, description in required_files.items():
        filepath = terraform_dir / filename
        if not filepath.exists():
            issues.append({
                "file": filename,
                "issue": f"Missing {filename} ({description})",
                "fix": f"Create {filename} with appropriate configuration"
            })
    
    return issues


def check_provider_issues(terraform_dir: Path) -> List[Dict[str, str]]:
    """Check for common provider configuration issues."""
    issues = []
    
    # Find all provider.tf files
    provider_files = list(terraform_dir.rglob("provider.tf"))
    
    for provider_file in provider_files:
        content = provider_file.read_text()
        
        # Check for hardcoded credentials
        if "access_key" in content and "=" in content and "var." not in content:
            issues.append({
                "file": str(provider_file.relative_to(terraform_dir)),
                "issue": "Possible hardcoded AWS credentials",
                "fix": "Use variables instead: access_key = var.aws_access_key"
            })
        
        # Check for duplicate provider blocks
        provider_count = content.count('provider "aws"')
        if provider_count > 1:
            issues.append({
                "file": str(provider_file.relative_to(terraform_dir)),
                "issue": f"Multiple provider blocks ({provider_count}) in same file",
                "fix": "Keep only one provider block per file"
            })
    
    return issues


def run_prechecks(terraform_dir: str) -> Tuple[bool, List[Dict[str, str]]]:
    """Run all pre-checks and return (success, issues)."""
    terraform_path = Path(terraform_dir)
    all_issues = []
    
    LOGGER.info("Running Terraform pre-checks...")
    
    # Run all checks
    all_issues.extend(check_required_files(terraform_path))
    all_issues.extend(check_module_structure(terraform_path))
    all_issues.extend(check_provider_issues(terraform_path))
    
    if all_issues:
        LOGGER.warning(f"Found {len(all_issues)} issues during pre-check")
        for issue in all_issues:
            LOGGER.warning(f"  {issue['file']}: {issue['issue']}")
    else:
        LOGGER.info("Pre-checks passed successfully")
    
    return len(all_issues) == 0, all_issues


def auto_fix_simple_issues(terraform_dir: str, issues: List[Dict[str, str]]) -> int:
    """Automatically fix simple, deterministic issues.
    
    Returns number of fixes applied.
    """
    terraform_path = Path(terraform_dir)
    fixes_applied = 0
    
    for issue in issues:
        # Only auto-fix very safe, deterministic issues
        if issue["file"] == "variables.tf" and "Missing" in issue["issue"]:
            # This would have been created by terraformer.py already
            LOGGER.info(f"Skipping auto-fix for {issue['file']} - should exist already")
        
        # Add more deterministic fixes here as needed
    
    return fixes_applied 