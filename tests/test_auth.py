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
import pytest

from positronic_serve.auth import LocalKeyManager, SingleKeyManager, build_key_manager


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