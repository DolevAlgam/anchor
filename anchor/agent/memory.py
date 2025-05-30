from collections import deque
from typing import Any, Deque, List

class Memory:
    """Simple fixed-size memory buffer to store observations between agent steps."""

    def __init__(self, max_items: int = 50):
        self.buffer: Deque[Any] = deque(maxlen=max_items)

    def add(self, item: Any) -> None:
        self.buffer.append(item)

    def latest(self, k: int) -> List[Any]:
        """Return up to k most recent items, newest last."""
        return list(self.buffer)[-k:] 