# =====================================================================
# Project Positronic — Polytemporal Cognitive Engram Memory Substrate
# Copyright (C) 2026 Shing Wong. All Rights Reserved.
# =====================================================================
# This program is DUAL-LICENSED. You may redistribute and/or modify it 
# under the terms of the GNU Affero General Public License as published by the 
# Free Software Foundation, either version 3 of the License, or (at your 
# option) any later version.
#
# Alternatively, commercial entities, multi-tenant instances, and Managed 
# Service Providers (MSPs) may utilize this program under a separate, 
# proprietary Commercial License Waiver issued directly by the copyright 
# holder, completely exempt from the network-use copyleft restrictions of 
# the AGPLv3 Section 13.
#
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU 
# Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License 
# along with this program. If not, see <https://gnu.org>.
# =====================================================================

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