"""Short-lived in-process cache for the customer product catalogue."""
import threading
import time
from typing import Any

_CACHE_TTL_SECONDS = 10.0
_lock = threading.RLock()
_cached_at = 0.0
_cached_products: list[dict[str, Any]] | None = None

def get_cached_products():
    with _lock:
        if _cached_products is not None and time.monotonic() - _cached_at < _CACHE_TTL_SECONDS:
            return _cached_products
        return None

def set_cached_products(products: list[dict[str, Any]]) -> None:
    global _cached_at, _cached_products
    with _lock:
        _cached_products = products
        _cached_at = time.monotonic()

def invalidate_products_cache() -> None:
    global _cached_at, _cached_products
    with _lock:
        _cached_products = None
        _cached_at = 0.0
