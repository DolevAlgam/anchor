import argparse
import logging
import os
import tempfile
from pathlib import Path

from anchor.repo.git import GitRepo
from anchor.workspace import Workspace
from anchor.agent.core import AnchorAgent
from anchor.terraform.terraformer import import_aws
from ..constants import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_BRANCH,
    DEFAULT_AWS_REGION,
    DEFAULT_LOG_LEVEL,
)

# Set up logging based on environment
log_level = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL)
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
LOGGER = logging.getLogger("anchor.cli")


def parse_args():
    p = argparse.ArgumentParser(description="Anchor MVP runner")
    p.add_argument("repo_url", help="HTTPS URL of the git repo to clone")
    p.add_argument("--branch", default=DEFAULT_BRANCH, help="Branch name to create")
    p.add_argument("--workdir", help="Optional workdir path (default tmp)")
    p.add_argument("--max-iters", type=int, default=DEFAULT_MAX_ITERATIONS)
    return p.parse_args()


def main():
    args = parse_args()
    
    # Log which AWS accounts are configured
    if "SRC_AWS_ACCESS_KEY_ID" in os.environ:
        LOGGER.info("Source AWS account configured for discovery (SRC_AWS_*)")
    else:
        LOGGER.warning("No source AWS credentials found (SRC_AWS_*)")
    
    if "DEST_AWS_ACCESS_KEY_ID" in os.environ:
        LOGGER.info("Destination AWS account configured for deployment (DEST_AWS_*)")
    else:
        LOGGER.warning("No destination AWS credentials found (DEST_AWS_*)")
    
    workdir = args.workdir or tempfile.mkdtemp(prefix="anchor_repo_")
    LOGGER.info("Cloning %s into %s", args.repo_url, workdir)

    repo = GitRepo.clone(args.repo_url, workdir)
    # create new branch
    repo.repo.git.checkout(args.branch, b=True)

    # Setup workspace pointing to infra/terraform (may not exist yet)
    infra_dir = Path(repo.path) / "infra" / "terraform"
    infra_dir.mkdir(parents=True, exist_ok=True)

    # If infra dir is empty, run terraformer import to populate
    if not any(infra_dir.iterdir()):
        LOGGER.info("Running terraformer import to discover resources from source account ...")
        rc = import_aws(str(infra_dir))
        if rc != 0:
            LOGGER.warning("Terraformer import failed (code %s). Creating minimal config.", rc)
            # Create minimal terraform file so agent has something to work with
            main_tf = infra_dir / "main.tf"
            main_tf.write_text(f'''terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = var.aws_region
}}

variable "aws_region" {{
  type    = string
  default = "{DEFAULT_AWS_REGION}"
}}

# TODO: Add resources imported from source account
# Terraformer import failed - add resources manually
''')
            LOGGER.info("Created minimal main.tf as fallback")

    ws = Workspace(str(infra_dir))

    agent = AnchorAgent(workspace=ws, max_iters=args.max_iters)
    success = agent.run()

    repo.commit_all("feat: add terraform infra via anchor")
    repo.push(branch=args.branch)

    if success:
        LOGGER.info("Anchor run succeeded. Remember to open a pull-request!")
    else:
        LOGGER.warning("Anchor run finished but did not fully succeed.")


if __name__ == "__main__":
    main() 