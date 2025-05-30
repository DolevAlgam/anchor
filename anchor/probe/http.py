import requests
from typing import Tuple


def check_endpoint(url: str, timeout: float = 5.0) -> Tuple[bool, int]:
    """Returns (is_healthy, status_code)."""
    try:
        r = requests.get(url, timeout=timeout)
        return (200 <= r.status_code < 300, r.status_code)
    except requests.RequestException:
        return (False, 0) 