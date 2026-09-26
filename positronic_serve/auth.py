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
import base64
import hashlib
import ipaddress
import json
from pathlib import Path
from typing import Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


class KeyManager(Protocol):
    """Auth seam — contributors ship their own manager without touching the server."""

    def validate(self, token: str | None, *, scope: str = "memory") -> bool: ...

    def inspect(self, token: str | None, *, scope: str = "memory") -> dict | None: ...

    def describe(self) -> dict: ...


class LocalKeyManager:
    """Dev track: no key required (bind to 127.0.0.1)."""

    def validate(self, token: str | None, *, scope: str = "memory") -> bool:
        return True

    def inspect(self, token: str | None, *, scope: str = "memory") -> dict | None:
        return None

    def describe(self) -> dict:
        return {"manager": "local", "scopes": ["memory"]}


class SingleKeyManager:
    """One-key quickie: single bearer token from serve.json."""

    def __init__(self, key: str) -> None:
        self.key = key

    def validate(self, token: str | None, *, scope: str = "memory") -> bool:
        return bool(token) and token == self.key

    def inspect(self, token: str | None, *, scope: str = "memory") -> dict | None:
        return None

    def describe(self) -> dict:
        return {"manager": "single", "scopes": ["memory"]}


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    pad = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + pad)


def _key_id(public_key: Ed25519PublicKey) -> str:
    raw = public_key.public_bytes(serialization.Encoding.Raw,
                                  serialization.PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()[:16]


def ip_in_subnet(ip: str, subnet: str) -> bool:
    """True when ip falls inside the CIDR subnet (strict=False, mapped-v4 unwrapped)."""
    try:
        addr = ipaddress.ip_address(ip)
        net = ipaddress.ip_network(subnet, strict=False)
    except ValueError:
        return False
    if addr.version == 6 and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    try:
        return addr in net
    except TypeError:                      # IPv4/IPv6 version mismatch
        return False


def host_matches_domain(host: str, domain: str) -> bool:
    """Exact, case-insensitive Host/allowed_domain match with the port removed."""
    value = (host or "").strip().lower()
    if value.startswith("["):              # bracketed IPv6: [::1]:2114
        value = value[1:].split("]", 1)[0]
    elif value.count(":") == 1:            # name:port or v4:port
        value = value.split(":", 1)[0]
    return bool(value) and value == (domain or "").strip().lower()


class BoundKeyManager:
    """bound-single: Ed25519-signed bearer token bound to a network identity.

    Verify-only: the server embeds the Master Public Key (PEEP-0002 §4.5)
    and never mints tokens.
    """

    def __init__(self, public_key: Ed25519PublicKey) -> None:
        self._public_key = public_key
        self.key_id = _key_id(public_key)

    @classmethod
    def from_config(cls, cfg: dict) -> "BoundKeyManager":
        inline = cfg.get("public_key")
        path = cfg.get("public_key_file")
        if inline and path:
            raise ValueError("bound-single: set public_key or "
                             "public_key_file, not both")
        if path:
            data = Path(path).read_bytes()
        elif inline:
            data = _b64url_decode(inline)
        else:
            raise ValueError("bound-single requires public_key "
                             "or public_key_file")
        return cls(_load_public_key(data))

    def inspect(self, token: str | None, *, scope: str = "memory") -> dict | None:
        if not token or token.count(".") != 2:
            return None
        header_b64, claims_b64, sig_b64 = token.split(".")
        try:
            header = json.loads(_b64url_decode(header_b64))
            claims = json.loads(_b64url_decode(claims_b64))
            signature = _b64url_decode(sig_b64)
        except ValueError:
            return None
        if not isinstance(header, dict) or not isinstance(claims, dict):
            return None
        if header.get("alg") != "EdDSA":   # rejects alg=none and confusion
            return None
        if header.get("kid") != self.key_id:
            return None
        message = f"{header_b64}.{claims_b64}".encode("ascii")
        try:
            self._public_key.verify(signature, message)
        except InvalidSignature:
            return None
        subnet = claims.get("allowed_subnet")
        domain = claims.get("allowed_domain")
        if not isinstance(subnet, str) or not isinstance(domain, str):
            return None
        if not domain.strip():
            return None
        try:
            ipaddress.ip_network(subnet, strict=False)
        except ValueError:
            return None
        return claims

    def validate(self, token: str | None, *, scope: str = "memory") -> bool:
        return self.inspect(token, scope=scope) is not None

    def describe(self) -> dict:
        return {"manager": "bound-single", "scopes": ["memory"],
                "key_id": self.key_id}


def _load_public_key(data: bytes) -> Ed25519PublicKey:
    if data.lstrip().startswith(b"-----BEGIN"):
        key = serialization.load_pem_public_key(data)
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError("bound-single: key must be an Ed25519 public key")
        return key
    if len(data) != 32:
        raise ValueError("bound-single: raw public key must be 32 bytes")
    return Ed25519PublicKey.from_public_bytes(data)


def mint_bound_token(private_key: Ed25519PrivateKey, claims: dict) -> str:
    """Mint a bound-single token client-side; the server only verifies."""
    header = {"alg": "EdDSA", "kid": _key_id(private_key.public_key())}
    header_b64 = _b64url_encode(
        json.dumps(header, separators=(",", ":")).encode())
    claims_b64 = _b64url_encode(
        json.dumps(claims, separators=(",", ":")).encode())
    signature = private_key.sign(f"{header_b64}.{claims_b64}".encode("ascii"))
    return f"{header_b64}.{claims_b64}.{_b64url_encode(signature)}"


def public_key_b64(private_key: Ed25519PrivateKey) -> str:
    """Base64url Master Public Key for serve.json auth.public_key."""
    raw = private_key.public_key().public_bytes(serialization.Encoding.Raw,
                                                serialization.PublicFormat.Raw)
    return _b64url_encode(raw)


_MANAGERS = {"local": LocalKeyManager, "single": SingleKeyManager,
             "bound-single": BoundKeyManager}


def build_key_manager(cfg: dict) -> KeyManager:
    """Build from serve.json auth block: {manager: local|single, key: ...}."""
    manager = (cfg or {}).get("manager", "local")
    if manager not in _MANAGERS:
        raise ValueError(f"unknown key manager: {manager!r} "
                         f"(supported: {sorted(_MANAGERS)})")
    if manager == "single":
        return SingleKeyManager((cfg or {}).get("key", ""))
    if manager == "bound-single":
        return BoundKeyManager.from_config(cfg or {})
    return LocalKeyManager()