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

# positronic_serve/cli.py
import argparse
import sys


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="positronic-serve",
                                description="PEEP network layer (port 2114)")
    p.add_argument("--config-dir", default=".", help="dir holding .positronic + serve.json")
    p.add_argument("--host", default=None)
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--reload", action="store_true")
    args = p.parse_args(argv)

    from positronic_serve.config import load_config
    from positronic_serve.server import create_app

    cfg = load_config(args.config_dir)
    host = args.host or cfg.get("host", "127.0.0.1")
    port = args.port or cfg.get("port", 2114)

    import uvicorn
    uvicorn.run(create_app(cfg), host=host, port=port,
                reload=args.reload, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())