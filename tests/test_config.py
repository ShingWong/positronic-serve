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

# tests/test_config.py
import json

from positronic_serve.config import load_config


def test_defaults_without_file(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg["host"] == "127.0.0.1"
    assert cfg["port"] == 2114
    assert cfg["auth"] == {"manager": "local"}
    assert cfg["peers"] == []
    assert cfg["brain"] == "kairos"


def test_file_merges_and_keeps_defaults(tmp_path):
    (tmp_path / "serve.json").write_text(json.dumps({
        "port": 8756, "auth": {"manager": "single", "key": "x"},
        "peers": ["https://b.example.com"]}))
    cfg = load_config(tmp_path)
    assert cfg["port"] == 8756
    assert cfg["auth"]["manager"] == "single"
    assert cfg["peers"] == ["https://b.example.com"]
    assert cfg["host"] == "127.0.0.1"      # default preserved
    assert cfg["brain"] == "kairos"         # default preserved