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