# positronic_serve/auth.py
from typing import Protocol


class KeyManager(Protocol):
    """Auth seam — contributors ship their own manager without touching the server."""

    def validate(self, token: str | None, *, scope: str = "memory") -> bool: ...

    def describe(self) -> dict: ...


class LocalKeyManager:
    """Dev track: no key required (bind to 127.0.0.1)."""

    def validate(self, token: str | None, *, scope: str = "memory") -> bool:
        return True

    def describe(self) -> dict:
        return {"manager": "local", "scopes": ["memory"]}


class SingleKeyManager:
    """One-key quickie: single bearer token from serve.json."""

    def __init__(self, key: str) -> None:
        self.key = key

    def validate(self, token: str | None, *, scope: str = "memory") -> bool:
        return bool(token) and token == self.key

    def describe(self) -> dict:
        return {"manager": "single", "scopes": ["memory"]}


_MANAGERS = {"local": LocalKeyManager, "single": SingleKeyManager}


def build_key_manager(cfg: dict) -> KeyManager:
    """Build from serve.json auth block: {manager: local|single, key: ...}."""
    manager = (cfg or {}).get("manager", "local")
    if manager not in _MANAGERS:
        raise ValueError(f"unknown key manager: {manager!r} "
                         f"(supported: {sorted(_MANAGERS)})")
    if manager == "single":
        return SingleKeyManager((cfg or {}).get("key", ""))
    return LocalKeyManager()