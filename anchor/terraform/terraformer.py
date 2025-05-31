import os
import subprocess
import shutil
import re
from pathlib import Path
from typing import List, Optional, Dict, Set
from ..constants import TERRAFORMER_AWS_SERVICES


def import_aws(output_dir: str, regions: Optional[List[str]] = None) -> int:
    """Run terraformer import aws for given regions.

    Returns the subprocess return code.
    """
    regions = regions or [os.getenv("AWS_REGION", "us-east-1")]
    region_arg = ",".join(regions)

    # Use services from constants
    services = ",".join(TERRAFORMER_AWS_SERVICES)

    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Build command
    print(f"[Terraformer] output_dir={output_dir} regions={region_arg} services={services}")
    
    cmd = [
        "terraformer",
        "import",
        "aws",
        "--profile=",  # Force using environment variables
        f"--resources={services}",
        f"--regions={region_arg}",
        f"--path-output={output_dir}",
        "--compact",
    ]
    
    # Ensure AWS credentials are available
    env = os.environ.copy()
    # Use source AWS credentials for Terraformer
    if "SRC_AWS_ACCESS_KEY_ID" in os.environ:
        env["AWS_ACCESS_KEY_ID"] = os.environ["SRC_AWS_ACCESS_KEY_ID"]
        env["AWS_SECRET_ACCESS_KEY"] = os.environ["SRC_AWS_SECRET_ACCESS_KEY"]
        print(f"[Terraformer] Using source AWS credentials (SRC_AWS_*)")
    
    print(f"[Terraformer] AWS_ACCESS_KEY_ID present: {'AWS_ACCESS_KEY_ID' in env}")
    print(f"[Terraformer] AWS_SECRET_ACCESS_KEY present: {'AWS_SECRET_ACCESS_KEY' in env}")
    print(f"[Terraformer] AWS_REGION: {env.get('AWS_REGION', 'not set')}")
    
    # Disable IMDS lookup to force using environment credentials
    env["AWS_EC2_METADATA_DISABLED"] = "true"

    print(f"[Terraformer] Running command: {' '.join(cmd)}")
    proc = subprocess.run(cmd, text=True, env=env)
    if proc.stdout:
        print(proc.stdout)
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr)
        return proc.returncode

    # Move files from aws directory to output directory
    aws_dir = Path(output_dir) / "aws"
    if aws_dir.exists():
        for item in aws_dir.glob("**/*"):
            if item.is_file():
                rel_path = item.relative_to(aws_dir)
                # Ensure no trailing spaces in directory names
                parts = list(rel_path.parts)
                parts = [p.strip() for p in parts]
                target_path = output_path.joinpath(*parts)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                item.rename(target_path)
        # Remove aws directory and all its contents
        shutil.rmtree(aws_dir)

    # Post-process: Clean up Terraformer output
    clean_terraform_files(output_path)
    
    # Generate main.tf with module blocks for each service/region
    module_blocks = []
    for service_dir in output_path.iterdir():
        if service_dir.is_dir() and not service_dir.name.startswith('.'):
            print(f"[Terraformer] Processing service directory: {service_dir.name}")
            for region_dir in service_dir.iterdir():
                if region_dir.is_dir():
                    # Ensure no trailing spaces in module names
                    service_name = service_dir.name.strip()
                    region_name = region_dir.name.strip()
                    module_name = f"{service_name}_{region_name}"
                    module_source = f"./{service_name}/{region_name}"
                    print(f"[Terraformer] Adding module: {module_name} with source: {module_source}")
                    module_blocks.append(f'''module "{module_name}" {{
  source = "{module_source}"
  aws_access_key = var.aws_access_key
  aws_secret_key = var.aws_secret_key
  aws_region = var.aws_region
}}
''')
    
    # If no modules were found, create a placeholder
    if not module_blocks:
        print("[Terraformer] Warning: No modules found after import")
        # Return early if no modules to avoid creating invalid configuration
        return 1
    
    # Create configuration files in correct order
    # 1. First create variables.tf (required by other files)
    variables_config = '''# IMPORTANT: DO NOT MODIFY THIS FILE - Required for AWS provider configuration
# These variables are used by the root provider and all modules

variable "aws_access_key" {
  description = "AWS access key"
  type        = string
}

variable "aws_secret_key" {
  description = "AWS secret key"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}'''
    variables_path = output_path / "variables.tf"
    print(f"[Terraformer] Creating variables.tf at: {variables_path}")
    try:
        with variables_path.open("w") as f:
            f.write(variables_config)
        print(f"[Terraformer] Created variables.tf successfully")
    except Exception as e:
        print(f"[Terraformer] ERROR creating variables.tf: {e}")
        return 1
    
    # 2. Create provider.tf
    provider_config = '''provider "aws" {
  access_key = var.aws_access_key
  secret_key = var.aws_secret_key
  region     = var.aws_region
}'''
    provider_path = output_path / "provider.tf"
    print(f"[Terraformer] Creating provider.tf at: {provider_path}")
    try:
        with provider_path.open("w") as f:
            f.write(provider_config)
        print(f"[Terraformer] Created provider.tf successfully")
    except Exception as e:
        print(f"[Terraformer] ERROR creating provider.tf: {e}")
        return 1
    
    # 3. Create backend.tf
    backend_config = '''terraform {
  backend "local" {}
}'''
    backend_path = output_path / "backend.tf"
    print(f"[Terraformer] Creating backend.tf at: {backend_path}")
    try:
        with backend_path.open("w") as f:
            f.write(backend_config)
        print(f"[Terraformer] Created backend.tf successfully")
    except Exception as e:
        print(f"[Terraformer] ERROR creating backend.tf: {e}")
        return 1
    
    # 4. Finally create main.tf (depends on variables)
    main_tf_path = output_path / "main.tf"
    print(f"[Terraformer] Creating main.tf at: {main_tf_path}")
    try:
        with main_tf_path.open("w") as f:
            # Add protective header comment
            header = '''# IMPORTANT: DO NOT MODIFY THIS FILE - Auto-generated module definitions
# If you see "Module not installed" errors, run: terraform init
# Each module below references Terraform configurations imported by Terraformer

'''
            f.write(header + "\n".join(module_blocks))
        print(f"[Terraformer] Created main.tf with {len(module_blocks)} modules")
    except Exception as e:
        print(f"[Terraformer] ERROR creating main.tf: {e}")
        return 1
    
    # 5. Initialize Terraform with local state
    print("[Terraformer] Initializing Terraform...")
    init_result = subprocess.run(
        ["terraform", "init", "-backend=false"], 
        cwd=output_dir,
        capture_output=True,
        text=True
    )
    if init_result.returncode != 0:
        print(f"[Terraformer] ERROR during terraform init: {init_result.stderr}")
        return init_result.returncode
    print("[Terraformer] Terraform initialized successfully")
    
    # 6. Validate all files were created
    required_files = ["variables.tf", "provider.tf", "backend.tf", "main.tf"]
    for filename in required_files:
        filepath = output_path / filename
        if not filepath.exists():
            print(f"[Terraformer] ERROR: Required file {filename} does not exist at {filepath}")
            return 1
        else:
            print(f"[Terraformer] Verified {filename} exists")
    
    print(f"[Terraformer] Successfully completed import with {len(module_blocks)} modules")
    
    # Run pre-checks to validate the generated configuration
    from .precheck import run_prechecks
    success, issues = run_prechecks(output_dir)
    if not success:
        print(f"[Terraformer] Pre-check found {len(issues)} potential issues:")
        for issue in issues[:5]:  # Show first 5 issues
            print(f"  - {issue['file']}: {issue['issue']}")
        if len(issues) > 5:
            print(f"  ... and {len(issues) - 5} more issues")
    
    # 7. Create README for the agent
    readme_content = '''# Terraform Configuration - Generated by Terraformer

## Important Files (DO NOT MODIFY)
- `main.tf` - Module definitions for all imported resources
- `variables.tf` - Required AWS credential variables
- `provider.tf` - Root AWS provider configuration
- `backend.tf` - Terraform state backend configuration

## Directory Structure
Each service has its own directory with region subdirectories:
- `service_name/region_name/` - Contains resources.tf, provider.tf, outputs.tf

## Common Issues and Solutions

### "Module not installed"
**Solution**: Run `terraform init`

### "Provider configuration not present"
**Solution**: Ensure each module directory has its own provider.tf

### "Missing required argument"
**Solution**: Check that variables are defined in root variables.tf

## To Deploy
1. Run `terraform init` to initialize modules
2. Run `terraform validate` to check syntax
3. Run `terraform plan` to preview changes
4. Run `terraform apply` to deploy

## AWS Credentials
The configuration uses variables for AWS credentials:
- Set TF_VAR_aws_access_key
- Set TF_VAR_aws_secret_key
- Set TF_VAR_aws_region (defaults to us-east-1)
'''
    readme_path = output_path / "README.md"
    print(f"[Terraformer] Creating README.md at: {readme_path}")
    try:
        with readme_path.open("w") as f:
            f.write(readme_content)
        print(f"[Terraformer] Created README.md with instructions")
    except Exception as e:
        print(f"[Terraformer] ERROR creating README.md: {e}")
    
    return 0 

