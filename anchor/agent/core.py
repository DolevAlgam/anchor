import logging
import time
from typing import Any
import json

from openai import OpenAI

from .prompt import build_prompt
from .tools import TOOL_MAP, apply_llm_actions
from .memory import Memory

LOGGER = logging.getLogger("anchor.agent")
LOGGER.setLevel(logging.DEBUG)


class AnchorAgent:
    """Runs the autonomous loop that cleans & deploys Terraform."""

    def __init__(self, workspace: "Workspace", max_iters: int = 20, model: str = "gpt-4o"):
        self.workspace = workspace
        self.max_iters = max_iters
        self.model = model
        self.llm = OpenAI()
        self.memory = Memory(max_items=50)

    def run(self) -> bool:
        """Execute iterative loop. Returns True on success (apply + probe OK)."""
        for step in range(self.max_iters):
            LOGGER.info("\n=== Agent step %s ===", step + 1)
            observation: Any = self.workspace.snapshot()
            LOGGER.debug("Workspace snapshot: %s", json.dumps(observation, indent=2))
            self.memory.add(observation)

            prompt = build_prompt(self.memory.latest(7))
            LOGGER.debug("Sending prompt with %d messages", len(prompt))
            for msg in prompt:
                LOGGER.debug("Message [%s]: %s", msg["role"], msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"])
            
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=prompt,
                tools=[t.schema for t in TOOL_MAP.values()],
                tool_choice="auto",
            )
            
            LOGGER.debug("LLM response: %s", response.model_dump_json(indent=2)[:1000] + "..." if len(response.model_dump_json()) > 1000 else response.model_dump_json())

            finished = apply_llm_actions(
                response=response,
                workspace=self.workspace,
                tool_map=TOOL_MAP,
                logger=LOGGER,
            )

            if finished:
                LOGGER.info("Goal achieved; exiting loop.")
                return True

            time.sleep(1)

        LOGGER.warning("Maximum iterations reached without complete success.")
        return False 