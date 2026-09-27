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

# tests/test_auth.py
import hashlib

import pytest

from positronic_serve.auth import (
    LocalKeyManager,
    SingleKeyManager,
    build_key_manager,
    host_matches_domain,
    ip_in_subnet,
    mint_bound_token,
    public_key_b64,
)


def test_local_manager_accepts_any_or_no_token():
    m = LocalKeyManager()
    assert m.validate(None) is True
    assert m.validate("anything") is True


def test_single_manager_requires_exact_key():
    m = SingleKeyManager("sekret")
    assert m.validate("sekret") is True
    assert m.validate("wrong") is False
    assert m.validate(None) is False


def test_build_local_default():
    assert isinstance(build_key_manager({"manager": "local"}), LocalKeyManager)


def test_build_single_uses_key():
    m = build_key_manager({"manager": "single", "key": "abc"})
    assert m.validate("abc") is True and m.validate("nope") is False


def test_build_unknown_manager_raises():
    with pytest.raises(ValueError):
        build_key_manager({"manager": "google"})


BOUND_CLAIMS = {"allowed_subnet": "10.66.66.0/24",
                "allowed_domain": "ops.example.com"}


def _ed25519():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
    return Ed25519PrivateKey.generate()


def _bound_manager(priv):
    return build_key_manager(
        {"manager": "bound-single", "public_key": public_key_b64(priv)})


