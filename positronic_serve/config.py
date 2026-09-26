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

# positronic_serve/config.py
import json
from pathlib import Path

from positronic_serve import DEFAULT_PORT

_DEFAULTS = {
    "host": "127.0.0.1",
    "port": DEFAULT_PORT,
    "dir": None,
    "brain": "kairos",
    "auth": {"manager": "local"},
    "peers": [],
}


def load_config(project_dir) -> dict:
    project_dir = Path(project_dir)
    cfg = dict(_DEFAULTS)
    serve_json = project_dir / "serve.json"
    if serve_json.exists():
        loaded = json.loads(serve_json.read_text())
        cfg.update(loaded)
    if cfg.get("dir") is None:
        cfg["dir"] = str(project_dir)
    return cfg