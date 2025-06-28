import threading
from typing import Any, Dict, List, Optional

CACHE_SIZE = 1024  # LRU cache size for team calculations

class SelectiveCache:
    """Custom cache supporting selective invalidation."""
    def __init__(self, maxsize: int = CACHE_SIZE):
        self.maxsize = maxsize
        self._cache: Dict[str, Any] = {}
        self._access_order: List[str] = []  # LRU tracking
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                self._access_order.remove(key)
                self._access_order.append(key)
                return self._cache[key]
            return None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._cache:
                self._access_order.remove(key)
            elif len(self._cache) >= self.maxsize:
                lru_key = self._access_order.pop(0)
                del self._cache[lru_key]
            self._cache[key] = value
            self._access_order.append(key)

    def invalidate_by_team(self, team_name: str) -> int:
        with self._lock:
            invalidated_count = 0
            keys_to_remove = []
            for key in list(self._cache.keys()):
                if self._is_team_key(key, team_name):
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self._cache[key]
                self._access_order.remove(key)
                invalidated_count += 1
            return invalidated_count

    def clear_all(self) -> None:
        with self._lock:
            self._cache.clear()
            self._access_order.clear()

    def _is_team_key(self, cache_key: str, team_name: str) -> bool:
        if cache_key == team_name:
            return True
        team_name_repr = repr(team_name)
        if cache_key.startswith(f"({team_name_repr},") or cache_key == f"({team_name_repr})":
            return True
        import re
        pattern = rf"(\(|,\s*){re.escape(team_name_repr)}(\s*,|\s*\)|$)"
        return bool(re.search(pattern, cache_key))

_hash_cache = SelectiveCache()
_correlation_cache = SelectiveCache()
_success_cache = SelectiveCache()
_classic_stats_cache = SelectiveCache()
_new_stats_cache = SelectiveCache()
_team_process_cache = SelectiveCache()


def _make_cache_key(*args, **kwargs) -> str:
    key_parts = [repr(arg) for arg in args]
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}={repr(v)}")
    return f"({', '.join(key_parts)})"


def selective_cache(cache_instance: SelectiveCache):
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache_key = _make_cache_key(*args, **kwargs)
            cached = cache_instance.get(cache_key)
            if cached is not None:
                return cached
            result = func(*args, **kwargs)
            cache_instance.set(cache_key, result)
            return result
        wrapper.cache_clear = cache_instance.clear_all
        wrapper.cache_invalidate_team = cache_instance.invalidate_by_team
        wrapper.cache_info = lambda: f"Cache entries: {len(cache_instance._cache)}"
        return wrapper
    return decorator
