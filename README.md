# Anchor 🚢

**Anchor** is an open-source autonomous infrastructure replicator.  Provide it with:

1. A public Git repository that contains a basic REST API
2. AWS **Account 1** credentials (source) with admin access
3. AWS **Account 2** credentials (destination) with admin access

Anchor will:

* Reverse-engineer all resources in Account 1 using `terraformer`
* Iteratively fix and shape the exported Terraform so it can stand alone
* Deploy the resulting infrastructure to Account 2
* Ship a pull-request to the supplied repo containing a tidy `infra/terraform` directory plus CI/CD workflows

---
## MVP scope

Input ‑ Environment variables

| Variable | Description |
|----------|-------------|
| `REPO_URL` | HTTPS link to the Git repository |
| `SRC_AWS_ACCESS_KEY_ID` / `SRC_AWS_SECRET_ACCESS_KEY` | Admin creds for source account |
| `DEST_AWS_ACCESS_KEY_ID` / `DEST_AWS_SECRET_ACCESS_KEY` | Admin creds for destination account |

Output

* A new branch `anchor/infra` in the repo
* `infra/terraform` directory that plans & applies without errors
* GitHub Actions workflows:
  * `terraform-plan.yml` (runs on pull-request)
  * `terraform-apply.yml` (runs on merge)

---
## High-level flow

1. **Discovery** — export AWS resources from Account 1 via `terraformer`
2. **Agent loop** — LLM-driven agent cleans code, fixes validation errors, adds missing pieces, and applies to Account 2 while health-checking the endpoint
3. **Ship PR** — push branch & open PR with Terraform code + CI/CD

---
## Repository layout (after Anchor runs)

```text
repo/
 ├── infra/
 │   └── terraform/
 │       ├── main.tf
 │       ├── variables.tf
 │       └── ...
 └── .github/workflows/
     ├── terraform-plan.yml
     └── terraform-apply.yml
```

---
## Quick start (development)

### Docker (Recommended)

```bash
# Clone Anchor repo
$ git clone https://github.com/<you>/anchor.git && cd anchor

# Set environment variables
$ export OPENAI_API_KEY=sk-...
$ export SRC_AWS_ACCESS_KEY_ID=AKIA...
$ export SRC_AWS_SECRET_ACCESS_KEY=...
$ export DEST_AWS_ACCESS_KEY_ID=AKIA...
$ export DEST_AWS_SECRET_ACCESS_KEY=...

# Run with Docker Compose
$ docker-compose up --build

# Or run directly with Docker
$ docker build -t anchor:latest .
$ docker run --rm \
  -e OPENAI_API_KEY \
  -e SRC_AWS_ACCESS_KEY_ID \
  -e SRC_AWS_SECRET_ACCESS_KEY \
  -e DEST_AWS_ACCESS_KEY_ID \
  -e DEST_AWS_SECRET_ACCESS_KEY \
  -e AWS_REGION=us-east-1 \
  -e LOG_LEVEL=DEBUG \
  anchor:latest \
  --branch anchor/infra \
  https://github.com/org/repo.git
```

### Local Python

```bash
# Clone Anchor dev repo
$ git clone https://github.com/<you>/anchor.git && cd anchor

# Install prerequisites (macOS example)
$ brew install go terraform
# Easiest: pre-built binary
$ brew install terraformer  # or use their releases page
# Or build via Go
$ go install github.com/GoogleCloudPlatform/terraformer@latest
$ pip install -r requirements.txt  # if Python components are used

# Run MVP
$ REPO_URL=https://github.com/org/repo.git \
  SRC_AWS_ACCESS_KEY_ID=... \
  SRC_AWS_SECRET_ACCESS_KEY=... \
  DEST_AWS_ACCESS_KEY_ID=... \
  DEST_AWS_SECRET_ACCESS_KEY=... \
  python -m anchor.cmd.anchor $REPO_URL
```

### Debug Mode

