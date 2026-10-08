from __future__ import annotations
import functools


def ensure_loaded(func):
    """Comprueba que el gestor tiene el fichero cargado antes de ejecutar el método."""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        self._require_loaded()
        return func(self, *args, **kwargs)
    return wrapper