def clean_terraform_files(directory: Path) -> None:
    """Clean up common issues in Terraformer-generated files."""
    
    print(f"[Terraformer] Starting post-processing cleanup in {directory}")
    
    # Track all required variables across modules
    all_required_vars: Set[str] = set()
    
    for tf_file in directory.rglob("*.tf"):
        if tf_file.name in ["main.tf", "variables.tf", "backend.tf"]:
            continue  # Skip root configuration files
            
        print(f"[Terraformer] Processing {tf_file.relative_to(directory)}")
        
        try:
            content = tf_file.read_text()
            original_content = content
            
            # 1. Remove hardcoded AWS account IDs and replace with data sources
            content = re.sub(
                r'arn:aws:([^:]+):([^:]+):(\d{12}):',
                r'arn:aws:\1:\2:${data.aws_caller_identity.current.account_id}:',
                content
            )
            
            # 2. Remove hardcoded regions and use variables
            content = re.sub(
                r'(region\s*=\s*)"[a-z]{2}-[a-z]+-\d+"',
                r'\1var.aws_region',
                content
            )
            
            # 3. Fix provider references in resources
            content = re.sub(
                r'provider\s*=\s*"aws\.[^"]*"',
                'provider = aws',
                content
            )
            
            # 4. Remove lifecycle prevent_destroy that might block changes
            content = re.sub(
                r'lifecycle\s*\{[^}]*prevent_destroy\s*=\s*true[^}]*\}',
                '',
                content,
                flags=re.DOTALL
            )
            
            # 5. Add proper variable references for common attributes
            # Find all variable references and track them
            var_matches = re.findall(r'var\.(\w+)', content)
            all_required_vars.update(var_matches)
            
            # 6. If this is a provider.tf in a module, ensure it uses variables
            if tf_file.name == "provider.tf" and tf_file.parent.parent != directory:
                content = '''terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  access_key = var.aws_access_key
  secret_key = var.aws_secret_key
  region     = var.aws_region
}

variable "aws_access_key" {
  description = "AWS access key"
  type        = string
}

variable "aws_secret_key" {
  description = "AWS secret key"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}
'''
            
            # 7. Add data source for current account if ARNs are used
            if "data.aws_caller_identity.current.account_id" in content:
                if "data \"aws_caller_identity\" \"current\"" not in content:
                    content = 'data "aws_caller_identity" "current" {}\n\n' + content
            
            # Write back only if changed
            if content != original_content:
                tf_file.write_text(content)
                print(f"[Terraformer] Updated {tf_file.relative_to(directory)}")
                
        except Exception as e:
            print(f"[Terraformer] Error processing {tf_file}: {e}")
    
    # 8. Ensure all modules have required files
    for service_dir in directory.iterdir():
        if service_dir.is_dir() and not service_dir.name.startswith('.'):
            for region_dir in service_dir.iterdir():
                if region_dir.is_dir():
                    # Ensure provider.tf exists in each module
                    module_provider = region_dir / "provider.tf"
                    if not module_provider.exists():
                        print(f"[Terraformer] Creating provider.tf for {region_dir.relative_to(directory)}")
                        module_provider.write_text('''terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  access_key = var.aws_access_key
  secret_key = var.aws_secret_key
  region     = var.aws_region
}

variable "aws_access_key" {
  description = "AWS access key"
  type        = string
}

variable "aws_secret_key" {
  description = "AWS secret key"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}
''') 