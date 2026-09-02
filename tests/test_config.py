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