Set `LOG_LEVEL=DEBUG` to see:
- Full prompt/response exchanges with the LLM
- Terraform command outputs
- Workspace snapshots at each iteration
- Tool execution details

```bash
# Docker
$ docker-compose up  # Already has LOG_LEVEL=DEBUG in docker-compose.yml

# Local
$ LOG_LEVEL=DEBUG python -m anchor.cmd.anchor ...
```

> ⚠️  Use disposable AWS accounts — Anchor requires full admin privileges for now.

> When you create IAM access keys for Anchor/Terraformer, select the purpose **"Command Line Interface (CLI)"** or **"Local code"** in the AWS Console. Anchor runs from your local machine, so it does not need a compute-service or third-party designation.

---
## Roadmap

* Pluggable cloud providers (GCP, Azure)
* Least-privilege IAM synthesis
* Drift detection & cost diffing
* UI dashboard & audit log

---
## License

Anchor is released under the MIT license. See `LICENSE` for details.

## AWS credential setup (read-only discovery)

Follow these steps once in **Account 1** (the source environment). They create a safe, read-only identity for Anchor/Terraformer to enumerate resources.

1. **Create a customer managed policy**
   1. Download or copy `aws-readonly-policy.json` from this repo.
   2. AWS Console → IAM → Policies → **Create policy** → JSON tab → paste the file → **Next** → name it `AnchorReadOnly` → create.
   3. CLI equivalent:
      ```bash
      aws iam create-policy \
        --policy-name AnchorReadOnly \
        --policy-document file://aws-readonly-policy.json
      ```

2. **Create a role that holds the policy (optional but recommended)**
   Creating a role lets you keep long-lived keys minimal and use short-lived STS tokens.

   1. IAM → Roles → **Create role** → Trusted entity: _AWS account_ → **This account** → Next.
   2. Attach the **AnchorReadOnly** policy, continue, and name the role `AnchorReadOnlyRole`.
   3. Record the resulting role ARN (`arn:aws:iam::<acct_id>:role/AnchorReadOnlyRole`).

3. **Create a user that can assume the role (or attach the policy directly)**

   *Fast path* — attach the policy directly:
   ```bash
   aws iam create-user --user-name anchor_ro
   aws iam attach-user-policy \
     --user-name anchor_ro \
     --policy-arn arn:aws:iam::<acct_id>:policy/AnchorReadOnly
   aws iam create-access-key --user-name anchor_ro
   ```
   _Console_: IAM → Users → **Add user** → “Access key ‑ Programmatic access” → skip console password → **Next** → **Attach existing policies** → search & tick **AnchorReadOnly** → create → download **Access key ID / Secret**.

   *Role path* — least privilege with STS:
   1. Create user `anchor_sts` with **no policies**. Generate access keys (CLI/local).  
      Console path: IAM → Users → Add user → Programmatic access.
   2. Attach an inline policy that lets the user assume the role:
      ```json
      {
        "Version": "2012-10-17",
        "Statement": [{
          "Effect": "Allow",
          "Action": "sts:AssumeRole",
          "Resource": "arn:aws:iam::<acct_id>:role/AnchorReadOnlyRole"
        }]
      }
      ```
   3. Anchor/Terraformer can now obtain temporary creds via:
      ```bash
      aws sts assume-role \
        --role-arn arn:aws:iam::<acct_id>:role/AnchorReadOnlyRole \
        --role-session-name anchor
      ```

4. **Select purpose** – when the console prompts for a reason choose **"Command Line Interface (CLI)"** or **"Local code"**. Anchor runs locally.

5. **Set environment variables**
   ```bash
   export SRC_AWS_ACCESS_KEY_ID=AKIA...
   export SRC_AWS_SECRET_ACCESS_KEY=XXX
   # If using STS, also export: AWS_SESSION_TOKEN
   ```

Repeat a similar process in **Account 2** (destination). For the MVP you will eventually attach broader (write) permissions or simply use an AdministratorAccess policy when comfortable.

--- 