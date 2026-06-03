from __future__ import annotations

def ensure_loaded(func):
    def wrapper(self, *args, **kwargs):
        self._require_loaded()
        return func(self, *args, **kwargs)
    return wrapper