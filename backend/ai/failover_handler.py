"""Rate-limit handling, exponential backoff, and thread-safe key rotation.

Extracted from ``packages/ai_engine/service.py``. All mutable state (active
key index, failover attempts, provider binding) is guarded by a lock so
multiple worker threads can share one ``AIService`` instance safely.
"""

import threading
import time

BACKOFF_TIMES = [3, 6, 12, 24, 48]
DEFAULT_MAX_RETRIES = 5

_TIMEOUT_KEYS = ("timeout", "connection")
_CONN_REFUSED_KEYS = ("ConnectionRefused", "ConnectError", "Failed to connect", "ECONNREFUSED")


def detect_rate_limit(err: str) -> bool:
    e = err.lower()
    return "429" in err or "quota" in e or "exhausted" in e


def detect_auth_failure(err: str) -> bool:
    e = err.lower()
    return (
        "401" in err
        or "403" in err
        or "invalid_api_key" in e
        or "authentication" in e
    )


def detect_connection_refused(err: str) -> bool:
    return any(key in err for key in _CONN_REFUSED_KEYS)


def detect_retryable(err: str) -> bool:
    e = err.lower()
    if detect_connection_refused(err):
        return True
    return (
        "429" in err
        or "500" in err
        or "502" in err
        or "503" in err
        or "504" in err
        or any(k in e for k in _TIMEOUT_KEYS)
        or "JSON Parse Error" in err
    )


class KeyRing:
    """Thread-safe pool of API keys for the active provider."""

    def __init__(self, api_keys):
        self._lock = threading.Lock()
        self._keys = self._normalize(api_keys)
        self._index = 0

    @staticmethod
    def _normalize(api_keys) -> list[str]:
        if isinstance(api_keys, str):
            keys = [k.strip() for k in api_keys.splitlines() if k.strip()]
            if not keys:
                keys = [api_keys]
        elif isinstance(api_keys, list):
            keys = [k for k in api_keys if k and isinstance(k, str)]
        else:
            keys = []
        return keys or [""]

    def current(self) -> str:
        with self._lock:
            return self._keys[self._index]

    def position(self) -> tuple[int, int]:
        """Return (current_index, total_keys) for log messages."""
        with self._lock:
            return self._index, len(self._keys)

    def size(self) -> int:
        with self._lock:
            return len(self._keys)

    def index(self) -> int:
        with self._lock:
            return self._index

    def rotate(self) -> str:
        """Cycle to the next key and return it. Used on rate-limit/key exhaustion."""
        with self._lock:
            self._index = (self._index + 1) % len(self._keys)
            return self._keys[self._index]

    def replace(self, keys) -> str:
        """Replace the whole pool (used on provider failover). Returns new active key."""
        with self._lock:
            self._keys = self._normalize(keys)
            self._index = 0
            return self._keys[0]


class FailoverHandler:
    """Container for retry/backoff/rotation/failover state shared by workers."""

    def __init__(
        self,
        api_keys,
        failover_providers: dict | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_times: list[int] | None = None,
    ):
        self._lock = threading.Lock()
        self.keyring = KeyRing(api_keys)
        self.failover_providers = failover_providers or {}
        self.max_retries = max_retries
        self.backoff_times = list(backoff_times or BACKOFF_TIMES)
        self._failover_attempted = False
        self.provider = None

    def bind_provider(self, provider: str):
        with self._lock:
            self.provider = provider

    def api_key(self) -> str:
        return self.keyring.current()

    def has_failovers(self) -> int:
        """Return number of usable failover providers for the active provider."""
        count = 0
        for alt_provider, alt_key in self.failover_providers.items():
            if alt_key and alt_provider != self.provider:
                count += 1
        return count

    def backoff_delay(self, attempt: int) -> int:
        return self.backoff_times[attempt] if attempt < len(self.backoff_times) else 30

    def rotate_key(self) -> str:
        return self.keyring.rotate()

    def replace_keys(self, keys) -> str:
        return self.keyring.replace(keys)

    def mark_failover_attempted(self):
        with self._lock:
            self._failover_attempted = True

    @property
    def failover_attempted(self) -> bool:
        with self._lock:
            return self._failover_attempted

    def wait_backoff(self, attempt: int):
        time.sleep(self.backoff_delay(attempt))