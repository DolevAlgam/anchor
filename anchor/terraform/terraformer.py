import os
import subprocess
from pathlib import Path
from typing import List, Optional


def import_aws(output_dir: str, regions: Optional[List[str]] = None) -> int:
    """Run terraformer import aws for given regions.

    Returns the subprocess return code.
    """
    regions = regions or [os.getenv("AWS_REGION", "us-east-1")]
    region_arg = ",".join(regions)

    # Limited set of services to import
    services = "cloudwatch,ec2_instance,ebs,ecs,lambda,cloudfront,api_gateway,s3,eks,ecr"

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

    # Initialise Terraform (downloads providers if not cached)
    subprocess.run(["terraform", "init", "-backend=false"], cwd=output_dir)
    return 0 