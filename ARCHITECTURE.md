# Anchor – Code-base Map

Below is a high-level call-graph of the current MVP implementation.  Each subgraph groups related functions/classes by module; primary call-edges between modules are shown so you can trace an execution path from the CLI down to Terraform operations and back.

```mermaid
flowchart TD
    %% ============== cmd layer ==========
    subgraph cmd/anchor.py
        A1(parse_args)
        A2(main)
    end

    %% ============== repo helpers ==========
    classDef cls fill:#e6f7ff,stroke:#007acc,stroke-width:2;

    subgraph repo/git.py
        RG1(clone_repo)
        RG2[GitRepo.clone]
        RG3[GitRepo.commit_all]
        RG4[GitRepo.push]
    end

    %% apply class styles
    class RG2,RG3,RG4 cls;

    subgraph repo/github.py
        GH1(open_pull_request)
    end

    %% ============== workspace ==========
    subgraph workspace.py
        WS1[Workspace.__init__]
        WS2[Workspace.snapshot]
        WS3[Workspace.temp]
    end

    %% ============== agent ==========
    subgraph agent/core.py
        AG1[AnchorAgent.__init__]
        AG2[AnchorAgent.run]
    end
    class AG1,AG2 cls;

    subgraph agent/memory.py
        M1[Memory.add]
        M2[Memory.latest]
    end
    class M1,M2 cls;

    subgraph agent/prompt.py
        P1(build_prompt)
    end

    subgraph agent/tools.py
        T0(Tool class)
        T1(patch_file)
        T2(delete_file)
        T3(run_command)
        T4(apply_llm_actions)
    end

    %% ============== terraform layer ==========
    subgraph terraform/executor.py
        TE1[TerraformExecutor.__init__]
        TE2( _run )
        TE3(fmt)
        TE4(init)
        TE5(validate)
        TE6(plan)
        TE7(show_plan_json)
        TE8(apply)
    end
    class TE1 cls;

    subgraph terraform/parser.py
        PS1(plan_stats)
    end

    %% ============== probe ==========
    subgraph probe/http.py
        PR1(check_endpoint)
    end

    %% ==== primary call edges =====
    A2 -->|clones repo| RG2
    A2 -->|creates workspace| WS1
    A2 -->|runs agent| AG2
    RG2 --> RG1
    AG2 --> M1
    AG2 --> M2
    AG2 --> P1
    AG2 --> WS2
    AG2 --> T4
    WS2 --> TE3
    WS2 --> TE4
    WS2 --> TE5
    WS2 --> TE6
    TE6 --> TE7
    WS2 --> PS1
    T4 --> T1
    T4 --> T2
    T4 --> T3
    AG2 -->|health check| PR1
    A2 -->|push & PR| RG4 --> GH1

    %% legend
    classDef note fill:#fffaf0,stroke:#999,stroke-dasharray: 5 5;
```

> Tip: Open this file in a Markdown viewer with Mermaid support (e.g. VS Code with "Markdown: Open Preview") to explore the interactive diagram. 

## Key Implementation Notes

### Docker Deployment
- `Dockerfile` creates a container with Terraform, Terraformer, and all Python dependencies
- `docker-compose.yml` provides easy orchestration with environment variable management
- AWS provider is pre-downloaded during image build for faster startup

### Debug Logging
- Set `LOG_LEVEL=DEBUG` to see full LLM prompts, responses, and tool executions
- Agent logs all workspace snapshots and intermediate states
- Terraform command outputs are captured and logged

### Terraformer Integration
- Runs inside Docker container with consistent Linux environment
- Falls back to creating minimal `main.tf` if import fails
- Credentials are passed via environment variables (SRC_* for discovery, DEST_* for deployment)

### Agent Loop
- Iterates up to `--max-iters` times (default 20)
- Each iteration:
  1. Snapshots workspace state (fmt, validate, plan)
  2. Builds prompt with recent observations
  3. Calls LLM with available tools
  4. Executes returned tool calls
  5. Checks for completion
- Memory buffer keeps last 50 observations for context

## Recent Improvements

- **Module/Directory Name Handling**: All module and directory names are now stripped of trailing spaces, preventing Terraform validation errors.
- **Centralized Configuration**: All configuration defaults (AWS region, branch, log level, max iterations, AWS services for Terraformer, etc.) are now defined in `anchor/constants.py`.
- **Improved Error Handling**: The system now provides clear error messages for invalid AWS credentials, OpenAI API key issues, and module directory problems.

## Troubleshooting

- **Invalid AWS Credentials**: Check your environment variables or `.env.local` for correct AWS keys if you see credential errors.
- **OpenAI API Key Error**: Ensure your `OPENAI_API_KEY` is valid if you see authentication errors.
- **Module Directory Errors**: If you see errors about unreadable module directories, check for valid credentials and resources in the source account.

## Maintainability

- All defaults and service lists are now in `anchor/constants.py` for a single source of truth.
- The agent and Terraformer reference these constants, reducing duplication and improving maintainability.