def _kid(priv):
    from cryptography.hazmat.primitives import serialization as ser
    raw = priv.public_key().public_bytes(ser.Encoding.Raw,
                                         ser.PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()[:16]


def _raw_token(priv, header, claims):
    """Build a token with a custom header (mint_bound_token fixes alg/kid)."""
    import base64 as b64
    import json as js

    def enc(obj):
        raw = b64.urlsafe_b64encode(
            js.dumps(obj, separators=(",", ":")).encode())
        return raw.rstrip(b"=").decode()

    header_b64 = enc(header)
    claims_b64 = enc(claims)
    signature = priv.sign(f"{header_b64}.{claims_b64}".encode("ascii"))
    sig_b64 = b64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"{header_b64}.{claims_b64}.{sig_b64}"


def test_local_and_single_inspect_have_no_claims():
    assert LocalKeyManager().inspect("anything") is None
    assert SingleKeyManager("sekret").inspect("sekret") is None


def test_bound_mint_inspect_roundtrip():
    priv = _ed25519()
    mgr = _bound_manager(priv)
    token = mint_bound_token(priv, BOUND_CLAIMS)
    assert mgr.validate(token) is True
    assert mgr.inspect(token) == BOUND_CLAIMS
    assert mgr.describe()["manager"] == "bound-single"
    assert mgr.describe()["key_id"] == _kid(priv)


def test_bound_rejects_token_signed_by_other_key():
    token = mint_bound_token(_ed25519(), BOUND_CLAIMS)
    mgr = _bound_manager(_ed25519())
    assert mgr.validate(token) is False
    assert mgr.inspect(token) is None


def test_bound_rejects_alg_none():
    priv = _ed25519()
    mgr = _bound_manager(priv)
    token = _raw_token(priv, {"alg": "none", "kid": _kid(priv)}, BOUND_CLAIMS)
    assert mgr.validate(token) is False


def test_bound_rejects_kid_mismatch():
    priv = _ed25519()
    mgr = _bound_manager(priv)
    real = _kid(priv)
    wrong = ("0" if real[0] != "0" else "1") + real[1:]
    token = _raw_token(priv, {"alg": "EdDSA", "kid": wrong}, BOUND_CLAIMS)
    assert mgr.validate(token) is False


def test_bound_rejects_tampered_claims():
    import base64 as b64
    import json as js
    priv = _ed25519()
    mgr = _bound_manager(priv)
    header_b64, _, sig_b64 = mint_bound_token(priv, BOUND_CLAIMS).split(".")
    forged_claims = {"allowed_subnet": "0.0.0.0/0",
                     "allowed_domain": "ops.example.com"}
    wide = b64.urlsafe_b64encode(
        js.dumps(forged_claims, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()
    assert mgr.validate(f"{header_b64}.{wide}.{sig_b64}") is False


def test_bound_rejects_malformed_tokens():
    mgr = _bound_manager(_ed25519())
    for bad in (None, "", "nonsense", "a.b", "a.b.c.d", "..", ".x."):
        assert mgr.validate(bad) is False, bad


def test_bound_rejects_bad_claims():
    priv = _ed25519()
    mgr = _bound_manager(priv)
    tokens = (
        mint_bound_token(priv, {"allowed_domain": "ops.example.com"}),
        mint_bound_token(priv, {"allowed_subnet": "not-a-cidr",
                                "allowed_domain": "x.example"}),
        mint_bound_token(priv, {"allowed_subnet": "10.0.0.0/8",
                                "allowed_domain": "   "}),
    )
    for token in tokens:
        assert mgr.validate(token) is False


def test_bound_rejects_deeply_nested_claims_without_raising():
    """A claims segment nested past the JSON recursion limit is an invalid
    token, not a server error. json.loads raises RecursionError (a
    RuntimeError), which must not escape inspect() (PEEP-0002 4.5)."""
    import base64 as b64
    import json as js

    mgr = _bound_manager(_ed25519())
    header_b64 = b64.urlsafe_b64encode(
        js.dumps({"alg": "EdDSA", "kid": "0" * 16}).encode()
    ).rstrip(b"=").decode()
    for depth in (9999, 20000):
        nested = ("[" * depth + "]" * depth).encode()
        claims_b64 = b64.urlsafe_b64encode(nested).rstrip(b"=").decode()
        sig_b64 = b64.urlsafe_b64encode(b"\x00" * 64).rstrip(b"=").decode()
        token = f"{header_b64}.{claims_b64}.{sig_b64}"
        assert mgr.validate(token) is False, depth
        assert mgr.inspect(token) is None, depth


def test_bound_rejects_oversized_segments():
    """The pre-parse cap keeps hostile input away from the JSON parser: a
    segment past the cap is malformed by definition, so it is rejected
    without decoding or parsing it at all."""
    mgr = _bound_manager(_ed25519())
    import base64 as b64
    import json as js

    header_b64 = b64.urlsafe_b64encode(
        js.dumps({"alg": "EdDSA", "kid": "0" * 16}).encode()
    ).rstrip(b"=").decode()
    big = b64.urlsafe_b64encode(b"x" * 20000).rstrip(b"=").decode()
    sig_b64 = b64.urlsafe_b64encode(b"\x00" * 64).rstrip(b"=").decode()
    for token in (f"{big}.{big}.{sig_b64}", f"{header_b64}.{big}.{sig_b64}"):
        assert mgr.validate(token) is False


def test_bound_requires_exactly_one_public_key_source():
    with pytest.raises(ValueError):
        build_key_manager({"manager": "bound-single"})
    priv = _ed25519()
    with pytest.raises(ValueError):
        build_key_manager({"manager": "bound-single",
                           "public_key": public_key_b64(priv),
                           "public_key_file": "master.pub"})


def test_ip_in_subnet_matrix():
    assert ip_in_subnet("127.0.0.1", "127.0.0.0/8") is True
    assert ip_in_subnet("127.0.0.1", "10.66.66.0/24") is False
    assert ip_in_subnet("10.66.66.7", "10.66.66.0/24") is True
    assert ip_in_subnet("10.66.66.7", "10.66.66.7/24") is True   # host bits
    assert ip_in_subnet("::ffff:10.66.66.7", "10.66.66.0/24") is True
    assert ip_in_subnet("::1", "127.0.0.0/8") is False
    assert ip_in_subnet("10.66.66.7", "::/0") is False
    assert ip_in_subnet("garbage", "10.0.0.0/8") is False
    assert ip_in_subnet("10.0.0.1", "garbage") is False


def test_host_matches_domain_matrix():
    assert host_matches_domain("LocalHost:21140", "localhost") is True
    assert host_matches_domain("ops.example.com:2114", "OPS.example.com") is True
    assert host_matches_domain("ops.example.com", "ops.example.com") is True
    assert host_matches_domain("ops.example.com", "evil.example") is False
    assert host_matches_domain("[::1]:2114", "::1") is True
    assert host_matches_domain("", "localhost") is False
    assert host_matches_domain("localhost", "") is False